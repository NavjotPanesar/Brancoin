import math
from io import BytesIO
import discord
from discord import app_commands
from discord.ext import commands
from models.dbcontainer import DbService
from models.models import (
    BoosterCard, BoosterPack, BoosterSegment, Card, Guild,
    Image, LeagueUser, User
)
from botclient.drawutils import DrawUtils
from league.leagueservice import LeagueService
from .base_cog import BaseCog


ADMIN_USER_ID = 114930910884790276


def is_admin():
    """Check decorator for admin-only commands."""
    async def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.id == ADMIN_USER_ID
    return app_commands.check(predicate)


class AdminCog(BaseCog):
    """Admin-only commands for managing the bot."""

    def __init__(self, bot: commands.Bot, db_service: DbService, league_service: LeagueService):
        super().__init__(bot, db_service)
        self.league = league_service

    @app_commands.command(name="addleague", description="[ADMIN] Link a League account to a user")
    @app_commands.describe(
        user="Discord user to link",
        summoner_name="League summoner name",
        tag="League tag (e.g., NA1)",
        trackable="Track this user's games",
        voteable="Allow voting on this user's games"
    )
    @is_admin()
    async def addleague(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        summoner_name: str,
        tag: str,
        trackable: bool = False,
        voteable: bool = False
    ):
        with self.db.Session() as session:
            target_user_account = session.query(User).filter(
                User.guild_id == str(interaction.guild.id),
                User.user_id == str(user.id)
            ).first()

            if not target_user_account:
                await interaction.response.send_message("User not found in database", ephemeral=True)
                return

            league_entry = LeagueUser()
            league_entry.discord_user = target_user_account
            league_entry.summoner_name = summoner_name
            league_entry.tag = tag
            league_entry.trackable = trackable
            league_entry.voteable = voteable

            puuid = self.league.get_puuid(league_entry)
            if puuid:
                league_entry.puuid = puuid
            else:
                await interaction.response.send_message("No puuid found", ephemeral=True)
                return

            session.add(league_entry)
            session.commit()

            await interaction.response.send_message("donezo")

    @app_commands.command(name="broadcast", description="[ADMIN] Set this channel as the broadcast channel")
    @app_commands.describe(role="Role to ping on broadcasts (optional)")
    @is_admin()
    async def broadcast(self, interaction: discord.Interaction, role: discord.Role = None):
        with self.db.Session() as session:
            guild = session.query(Guild).filter(
                Guild.guild_id == str(interaction.guild.id)
            ).first()
            guild.broadcast_channel_id = str(interaction.channel.id)
            if role:
                guild.broadcast_role_id = str(role.id)
            session.add(guild)
            session.commit()
            await interaction.response.send_message("joever")

    @app_commands.command(name="addcard", description="[ADMIN] Create a new card")
    @app_commands.describe(
        preview="Preview only (don't save)",
        title="Card title",
        description="Card description",
        level="Card level",
        atk="Attack value (0 for none)",
        defense="Defense value (0 for none)",
        card_style="Card style (normal, effect, etc.)",
        attribute="Card attribute (Earth, Fire, etc.)",
        card_type="Card type (Monster, Spell, etc.)",
        image_label="Label of uploaded image to use",
        cost="Card cost in Brancoins",
        shoppable="Can be bought in shop"
    )
    @is_admin()
    async def addcard(
        self,
        interaction: discord.Interaction,
        preview: bool,
        title: str,
        description: str,
        level: int,
        atk: int,
        defense: int,
        card_style: str,
        attribute: str,
        card_type: str,
        image_label: str,
        cost: int,
        shoppable: bool
    ):
        await interaction.response.defer()

        card = Card()
        card.title = title
        card.description = description
        card.level = str(level)
        card.atk = "" if atk == 0 else str(atk)
        card.defe = "" if defense == 0 else str(defense)
        card.card_style = card_style
        card.attribute = attribute
        card.type = card_type
        card.image_label = image_label
        card.cost = cost
        card.shoppable = shoppable

        if not preview:
            with self.db.Session() as session:
                session.add(card)
                session.commit()
                await interaction.followup.send(f"done {card.id}")
        else:
            with self.db.Session() as session:
                card.image = session.query(Image).filter(Image.label == card.image_label).first()
            await interaction.followup.send(
                file=discord.File(DrawUtils.card_to_byte_image(card), filename="preview.png")
            )

    @app_commands.command(name="addimage", description="[ADMIN] Upload an image for cards")
    @app_commands.describe(
        label="Label for the image",
        image="Image file to upload"
    )
    @is_admin()
    async def addimage(self, interaction: discord.Interaction, label: str, image: discord.Attachment):
        img = Image()
        img.label = label
        img.bin = await image.read()

        with self.db.Session() as session:
            session.add(img)
            session.commit()
            await interaction.response.send_message("done")

    @app_commands.command(name="addbooster", description="[ADMIN] Add a card to a booster pack")
    @app_commands.describe(
        pack="Booster pack ID",
        segment="Segment ID within the pack",
        card_id="ID of the card to add",
        chance="Weight/chance for this card"
    )
    @is_admin()
    async def addbooster(
        self,
        interaction: discord.Interaction,
        pack: str,
        segment: str,
        card_id: int,
        chance: int
    ):
        booster_card = BoosterCard()
        booster_card.booster_pack_id = pack
        booster_card.booster_segment_id = segment
        booster_card.chance = chance

        with self.db.Session() as session:
            card = session.query(Card).filter(Card.id == card_id).first()
            if not card:
                await interaction.response.send_message("Card not found", ephemeral=True)
                return
            booster_card.card = card
            session.add(booster_card)
            session.commit()
            await interaction.response.send_message("done")

    @app_commands.command(name="listsegments", description="[ADMIN] List all booster segments")
    @is_admin()
    async def listsegments(self, interaction: discord.Interaction):
        with self.db.Session() as session:
            segments = session.query(BoosterSegment).all()
            output = ""
            for segment in segments:
                output = output + segment.booster_pack_id + ":" + segment.id + "\n"
            if output:
                await interaction.response.send_message(output)
            else:
                await interaction.response.send_message("No segments found")

    @app_commands.command(name="viewpack", description="[ADMIN] Preview pack contents")
    @app_commands.describe(pack_name="Pack to preview")
    @is_admin()
    async def viewpack(self, interaction: discord.Interaction, pack_name: str):
        await interaction.response.defer()

        with self.db.Session() as session:
            pack = session.query(BoosterPack).filter(BoosterPack.id == pack_name).first()
            if pack is None:
                await interaction.followup.send("can't find pack")
                return

            print_cards = []
            for segment in pack.booster_segments:
                for card in segment.booster_cards:
                    print_cards.append(card.card)

            if not print_cards:
                await interaction.followup.send("Pack has no cards")
                return

            grid_size = math.ceil(math.sqrt(len(print_cards)))
            grid = (grid_size, grid_size)
            inv_img = await DrawUtils.draw_inv_card_spread(print_cards, (1000, 1000), grid, draw_blanks=True)
            buffered = BytesIO()
            inv_img.save(buffered, format="PNG")
            discord_file = discord.File(BytesIO(buffered.getvalue()), filename="previewpack.png")
            await interaction.followup.send(file=discord_file)

    async def cog_app_command_error(self, interaction: discord.Interaction, error):
        """Handle errors for admin commands."""
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("Unauthorized", ephemeral=True)
        else:
            raise error
