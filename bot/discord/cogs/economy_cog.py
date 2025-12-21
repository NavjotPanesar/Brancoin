import random
import discord
from discord import app_commands
from discord.ext import commands

from models.models import User
from models.dbcontainer import DbService
from envvars import Env


class EconomyCog(commands.Cog):
    """Economy commands for managing Brancoins."""

    def __init__(self, bot, db_service: DbService):
        self.bot = bot
        self.db = db_service
        self.custom_emoji = "<:brancoin:1233204357550575636>" if Env.is_debug == "false" else "<:test:1230694305937756160>"
        self.beg_cache = []  # Track who has begged
        self.freebie_chance = 1 / 30

    @app_commands.command(name="coin", description="Check your balance and League account info")
    async def coin(self, interaction: discord.Interaction):
        """Show your Brancoin balance and linked League accounts."""
        with self.db.Session() as session:
            user = session.query(User).filter(
                User.user_id == str(interaction.user.id),
                User.guild_id == str(interaction.guild.id)
            ).first()

            if not user:
                await interaction.response.send_message("Who are you?", ephemeral=True)
                return

            embed = discord.Embed(title="Brancoins", color=0xffcccc)
            embed.set_author(
                name=interaction.user.display_name,
                icon_url=interaction.user.display_avatar.url
            )
            embed.add_field(name="Total Brancoins", value=str(user.brancoins), inline=False)

            if user.league_users and len(user.league_users) > 0:
                for league_user in user.league_users:
                    embed.add_field(name="LoL tag", value=league_user.tag, inline=False)
                    embed.add_field(name="LoL username", value=league_user.summoner_name, inline=False)

                    membership_text = ""
                    if league_user.trackable:
                        membership_text += "Clown, "
                    if league_user.voteable:
                        membership_text += "RSquad, "
                    if not league_user.voteable and not league_user.trackable:
                        membership_text = "None"
                    membership_text = membership_text.rstrip(", ")
                    embed.add_field(name="Group Membership", value=membership_text, inline=False)
            else:
                embed.add_field(name="LoL account", value="Not connected", inline=False)

            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="board", description="View the Brancoin leaderboard")
    async def board(self, interaction: discord.Interaction):
        """Show the top 10 Brancoin holders."""
        with self.db.Session() as session:
            top_users = session.query(User).filter(
                User.guild_id == str(interaction.guild.id)
            ).order_by(User.brancoins.desc()).limit(10).all()

            embed = discord.Embed(
                title="Brancoin Leaderboard",
                description="Top 10",
                color=0xffcccc
            )

            for user in top_users:
                disc_user = await self.bot.fetch_user(user.user_id)
                if disc_user is not None:
                    embed.add_field(
                        name=disc_user.display_name,
                        value=f"{self.custom_emoji} {user.brancoins}",
                        inline=False
                    )

            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="beg", description="Beg for coins if you're broke")
    async def beg(self, interaction: discord.Interaction):
        """Get 10 free coins if your balance is 0 or less."""
        with self.db.Session() as session:
            user = session.query(User).filter(
                User.user_id == str(interaction.user.id),
                User.guild_id == str(interaction.guild.id)
            ).first()

            if not user:
                await interaction.response.send_message("Who are you?", ephemeral=True)
                return

            if user.brancoins > 0:
                await interaction.response.send_message("You're not broke enough to beg.", ephemeral=True)
                return

            if user.id in self.beg_cache:
                await interaction.response.send_message("You already begged. No more handouts.", ephemeral=True)
                return

            user.brancoins = 10
            session.add(user)
            session.commit()
            self.beg_cache.append(user.id)

            await interaction.response.send_message(f"Enjoy, you brokie\n{self.custom_emoji * 10}")

    @app_commands.command(name="gift", description="Gift coins to another user")
    @app_commands.describe(
        recipient="The user to gift coins to",
        amount="Number of coins to gift"
    )
    async def gift(self, interaction: discord.Interaction, recipient: discord.Member, amount: int):
        """Transfer coins to another user."""
        if amount <= 0:
            await interaction.response.send_message("Amount must be positive.", ephemeral=True)
            return

        if recipient.id == interaction.user.id:
            await interaction.response.send_message("You can't gift yourself.", ephemeral=True)
            return

        with self.db.Session() as session:
            source = session.query(User).filter(
                User.user_id == str(interaction.user.id),
                User.guild_id == str(interaction.guild.id)
            ).first()
            dest = session.query(User).filter(
                User.user_id == str(recipient.id),
                User.guild_id == str(interaction.guild.id)
            ).first()

            if not source:
                await interaction.response.send_message("Who are you?", ephemeral=True)
                return

            if not dest:
                await interaction.response.send_message("Recipient not found.", ephemeral=True)
                return

            if source.brancoins < amount:
                await interaction.response.send_message("You ain't got the facilities for that big man", ephemeral=True)
                return

            is_freebie = random.random() < self.freebie_chance
            if not is_freebie:
                source.brancoins -= amount
            dest.brancoins += amount
            session.commit()

            if is_freebie:
                await interaction.response.send_message(
                    f"Transferred {amount} {self.custom_emoji} to {recipient.mention}\n"
                    "The great Vivian Octave smiles upon you!!!\n"
                    ":maracas: :maracas: This gift will be granted for free! :maracas: :maracas:"
                )
            else:
                await interaction.response.send_message(
                    f"Transferred {amount} {self.custom_emoji} to {recipient.mention}"
                )
