

from asyncio import Semaphore
import datetime
from io import BytesIO
import math
from typing import List
import PIL
from discord import Message
import discord
import discord.ext
import discord.ext.commands
from discord.drawutils import DrawUtils
from models.dbcontainer import DbService
from models.models import BoosterCard, BoosterPack, Card, Guild, OwnedCard, Shop, User
from discord.basecommand import BaseCommand
import random


class ViewPackCards(BaseCommand):
    prefix = "bran viewpack"
    usage = prefix + " [pack_name]"
    admin = 114930910884790276

    async def process(self, ctx, message: Message, dbservice: DbService):
        if not self.does_prefix_match(self.prefix, message.content):
            return
        
        if message.author.id != self.admin:
            await message.reply("Unauthorized")
            return
        
        command_breakdown = message.content.split()
        pack_name = str(command_breakdown[2]) 
        with dbservice.Session() as session: 
            pack = session.query(BoosterPack).filter(BoosterPack.id == pack_name).first()
            if pack is None:
                await message.reply("can't find pack")
                return
            
            print_cards = []
            for segment in pack.booster_segments:
                for card in segment.booster_cards:
                    print_cards.append(card.card)

            grid = (math.ceil(math.sqrt(len(print_cards))), math.ceil(math.sqrt(len(print_cards))))
            inv_img = await DrawUtils.draw_inv_card_spread(print_cards,  (1000, 1000), grid, draw_blanks=True)
            buffered = BytesIO()
            inv_img.save(buffered, format="PNG")
            discord_file = discord.File(BytesIO(buffered.getvalue()), filename=f"previewpack.png")
            await message.reply(file=discord_file)