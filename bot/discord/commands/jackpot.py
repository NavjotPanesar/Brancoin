

from discord import Message
import discord
from models.dbcontainer import DbService
from models.models import Guild, Match, User
from discord.basecommand import BaseCommand
from discord.ext.commands import Bot


class ViewJackpot(BaseCommand):
    prefix = "bran jackpot"
    usage = prefix
    async def process(self, ctx, message: Message, dbservice: DbService):
        if not self.does_prefix_match(self.prefix, message.content):
            return
        
        with dbservice.Session() as session: 
            guild = session.query(Guild).filter(Guild.guild_id == str(message.guild.id)).first()
            await message.reply(f"Jackpot is currently {guild.brancoins} {self.custom_emoji}")