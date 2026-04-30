from discord.ext import commands
from models.dbcontainer import DbService
from models.models import User
from envvars import Env


class BaseCog(commands.Cog):
    """Base cog with shared utilities for all Brancoin cogs."""

    custom_emoji = "<:brancoin:1233204357550575636>" if Env.is_debug == "false" else "<:test:1230694305937756160>"

    def __init__(self, bot: commands.Bot, db_service: DbService):
        self.bot = bot
        self.db = db_service

    def get_user(self, session, user_id: str, guild_id: str) -> User | None:
        """Get a User from the database by Discord IDs."""
        return session.query(User).filter(
            User.user_id == user_id,
            User.guild_id == guild_id
        ).first()
