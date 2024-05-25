

from asyncio import Semaphore
import asyncio
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
from models.models import BoosterCard, BoosterPack, BoosterSegment, Card, Guild, OwnedCard, Shop, User
from discord.basecommand import BaseCommand
import random

class OpenPack(BaseCommand):
    prefix = "bran buypack"
    usage = prefix + " [pack_name]"

    async def process(self, ctx, message: Message, dbservice: DbService):
        if not self.does_prefix_match(self.prefix, message.content):
            return
        
        command_breakdown = message.content.split()
        pack_name = str(command_breakdown[2]) 
        with dbservice.Session() as session: 
            user = session.query(User).filter(User.user_id == str(message.author.id), User.guild_id == str(message.guild.id)).first()
            pack = session.query(BoosterPack).filter(BoosterPack.id == pack_name).first()
            if pack is None:
                await message.reply("can't find pack with that name")
                return

            if user.brancoins < pack.cost:
                await message.reply("You broke son")
                return
            
            drawn_card_segments = self.draw_cards_from_pack(pack)
            for drawn_card_segment in drawn_card_segments:
                for drawn_card in drawn_card_segment[1]:
                    owned_card = OwnedCard()
                    owned_card.card = drawn_card
                    user.owned_cards.append(owned_card)

            user.brancoins -= pack.cost

            session.add(user)
            session.commit()

            
            await message.reply(f"Opening a {pack_name} pack!")
            for drawn_card_segment in drawn_card_segments:
                files = self.display_segment(drawn_card_segment[0], drawn_card_segment[1])
                await asyncio.sleep(3)
                await message.reply(f"Looks like we have some {drawn_card_segment[0].id} cards...", files=files)

            await message.reply(f"Congrats on the new cards!")

    def display_segment(self, segment: BoosterSegment, cards: List[Card]):
        bg = "boostermat.jpeg" if segment.bg_fname == None else segment.bg_fname
        return self.card_spread(cards, bg)

    def card_spread(self, cards, bg):
        card_pages: List[List[Card]] = self.split(cards, 6)
        discord_files: List[discord.File] = []
        for idx, card_page in enumerate(card_pages):      
            grid = (len(card_page), 1)
            inv_img = DrawUtils.draw_inv_card_spread(card_page,  (1400, 400), grid, draw_blanks=True, bg=bg)
            buffered = BytesIO()
            inv_img.save(buffered, format="PNG")
            discord_files.append(discord.File(BytesIO(buffered.getvalue()), filename=f"page{idx}.png"))
        return discord_files
        
    def draw_cards_from_pack(self, pack: BoosterPack) -> List[tuple[BoosterSegment, List[Card]]]:
        drawn_cards: List[tuple[BoosterSegment, List[Card]]] = []
        for segment in pack.booster_segments:
            weights = []
            cards = []
            for booster_card in segment.booster_cards:
                weights.append(booster_card.chance)
                cards.append(booster_card.card)
            if len(cards) > 0 and len(weights) > 0 and len(cards) == len(weights):
                drawn_cards.append((segment, random.choices(cards, weights, k=segment.num_cards_to_draw)))
        return drawn_cards
    
    def split(self, arr, size):
        return [arr[i:i+size] for i in range(0,len(arr),size)]
