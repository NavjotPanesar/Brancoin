import discord
from discord.ext import commands
from dependency_injector.wiring import Provide, inject
from models.models import Guild, LeagueUser, User
from models.dbcontainer import DbContainer, DbService
from league.leagueservice import LeagueService
from league.leaguecontainer import LeagueContainer
from envvars import Env
from discord.cogs import (
    EconomyCog,
    GamblingCog,
    CardsCog,
    ShopCog,
    PacksCog,
    AdminCog,
    GameMonitorCog,
    JackpotCog,
)


@inject
class DiscordMonitorClient(commands.Bot):
    @inject
    def __init__(
        self,
        intents,
        dbservice: DbService = Provide[DbContainer.service],
        league_service: LeagueService = Provide[LeagueContainer.service]
    ):
        super().__init__(intents=intents, command_prefix="bran ")
        self.db = dbservice
        self.league = league_service

    async def setup_hook(self) -> None:
        # Add all cogs
        await self.add_cog(EconomyCog(self, self.db))
        await self.add_cog(GamblingCog(self, self.db))
        await self.add_cog(CardsCog(self, self.db))
        await self.add_cog(ShopCog(self, self.db))
        await self.add_cog(PacksCog(self, self.db))
        await self.add_cog(AdminCog(self, self.db, self.league))
        await self.add_cog(GameMonitorCog(self, self.db, self.league))
        await self.add_cog(JackpotCog(self, self.db))

        # Sync slash commands to Discord
        # For development, you can sync to a specific guild for instant updates:
        # guild = discord.Object(id=YOUR_GUILD_ID)
        # self.tree.copy_global_to(guild=guild)
        # await self.tree.sync(guild=guild)

        # For production, sync globally (takes up to 1 hour to propagate):
        await self.tree.sync()
        print("Slash commands synced")

    async def on_ready(self):
        print(f"Logged in as {self.user}")

        # Backfill PUUIDs for league users
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

        # Ensure guilds and users are in database
        for guild in self.guilds:
            self._create_guild(guild)
            self._populate_users(guild)

    def _populate_users(self, guild: discord.Guild):
        """Ensure all guild members exist in the database."""
        with self.db.Session() as session:
            for member in guild.members:
                if session.query(User).filter(
                    User.guild_id == str(guild.id),
                    User.user_id == str(member.id)
                ).count() == 0:
                    user = User()
                    user.guild_id = guild.id
                    user.user_id = member.id
                    session.add(user)
                    print("adding new user")
            session.commit()

    def _create_guild(self, guild: discord.Guild):
        """Ensure guild exists in the database."""
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
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    client = DiscordMonitorClient(intents=intents)
    print(f"Debug: {Env.is_debug}")
    client.run(Env.active_discord_token)
