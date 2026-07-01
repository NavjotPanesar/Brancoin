import math
import random
import discord
from discord import app_commands
from discord.ext import commands
from models.dbcontainer import DbService
from models.models import CardBonus, Card, OwnedCard, Guild, Match, User, Votes
from botclient.VoteType import VoteType
from botclient.CardBonusType import CardBonusType
from botclient.helpers.economy_utils import upper_class_wealth
from botclient.helpers.match_utils import generate_embed_for_match
from .base_cog import BaseCog


class GamblingCog(BaseCog):
    """Gambling commands: spin, jackpot, voting on matches."""

    # Spin configuration
    spin_cost = 2
    wins = [(1/500, 50), (1/50, 20), (1/18, 10), (1/6, 6), (1/4, 3), (5/8, 2)]
    freebie_chance = 1/100

    @app_commands.command(name="spin", description="Spin the wheel for a chance to win!")
    async def spin(self, interaction: discord.Interaction):
        with self.db.Session() as session:
            is_freebie = random.uniform(0, 1) < self.freebie_chance
            source = self.get_user(session, str(interaction.user.id), str(interaction.guild.id))
            guild = session.query(Guild).filter(Guild.guild_id == str(interaction.guild.id)).first()

            if guild.broadcast_channel_id is not None and str(interaction.channel.id) != guild.broadcast_channel_id:
                await interaction.response.send_message(
                    "Wrong channel, you clown :clown:",
                    ephemeral=True
                )
                return

            if source.brancoins < self.spin_cost:
                await interaction.response.send_message(
                    "You ain't got the facilities for that big man",
                    ephemeral=True
                )
                return

            # Calculate number of rolls (bonus from cards)
            num_rolls = self._num_rolls_to_do(session, interaction.user.id)
            output_msgs = []

            for _ in range(num_rolls):
                output_msgs.append(self._execute_spin(session, source, guild, is_freebie))

            session.commit()
            await interaction.response.send_message('\n------\n'.join(output_msgs))

    def _num_rolls_to_do(self, session, author_id: int) -> int:
        bonus_rolls = session.query(CardBonus).distinct(CardBonus.id).filter(
            CardBonus.bonus_type == CardBonusType.SPIN_2X.value
        ).join(Card).join(OwnedCard).join(User).filter(
            User.user_id == str(author_id)
        ).count()
        return 1 + bonus_rolls if bonus_rolls > 0 else 1

    def _execute_spin(self, session, source: User, guild: Guild, is_freebie: bool) -> str:
        coin_change = 0

        if not is_freebie:
            coin_change -= self.spin_cost

        spin_val = random.uniform(0, 1)
        win_val = 0
        for win in self.wins:
            if spin_val < win[0]:
                win_val = win[1]
                break

        jackpot_chance_dynamic = max(200, math.ceil(
            upper_class_wealth(session, str(guild.guild_id)) * 0.1
        ))
        won_jackpot = spin_val < (1 / jackpot_chance_dynamic)

        jackpot_value = guild.brancoins
        if won_jackpot:
            coin_change += jackpot_value
            guild.brancoins = 0
        else:
            guild.brancoins += self.spin_cost
            coin_change += win_val

        source.brancoins += coin_change

        if won_jackpot:
            output_msg = (
                f":rotating_light: :rotating_light: :rotating_light: "
                f"YOU WON THE JACKPOT OF {jackpot_value} {self.custom_emoji} !!! "
                f":rotating_light: :rotating_light: :rotating_light:"
            )
        else:
            if not is_freebie:
                if win_val == 0:
                    output_msg = f"Paid {self.spin_cost} {self.custom_emoji} ...\nWon nothing... dummy... :clown:"
                else:
                    output_msg = f"Paid {self.spin_cost} {self.custom_emoji} ...\nWon {win_val}!!!!:maracas:"
            else:
                if win_val == 0:
                    output_msg = (
                        "Paid nothing!!! Fames Jermo has blessed you! ...\n"
                        "Won nothing... it looks like this blessing is a toxic curse... :cursed:"
                    )
                else:
                    output_msg = (
                        "Paid nothing!!! Farhan smiles upon you!!\n"
                        f"Won {win_val}!!!! Time to convert!!!!:maracas: <:Prayge:1038601127052193814> :maracas:"
                    )

        session.add(guild)
        session.add(source)
        return output_msg

    @app_commands.command(name="jackpot", description="View the current jackpot")
    async def jackpot(self, interaction: discord.Interaction):
        with self.db.Session() as session:
            guild = session.query(Guild).filter(Guild.guild_id == str(interaction.guild.id)).first()
            await interaction.response.send_message(
                f"Jackpot is currently {guild.brancoins} {self.custom_emoji}"
            )

    @app_commands.command(name="vote", description="Vote on a match outcome")
    @app_commands.describe(
        vote_type="Whether to bet on win or lose",
        coins="Number of coins to bet",
        match_id="Optional specific match ID"
    )
    @app_commands.choices(vote_type=[
        app_commands.Choice(name="win", value="win"),
        app_commands.Choice(name="lose", value="lose"),
    ])
    async def vote(
        self,
        interaction: discord.Interaction,
        vote_type: str,
        coins: int,
        match_id: str = None
    ):
        if coins <= 0:
            await interaction.response.send_message("Nice try.", ephemeral=True)
            return

        vt = VoteType.WIN if vote_type == "win" else VoteType.LOSE

        with self.db.Session() as session:
            source_user = self.get_user(session, str(interaction.user.id), str(interaction.guild.id))

            if source_user.brancoins < coins:
                await interaction.response.send_message(
                    "Stop doing gamba broke boi",
                    ephemeral=True
                )
                return

            source_user.brancoins -= coins

            match_fetch_query = session.query(Match).filter(Match.finished == False)
            if match_id:
                match_fetch_query = match_fetch_query.filter(Match.match_id == match_id)
            target_match = match_fetch_query.first()

            if target_match is None:
                await interaction.response.send_message(
                    "No open matches found",
                    ephemeral=True
                )
                return

            for match_player in target_match.match_players:
                if vt == VoteType.LOSE and source_user.user_id == match_player.league_user.discord_user.user_id:
                    await interaction.response.send_message(
                        "Leave the throwing to tapson, dufus",
                        ephemeral=True
                    )
                    return

            if target_match.get_time_since_start().seconds > 5 * 60:
                await interaction.response.send_message(
                    "Too late idiot",
                    ephemeral=True
                )
                return

            new_vote = Votes()
            new_vote.type_of_vote = vt.value
            new_vote.processed = False
            new_vote.voter = source_user
            new_vote.brancoins = coins
            target_match.votes.append(new_vote)

            session.add(source_user)
            session.add(target_match)
            session.commit()

        await interaction.response.send_message("Vote placed")

    @app_commands.command(name="matches", description="View open matches")
    async def matches(self, interaction: discord.Interaction):
        await interaction.response.defer()

        with self.db.Session() as session:
            open_matches = session.query(Match).filter(Match.finished == False).all()

            if len(open_matches) == 0:
                await interaction.followup.send("No pending matches")
                return

            for open_match in open_matches:
                embedVar = await generate_embed_for_match(open_match, self.bot)
                await interaction.followup.send(embed=embedVar)
