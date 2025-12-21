import shlex
from discord import Message
import discord
from models.dbcontainer import DbService
from discord.basecommand import BaseCommand

class AdminSync(BaseCommand):
    prefix = "bran sync"
    usage = prefix
    admin = 114930910884790276
    async def process(self, ctx, message: Message, dbservice: DbService):
        if not self.does_prefix_match(self.prefix, message.content):
            return
        
        if message.author.id != self.admin:
            await message.reply("Unauthorized")
            return

        guild = discord.Object(id=message.guild.id)
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        await message.reply(f"Synced {len(synced)} slash commands to this guild.")
