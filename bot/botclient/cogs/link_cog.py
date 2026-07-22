import random

import discord
from discord import app_commands
from discord.ext import commands
from models.dbcontainer import DbService
from models.models import LeagueUser, User
from league.leagueservice import LeagueService
from .base_cog import BaseCog


# Classic default summoner icons (ids 0-28) that every League account can freely
# select. We challenge users to switch to one of these to prove account ownership.
STOCK_PROFILE_ICON_IDS = list(range(0, 29))

# Data Dragon patch used only to render the target icon image. Any valid version
# works for these stock icons; bump it if the CDN ever drops an old patch.
DDRAGON_VERSION = "14.14.1"


def _icon_image_url(icon_id: int) -> str:
    return f"https://ddragon.leagueoflegends.com/cdn/{DDRAGON_VERSION}/img/profileicon/{icon_id}.png"


class VerifyLinkView(discord.ui.View):
    """Ephemeral 'Verify' button attached to a pending link challenge."""

    def __init__(self, cog: "LinkCog", league_user_id: int, owner_user_id: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.league_user_id = league_user_id
        self.owner_user_id = owner_user_id  # Discord id allowed to press Verify

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.success)
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_user_id:
            await interaction.response.send_message("This verification isn't yours.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        await self.cog._attempt_verify(interaction, self.league_user_id, self)


class LinkCog(BaseCog):
    """Commands for users to link/unlink their own League accounts, with ownership verification."""

    def __init__(self, bot: commands.Bot, db_service: DbService, league_service: LeagueService):
        super().__init__(bot, db_service)
        self.league = league_service

    @app_commands.command(name="linkleague", description="Link one of your League accounts (with ownership check)")
    @app_commands.describe(
        riot_id="Your Riot ID / summoner name (e.g., Faker)",
        tag="Your Riot tag (e.g., NA1)"
    )
    async def linkleague(self, interaction: discord.Interaction, riot_id: str, tag: str):
        await interaction.response.defer(ephemeral=True)

        with self.db.Session() as session:
            user_account = self.get_user(session, str(interaction.user.id), str(interaction.guild.id))
            if not user_account:
                await interaction.followup.send("You're not in the database yet, try again shortly.", ephemeral=True)
                return

            candidate = LeagueUser()
            candidate.summoner_name = riot_id
            candidate.tag = tag

            # 1) Validate the account exists by resolving its PUUID.
            try:
                puuid = self.league.get_puuid(candidate)
            except Exception:
                puuid = None
            if not puuid:
                await interaction.followup.send(
                    f"Couldn't find a Riot account for **{riot_id}#{tag}**. Double-check the ID and tag.",
                    ephemeral=True
                )
                return

            # 2) Block if this account is already *verified* to someone (ignore
            #    unverified/pending rows so a stale claim can't lock others out).
            verified_owner = session.query(LeagueUser).filter(
                LeagueUser.puuid == puuid,
                LeagueUser.verified == True
            ).first()
            if verified_owner:
                if verified_owner.discord_user_id == user_account.id:
                    await interaction.followup.send(f"You already have **{riot_id}#{tag}** verified and linked.", ephemeral=True)
                else:
                    await interaction.followup.send(f"**{riot_id}#{tag}** is already linked to another user.", ephemeral=True)
                return

            # 3) Read the account's current icon (also lets us auto-complete below).
            try:
                current_icon = self.league.get_profile_icon_id(puuid)
            except Exception:
                current_icon = None

            # 4) Reuse an existing pending challenge for this user+account so the
            #    target icon stays STABLE across re-runs / button timeouts — a user
            #    mid-icon-change is never told to switch to a different icon.
            pending = session.query(LeagueUser).filter(
                LeagueUser.puuid == puuid,
                LeagueUser.discord_user_id == user_account.id,
                LeagueUser.verified == False
            ).first()

            if pending is not None:
                target_icon = pending.verification_icon_id
            else:
                # Fresh challenge: pick a stock icon they don't currently have, so
                # verifying always requires an observable change.
                choices = [i for i in STOCK_PROFILE_ICON_IDS if i != current_icon]
                target_icon = random.choice(choices)
                pending = LeagueUser()
                pending.discord_user = user_account
                pending.summoner_name = riot_id
                pending.tag = tag
                pending.puuid = puuid
                pending.trackable = False
                pending.voteable = False
                pending.verified = False
                pending.verification_icon_id = target_icon
                session.add(pending)

            # 5) If they've already set the challenge icon (e.g. the button timed
            #    out while they changed it), finish the link now — no second click.
            if current_icon is not None and current_icon == target_icon:
                if self._other_verified_owner(session, pending):
                    session.delete(pending)
                    session.commit()
                    await interaction.followup.send(
                        f"**{riot_id}#{tag}** was just linked by someone else.", ephemeral=True
                    )
                    return
                pending.verified = True
                pending.trackable = True
                pending.voteable = True
                pending.verification_icon_id = None
                label = self._label(pending)
                session.commit()
                await interaction.followup.send(
                    f"Verified! **{label}** is now linked and your games are tracked.",
                    ephemeral=True
                )
                return

            session.commit()
            pending_id = pending.id

        embed = discord.Embed(
            title="Verify you own this account",
            description=(
                f"To link **{riot_id}#{tag}**, set your **League profile icon** to the one shown below "
                f"(profile icon **#{target_icon}** — one of the free default icons everyone has), "
                "then press **Verify**.\n\n"
                "You can change it in the League client: click your icon on the profile page and pick it."
            ),
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=_icon_image_url(target_icon))
        embed.set_footer(
            text="The Verify button expires in 5 minutes — if it does, just re-run /linkleague "
                 "(you'll get the same icon) and it'll finish once your icon matches."
        )

        view = VerifyLinkView(self, pending_id, interaction.user.id)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    async def _attempt_verify(self, interaction: discord.Interaction, league_user_id: int, view: "VerifyLinkView"):
        """Check the live profile icon against the pending challenge and finalize the link."""
        with self.db.Session() as session:
            pending = session.query(LeagueUser).filter(LeagueUser.id == league_user_id).first()

            if pending is None or pending.verified:
                await interaction.followup.send("This verification is no longer active.", ephemeral=True)
                return

            # Guard against a race: someone else verified this account in the meantime.
            if self._other_verified_owner(session, pending):
                session.delete(pending)
                session.commit()
                await interaction.followup.send(
                    f"**{self._label(pending)}** was just linked by someone else.", ephemeral=True
                )
                return

            try:
                current_icon = self.league.get_profile_icon_id(pending.puuid)
            except Exception:
                await interaction.followup.send(
                    "Couldn't reach Riot to check your icon right now — try Verify again in a moment.",
                    ephemeral=True
                )
                return

            if current_icon != pending.verification_icon_id:
                await interaction.followup.send(
                    f"Your profile icon is still **#{current_icon}**. Set it to **#{pending.verification_icon_id}** "
                    "(shown above), wait a few seconds, then press **Verify** again.",
                    ephemeral=True
                )
                return

            # Success — promote the pending row to a real, tracked link.
            pending.verified = True
            pending.trackable = True
            pending.voteable = True
            pending.verification_icon_id = None
            label = self._label(pending)
            session.add(pending)
            session.commit()

        for child in view.children:
            child.disabled = True
        view.stop()
        try:
            await interaction.edit_original_response(view=view)
        except discord.HTTPException:
            pass

        await interaction.followup.send(
            f"Verified! **{label}** is now linked and your games are tracked. "
            "(You can change your profile icon back whenever you like.)",
            ephemeral=True
        )

    @app_commands.command(name="unlinkleague", description="Remove one of your linked League accounts")
    @app_commands.describe(account="Which linked account to remove (leave blank if you only have one)")
    async def unlinkleague(self, interaction: discord.Interaction, account: str = None):
        await interaction.response.defer(ephemeral=True)

        with self.db.Session() as session:
            user_account = self.get_user(session, str(interaction.user.id), str(interaction.guild.id))
            linked = user_account.league_users if user_account else []

            if not linked:
                await interaction.followup.send("You don't have any linked League accounts.", ephemeral=True)
                return

            if account is not None:
                target = next((lu for lu in linked if self._label(lu).lower() == account.lower()), None)
                if target is None:
                    await interaction.followup.send(
                        f"You don't have **{account}** linked. Your accounts: "
                        + ", ".join(f"**{self._label(lu)}**" for lu in linked),
                        ephemeral=True
                    )
                    return
            elif len(linked) == 1:
                target = linked[0]
            else:
                await interaction.followup.send(
                    "You have multiple linked accounts — pick one to remove: "
                    + ", ".join(f"**{self._label(lu)}**" for lu in linked),
                    ephemeral=True
                )
                return

            label = self._label(target)
            session.delete(target)
            session.commit()

            await interaction.followup.send(f"Unlinked **{label}**.", ephemeral=True)

    @unlinkleague.autocomplete("account")
    async def unlinkleague_account_autocomplete(self, interaction: discord.Interaction, current: str):
        """Suggest the invoking user's linked accounts."""
        with self.db.Session() as session:
            user_account = self.get_user(session, str(interaction.user.id), str(interaction.guild.id))
            labels = [self._label(lu) for lu in (user_account.league_users if user_account else [])]

        return [
            app_commands.Choice(name=label, value=label)
            for label in labels
            if current.lower() in label.lower()
        ][:25]

    @staticmethod
    def _other_verified_owner(session, pending: LeagueUser) -> bool:
        """True if a *different* row has already verified this same account (race guard)."""
        return session.query(LeagueUser).filter(
            LeagueUser.puuid == pending.puuid,
            LeagueUser.verified == True,
            LeagueUser.id != pending.id
        ).first() is not None

    @staticmethod
    def _label(league_user: LeagueUser) -> str:
        """Human-readable 'riot_id#tag' label for a linked account."""
        return f"{league_user.summoner_name}#{league_user.tag}"
