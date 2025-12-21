import math
import traceback

from discord.ext import commands

from discord.repeattimer import RepeatTimer
from discord.commands.jackpot import ViewJackpot
from models.models import Guild
from models.dbcontainer import DbService


class JackpotCog(commands.Cog):
    """Manages the jackpot trickle that periodically increases guild jackpots."""

    def __init__(self, bot, db_service: DbService):
        self.bot = bot
        self.db = db_service

        self.trickle_timer = RepeatTimer(60 * 60, self.jackpot_trickle)
        self.trickle_timer.start()

    def cog_unload(self):
        """Clean up timer when cog is unloaded."""
        self.trickle_timer.cancel()

    def jackpot_trickle(self):
        """Periodically increase jackpot for guilds below the soft cap."""
        try:
            print("trickle")
            with self.db.Session() as session:
                guilds = session.query(Guild).all()
                for guild in guilds:
                    jackpot_soft_cap = math.ceil(ViewJackpot.upper_class_wealth(session, str(guild.guild_id)) * 0.1)
                    if guild.brancoins < jackpot_soft_cap:
                        guild.brancoins += math.ceil(jackpot_soft_cap * 0.08)
                        session.add(guild)
                session.commit()
        except Exception as e:
            print(e)
            print(traceback.format_exc())
