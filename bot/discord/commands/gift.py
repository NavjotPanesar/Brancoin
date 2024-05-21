

from discord import Message
import discord
import discord.ext
import discord.ext.commands
from models.dbcontainer import DbService
from models.models import User
from discord.basecommand import BaseCommand
import random


class Gift(BaseCommand):
    freebie_chance = 1/30
    prefix = "bran gift"
    usage = f"{prefix} [user] [num]"
    async def process(self, ctx, message: Message, dbservice: DbService):
        if not self.does_prefix_match(self.prefix, message.content):
            return
        command_breakdown = message.content.split()
        try:
            tagged_user = message.mentions[0]
        except:
            await message.reply("Who?")
            return
        
        is_freebie = True if random.uniform(0, 1) < self.freebie_chance else False

        try:
            num = int(command_breakdown[3]) 
            if num <= 0:
                return
        except:
            await message.reply("How many coin???")
            return
        
        with dbservice.Session() as session: 
            source = session.query(User).filter(User.user_id == str(message.author.id), User.guild_id == str(message.guild.id)).first()
            dest = session.query(User).filter(User.user_id == str(tagged_user.id), User.guild_id == str(message.guild.id)).first()

            if source.brancoins < num:
                await message.reply("You ain't got the facilities for that big man")
                return

            if not is_freebie:
                source.brancoins -= num
            dest.brancoins += num
            session.add(source)
            session.add(dest)
            session.commit()
            
            if not is_freebie:
                await message.reply(f"Transfered {num} {self.custom_emoji} to {tagged_user.mention}")
            else:
                await message.reply(f"Transfered {num} {self.custom_emoji} to {tagged_user.mention}\nThe great Vivian Octave smiles upon you!!!\n :maracas::maracas: This gift will be granted for free! :maracas: :maracas:")
            