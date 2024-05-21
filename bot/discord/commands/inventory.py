

from io import BytesIO
import math
from typing import List
from discord import Message
import discord
from discord.drawutils import DrawUtils
from models.dbcontainer import DbService
from models.models import Card, User
from discord.basecommand import BaseCommand
from PIL import Image


class Inventory(BaseCommand):
    prefix = "bran inv"
    usage = prefix
    async def process(self, ctx, message: Message, dbservice: DbService):
        if not self.does_prefix_match(self.prefix, message.content):
            return
        
        with dbservice.Session() as session: 
            guy = session.query(User).filter(User.user_id == str(message.author.id), User.guild_id == str(message.guild.id)).first()
            if guy:
                cards = []
                for owned_card in guy.owned_cards:
                    cards.append(owned_card.card)
                
                if(len(cards) <= 0):
                    await message.reply("No cards")
                    return

                max_x = 6
                max_y = 4
                card_pages: List[List[Card]] = self.split(cards, max_x*max_y)
                discord_files: List[discord.File] = []
                for idx, card_page in enumerate(card_pages):      
                    img_size = (1600, 1200)
                    grid = (max_x,max_y)
                    if len(card_page) <= max_x*1:
                        grid = (math.ceil(len(card_page)/1), 1)
                    elif len(card_page) <= max_x*2: 
                        grid = (math.ceil(len(card_page)/2), 2)
                    elif len(card_page) <= max_x*3: 
                        grid = (math.ceil(len(card_page)/3), 3)
                    else : 
                        grid = (math.ceil(len(card_page)/4), 4)
                        img_size = (1600, 1600)
                    print(img_size)
                    inv_img = DrawUtils.draw_inv_card_spread(card_page, img_size , grid, True)
                    buffered = BytesIO()
                    inv_img.save(buffered, format="PNG")
                    discord_files.append(discord.File(BytesIO(buffered.getvalue()), filename=f"page{idx}.png"))
                await message.reply(f"Inventory:", files=discord_files)
            else:
                await message.reply("Who are you?")

    def split(self, arr, size):
        return [arr[i:i+size] for i in range(0,len(arr),size)]