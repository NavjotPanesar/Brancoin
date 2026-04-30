import random
import discord
from discord import app_commands
from discord.ext import commands
from models.dbcontainer import DbService
from models.models import User
from .base_cog import BaseCog


class EconomyCog(BaseCog):
    """Economy commands: coin balance, leaderboard, begging, and gifting."""

    freebie_chance = 1 / 30  # Chance for free gift
    chance_of_free_coin = 1 / 25  # Passive discovery chance
    beg_cache = []  # Track users who have begged

    @app_commands.command(name="coin", description="Check your Brancoin balance")
    async def coin(self, interaction: discord.Interaction):
        with self.db.Session() as session:
            guy = self.get_user(session, str(interaction.user.id), str(interaction.guild.id))
            if guy:
                embedVar = discord.Embed(title="Brancoins", description="", color=0xffcccc)
                embedVar.set_author(
                    name=interaction.user.display_name,
                    icon_url=interaction.user.display_avatar.url
                )
                embedVar.add_field(name="Total Brancoins", value=str(guy.brancoins), inline=False)

                if guy.league_users and len(guy.league_users) > 0:
                    for league_user in guy.league_users:
                        embedVar.add_field(name="LoL tag", value=league_user.tag, inline=False)
                        embedVar.add_field(name="LoL username", value=league_user.summoner_name, inline=False)
                        membership_text = ""
                        if league_user.trackable:
                            membership_text = membership_text + "Clown, "
                        if league_user.voteable:
                            membership_text = membership_text + "RSquad, "
                        if not league_user.voteable and not league_user.trackable:
                            membership_text = "None"
                        membership_text = membership_text.rstrip(", ")
                        embedVar.add_field(name="Group Membership", value=membership_text, inline=False)
                else:
                    embedVar.add_field(name="Lol account", value="Not connected", inline=False)

                await interaction.response.send_message(embed=embedVar)
            else:
                await interaction.response.send_message("Who are you?")

    @app_commands.command(name="board", description="View the Brancoin leaderboard")
    async def board(self, interaction: discord.Interaction):
        lim = 10
        with self.db.Session() as session:
            top_users = session.query(User).filter(
                User.guild_id == str(interaction.guild.id)
            ).order_by(User.brancoins.desc()).limit(lim).all()

            embedVar = discord.Embed(
                title="Braincoin leaderboard",
                description=f"Top {str(lim)}",
                color=0xffcccc
            )
            for user in top_users:
                disc_user = await self.bot.fetch_user(user.user_id)
                if disc_user is not None:
                    embedVar.add_field(
                        name=str(disc_user.display_name),
                        value=f"{self.custom_emoji} {str(user.brancoins)}",
                        inline=False
                    )

            await interaction.response.send_message(embed=embedVar)

    @app_commands.command(name="beg", description="Beg for starter coins (only works if you're broke)")
    async def beg(self, interaction: discord.Interaction):
        with self.db.Session() as session:
            guy = self.get_user(session, str(interaction.user.id), str(interaction.guild.id))
            if guy and guy.brancoins <= 0 and guy.id not in self.beg_cache:
                guy.brancoins = 10
                session.add(guy)
                session.commit()
                self.beg_cache.append(guy.id)
                await interaction.response.send_message(
                    f"Enjoy, you brokie \n {self.custom_emoji * 10}"
                )
            elif guy and guy.brancoins > 0:
                await interaction.response.send_message(
                    "You still have coins, get out of here!",
                    ephemeral=True
                )
            elif guy and guy.id in self.beg_cache:
                await interaction.response.send_message(
                    "You already begged once. No more handouts!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message("Who are you?", ephemeral=True)

    @app_commands.command(name="gift", description="Gift Brancoins to another user")
    @app_commands.describe(
        recipient="The user to gift coins to",
        amount="Number of coins to gift"
    )
    async def gift(self, interaction: discord.Interaction, recipient: discord.Member, amount: int):
        if amount <= 0:
            await interaction.response.send_message("Nice try.", ephemeral=True)
            return

        is_freebie = random.uniform(0, 1) < self.freebie_chance

        with self.db.Session() as session:
            source = self.get_user(session, str(interaction.user.id), str(interaction.guild.id))
            dest = self.get_user(session, str(recipient.id), str(interaction.guild.id))

            if source is None or dest is None:
                await interaction.response.send_message("User not found.", ephemeral=True)
                return

            if source.brancoins < amount:
                await interaction.response.send_message(
                    "You ain't got the facilities for that big man",
                    ephemeral=True
                )
                return

            if not is_freebie:
                source.brancoins -= amount
            dest.brancoins += amount
            session.add(source)
            session.add(dest)
            session.commit()

            if not is_freebie:
                await interaction.response.send_message(
                    f"Transfered {amount} {self.custom_emoji} to {recipient.mention}"
                )
            else:
                await interaction.response.send_message(
                    f"Transfered {amount} {self.custom_emoji} to {recipient.mention}\n"
                    f"The great Vivian Octave smiles upon you!!!\n"
                    f":maracas::maracas: This gift will be granted for free! :maracas: :maracas:"
                )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Passive coin discovery - random chance to earn a coin on any message."""
        if message.author.bot:
            return
        if message.guild is None:
            return

        if random.uniform(0, 1) < self.chance_of_free_coin:
            with self.db.Session() as session:
                guy = self.get_user(session, str(message.author.id), str(message.guild.id))
                if guy:
                    guy.brancoins = guy.brancoins + 1
                    session.add(guy)
                    session.commit()
                    await message.add_reaction(self.custom_emoji)
