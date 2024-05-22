

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


class ViewPacks(BaseCommand):
    prefix = "bran packs"
    usage = prefix

    async def process(self, ctx, message: Message, dbservice: DbService):
        if not self.does_prefix_match(self.prefix, message.content):
            return
        
        with dbservice.Session() as session: 
            packs = session.query(BoosterPack).all()
            if packs is None or len(packs) == 0:
                await message.reply("can't find any packs")
                return

            embed = discord.Embed(title=f"Pack Shop!", description="", color=0xccffff)
            embed.set_author(name="Check out these boosters!", icon_url="https://i.imgur.com/L4Ps6O5.png")
            
            for pack in packs:
                embed.add_field(name="Pack", value=str(pack.id), inline=True)
                embed.add_field(name="Cost", value=str(pack.cost), inline=True)
                embed.add_field(name="Description", value=str(pack.desc), inline=True)
                embed.add_field(name="", value="", inline=False)

            embed.set_image(url="https://i.imgur.com/NifcNgd.jpeg")

            await message.reply(embed=embed)