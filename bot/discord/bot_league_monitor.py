import discord
import discord.ext.commands
import traceback

from discord.commands.torchdupes import DeleteDupeCards
from discord.commands.torch import DeleteCard
from discord.commands.viewcard import ViewCard
from discord.commands.viewpackcards import ViewPackCards
from discord.commands.openpack import OpenPack
from discord.commands.addcard import AdminAddCard
from discord.commands.addimage import AdminAddImage
from discord.commands.selectcard import SelectCard
from discord.commands.inventory import Inventory
from discord.commands.buy import Buy
from discord.commands.viewshop import ViewShop
from discord.commands.vote import AddVote
from discord.commands.addbroadcast import AdminAddBroadcast
from discord.commands.addleague import AdminAddLeague
from discord.commands.jackpot import ViewJackpot
from discord.commands.viewmatches import ViewMatches
from discord.commands.spin import Spin
from discord.commands.addbooster import AdminAddBooster
from discord.commands.discover import Discover
from discord.cogs.broadcast_cog import BroadcastCog
from discord.cogs.economy_cog import EconomyCog
from discord.cogs.jackpot_cog import JackpotCog
from discord.cogs.game_monitor_cog import GameMonitorCog
from models.models import Guild, LeagueUser, User
from league.leaguecontainer import LeagueContainer
from models.dbcontainer import DbContainer, DbService
from league.leagueservice import LeagueService
from dependency_injector.wiring import Provide, inject
from envvars import Env
from discord.ext import commands


@inject
class DiscordMonitorClient(commands.Bot):
    commands = []

    @inject
    def __init__(self, intents, dbservice: DbService = Provide[DbContainer.service], league_service: LeagueService = Provide[LeagueContainer.service]):
        super().__init__(intents=intents, command_prefix="b ")
        self.db = dbservice
        self.league = league_service

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return

        # Admin command to sync slash commands to current guild
        if message.content == "bran sync":
            if message.author.guild_permissions.administrator:
                guild = discord.Object(id=message.guild.id)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                await message.reply(f"Synced {len(synced)} slash commands to this guild.")
            else:
                await message.reply("Admin only.")
            return

        for command in self.commands:
            try:
                await command.process(self.get_context, message, self.db)
            except Exception as e:
                print(e)
                print(traceback.format_exc())
        if message.content.startswith("bran help"):
            await self.help(message)
        await super().on_message(message)

    async def help(self, message: discord.Message):
        output = "All commands: "
        for command in self.commands:
            if hasattr(command, 'usage'):
                if not hasattr(command, 'admin') or command.admin == message.author.id:
                    output = output + f"\n {command.usage}"
        await message.reply(output)

    async def setup_hook(self) -> None:
        # Load cogs
        broadcast_cog = BroadcastCog(self, self.db)
        await self.add_cog(broadcast_cog)

        game_monitor_cog = GameMonitorCog(self, self.league, self.db, broadcast_cog)
        await self.add_cog(game_monitor_cog)

        jackpot_cog = JackpotCog(self, self.db)
        await self.add_cog(jackpot_cog)

        economy_cog = EconomyCog(self, self.db)
        await self.add_cog(economy_cog)

        # Slash commands are synced manually with "bran sync"

        # Legacy prefix commands (to be migrated to slash commands)
        self.commands = [
            AdminAddLeague(), AdminAddBroadcast(), ViewPackCards(), AdminAddImage(), AdminAddCard(),
            Discover(),
            ViewJackpot(), Spin(loop=self.loop, dbservice=self.db, ctx=self.get_context),
            ViewMatches(), AddVote(),
            Inventory(), ViewShop(), Buy(),
            OpenPack(), ViewCard(), SelectCard(), DeleteCard(), DeleteDupeCards(), AdminAddBooster()
        ]

    async def on_ready(self):
        with self.db.Session() as session:
            all_league_users = session.query(LeagueUser).all()
            for league_user in all_league_users:
                if league_user.puuid is None and league_user.voteable is True and league_user.trackable is True:
                    try:
                        league_user.puuid = self.league.get_puuid(league_user)
                        print(f"backfilling {league_user.summoner_name} with puuid: {league_user.puuid}")
                    except Exception as e:
                        league_user.trackable = False
                        league_user.voteable = False
                        print(f"couldn't find user {league_user.summoner_name}")
            session.commit()

        for guild in self.guilds:
            self.create_guild(guild)
            self.populate_users(guild)

    def populate_users(self, guild: discord.Guild):
        with self.db.Session() as session:
            for member in guild.members:
                if session.query(User).filter(User.guild_id == str(guild.id), User.user_id == str(member.id)).count() == 0:
                    user = User()
                    user.guild_id = guild.id
                    user.user_id = member.id
                    session.add(user)
                    print("adding new user")
                else:
                    print("user already exists")
            session.commit()

    def create_guild(self, guild: discord.Guild):
        with self.db.Session() as session:
            if session.query(Guild).filter(Guild.guild_id == str(guild.id)).count() == 0:
                bank = Guild()
                bank.guild_id = guild.id
                bank.brancoins = 10
                session.add(bank)
                session.commit()
            else:
                print("guild entry already exists")


def run():
    itnent = discord.Intents.default()
    itnent.members = True
    itnent.message_content = True
    client = DiscordMonitorClient(intents=itnent)
    print(f"Debug: {Env.is_debug}")
    client.run(Env.active_discord_token)
