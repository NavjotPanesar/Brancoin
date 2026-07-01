import math
import traceback
from discord.ext import commands, tasks
from models.dbcontainer import DbService
from models.models import Guild
from botclient.helpers.economy_utils import upper_class_wealth
from .base_cog import BaseCog


class JackpotCog(BaseCog):
    """Background task for jackpot trickle (periodic coin increases)."""

    async def cog_load(self):
        """Start background task when cog is loaded."""
        self.jackpot_trickle.start()

    async def cog_unload(self):
        """Stop background task when cog is unloaded."""
        self.jackpot_trickle.cancel()

    @tasks.loop(hours=1)
    async def jackpot_trickle(self):
        """Periodically increase jackpot based on top players' wealth."""
        try:
            with self.db.Session() as session:
                guilds = session.query(Guild).all()
                for guild in guilds:
                    jackpot_soft_cap = math.ceil(
                        upper_class_wealth(session, str(guild.guild_id)) * 0.1
                    )
                    if guild.brancoins < jackpot_soft_cap:
                        guild.brancoins += math.ceil(jackpot_soft_cap * 0.08)
                        session.add(guild)
                session.commit()
        except Exception as e:
            print(e)
            print(traceback.format_exc())

    @jackpot_trickle.before_loop
    async def before_jackpot_trickle(self):
        """Wait until bot is ready before starting task."""
        await self.bot.wait_until_ready()
