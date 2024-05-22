

import datetime
from io import BytesIO
import PIL
from discord import Message
import discord
import discord.ext
import discord.ext.commands
from models.dbcontainer import DbService
from models.models import Card, Guild, OwnedCard, Shop, User
from discord.basecommand import BaseCommand
import random


class Buy(BaseCommand):
    prefix = "bran buy"
    usage = prefix + " [1/2/3/4]"

    async def process(self, ctx, message: Message, dbservice: DbService):
        if not self.does_prefix_match(self.prefix, message.content):
            return
        
        command_breakdown = message.content.split()
        shop_idx = int(command_breakdown[2]) 
        with dbservice.Session() as session: 
            source = session.query(User).filter(User.user_id == str(message.author.id), User.guild_id == str(message.guild.id)).first()
            shop = session.query(Shop).join(Card, Shop.card).filter(Shop.date_added == datetime.date.today()).order_by(Card.cost.asc(), Card.id.asc()).limit(4).all()
            selected_shop_item: Shop = shop[shop_idx - 1]

            if source.brancoins < selected_shop_item.card.cost:
                await message.reply("You broke son")

            ownedcard = OwnedCard()
            ownedcard.card = selected_shop_item.card
            source.owned_cards.append(ownedcard)
            source.brancoins -= selected_shop_item.card.cost
            session.add(source)
            
            session.commit()

            await message.reply(f"Congrats on the new card! {self.custom_emoji}")
        
        
            