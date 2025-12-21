import discord
from discord.ext import commands

from models.models import Guild
from models.dbcontainer import DbService

class BroadcastCog(commands.Cog):
    """Shared broadcasting utility for sending messages to all configured guilds."""

    def __init__(self, bot, db_service: DbService):
        self.bot = bot
        self.db = db_service

    async def broadcast_all(self, embed: discord.Embed):
        """Broadcast an embed to all guilds with a configured broadcast channel."""
        with self.db.Session() as session:
            guilds = session.query(Guild).filter(Guild.broadcast_channel_id != None).all()
            for guild in guilds:
                broadcast_channel = await self.bot.fetch_channel(guild.broadcast_channel_id)
                await broadcast_channel.send(embed=embed)

    async def broadcast_all_str(self, msg: str):
        """Broadcast a string message to all guilds with a configured broadcast channel."""
        with self.db.Session() as session:
            guilds = session.query(Guild).filter(Guild.broadcast_channel_id != None).all()
            for guild in guilds:
                broadcast_channel = await self.bot.fetch_channel(guild.broadcast_channel_id)
                message = msg
                if guild.broadcast_role_id is not None:
                    disc_guild_obj = await self.bot.fetch_guild(guild.guild_id)
                    disc_roles = await disc_guild_obj.fetch_roles()
                    disc_role: discord.Role = discord.utils.get(disc_roles, id=int(guild.broadcast_role_id))
                    message += f"\n{disc_role.mention}"
                await broadcast_channel.send(message)
