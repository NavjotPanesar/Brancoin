

from io import BytesIO
import math
from typing import List
from discord import Message
import discord
from discord.commands.viewcard import ViewCard
from discord.drawutils import DrawUtils
from models.dbcontainer import DbService
from models.models import Card, User
from discord.basecommand import BaseCommand
from PIL import Image


class SelectCard(BaseCommand):
    prefix = "bran summon"
    usage = prefix + " [1/2/3/'some title'/'some desc']"
    async def process(self, ctx, message: Message, dbservice: DbService):
        if not self.does_prefix_match(self.prefix, message.content):
            return
        
        command_breakdown = message.content.split()
        
        with dbservice.Session() as session: 
            guy = session.query(User).filter(User.user_id == str(message.author.id), User.guild_id == str(message.guild.id)).first()
            
            selected_card = None
            if self.represents_int(command_breakdown[2]):
                card_idx = int(command_breakdown[2]) - 1
                if guy and card_idx < len(guy.owned_cards):
                    selected_card = guy.owned_cards[card_idx].card
            else:
                selected_card = ViewCard.find_card_by_text(session, guy, message.content.removeprefix(self.prefix)).card

            if selected_card is not None:
                file = discord.File(DrawUtils.summon(selected_card), filename=f"summon.gif")
                await message.reply(f"Behold! I'll activate {selected_card.title}!!!", file=file)
            else:
                await message.reply("???")

    def split(self, arr, size):
        return [arr[i:i+size] for i in range(0,len(arr),size)]
    
    def represents_int(self, s):
        try: 
            int(s)
        except ValueError:
            return False
        else:
            return True