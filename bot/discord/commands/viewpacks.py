

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
from sqlalchemy import func
from discord.drawutils import DrawUtils
from models.dbcontainer import DbService
from models.models import BoosterCard, BoosterPack, BoosterSegment, Card, Guild, OwnedCard, Shop, User
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
            
            source = session.query(User).filter(User.user_id == str(message.author.id), User.guild_id == str(message.guild.id)).first()
            owned_card_ids = [x.card_id for x in source.owned_cards]
            missing_cards_text = []
            for pack in packs:
                distinct_cards_in_pack = session.query((func.distinct(BoosterCard.card_id))).filter(BoosterCard.booster_pack_id == pack.id).all()
                distinct_card_ids = [x.tuple()[0] for x in distinct_cards_in_pack]
                missing_card_ids = [x for x in distinct_card_ids if x not in owned_card_ids]
                missing_cards_text.append(f"\nYou're missing {len(missing_card_ids)} cards from this pack!")

            embed = discord.Embed(title=f"Pack Shop!", description="", color=0xccffff)
            embed.set_author(name="Check out these boosters!", icon_url="https://i.imgur.com/L4Ps6O5.png")
            
            for idx, pack in enumerate(packs):
                embed.add_field(name="Pack", value=str(pack.id), inline=True)
                embed.add_field(name="Cost", value=str(pack.cost), inline=True)
                embed.add_field(name="Description", value=f"{str(pack.desc)} {missing_cards_text[idx]}" , inline=True)
                embed.add_field(name="", value="", inline=False)

            embed.set_image(url="https://i.imgur.com/NifcNgd.jpeg")

            await message.reply(embed=embed)