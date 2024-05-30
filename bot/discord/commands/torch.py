

from io import BytesIO
import math
from typing import List
from discord import Message
import discord
from discord.drawutils import DrawUtils
from models.dbcontainer import DbService
from models.models import Card, OwnedCard, User
from discord.basecommand import BaseCommand
from PIL import Image


class DeleteCard(BaseCommand):
    prefix = "bran torch"
    usage = prefix + " [1,2,3]"
    async def process(self, ctx, message: Message, dbservice: DbService):
        if not self.does_prefix_match(self.prefix, message.content):
            return
        
        command_breakdown = message.content.split()
        card_idx = int(command_breakdown[2]) - 1
        
        with dbservice.Session() as session: 
            guy = session.query(User).filter(User.user_id == str(message.author.id), User.guild_id == str(message.guild.id)).first()
            if guy and card_idx < len(guy.owned_cards):
                owned_card = guy.owned_cards[card_idx]
                value = owned_card.card.cost
                title = owned_card.card.title
                guy.brancoins += math.ceil(value/6)
                session.query(OwnedCard).filter(OwnedCard.id == owned_card.id).delete()
                session.add(guy)
                session.commit()
                await message.reply(f"{title} has been sent to the shadow realm!!! {math.ceil(value/6)}{self.custom_emoji} restored. \n**card inventory indexes have changed, be careful when deleting in a chain**")
            else:
                await message.reply("???")
