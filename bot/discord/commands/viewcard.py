

from io import BytesIO
import math
from typing import List
from discord import Message
import discord
from sqlalchemy import text
from discord.drawutils import DrawUtils
from models.dbcontainer import DbService
from models.models import Card, OwnedCard, User
from discord.basecommand import BaseCommand
from PIL import Image


class ViewCard(BaseCommand):
    prefix = "bran viewcard"
    usage = prefix + " [1/2/3/'some title'/'some desc']"
    async def process(self, ctx, message: Message, dbservice: DbService):
        if not self.does_prefix_match(self.prefix, message.content):
            return
        
        command_breakdown = message.content.split()

        selected_card = None
        if self.represents_int(command_breakdown[2]):
            card_idx = int(command_breakdown[2]) - 1
            with dbservice.Session() as session: 
                guy = session.query(User).filter(User.user_id == str(message.author.id), User.guild_id == str(message.guild.id)).first()
                if guy and card_idx < len(guy.owned_cards):
                    card = guy.owned_cards[card_idx].card
                    file = discord.File(DrawUtils.card_to_byte_image(card), filename=f"card.png")
                    await message.reply(f"Behold! I'll activate {card.title}!!!", file=file)
                else:
                    await message.reply("???")
        else :
            with dbservice.Session() as session: 
                guy = session.query(User).filter(User.user_id == str(message.author.id), User.guild_id == str(message.guild.id)).first()
                card = ViewCard.find_card_by_text(session, guy, message.content.removeprefix(self.prefix)).card
                if card is not None:
                    file = discord.File(DrawUtils.card_to_byte_image(card), filename=f"card.png")
                    await message.reply(f"Behold! I'll activate {card.title}!!!", file=file)
                else:
                    await message.reply("???")

    @staticmethod
    def find_card_by_text(session, owner: User, search_text: str):
        query_text = text(
            "Select ownedcards.id, cards.cost, similarity(cards.title, :str_search) as sim from ownedcards inner join cards on ownedcards.card_id = cards.id where ownedcards.owner_id = :ownerid "
            "UNION ALL "
            "Select ownedcards.id, cards.cost, similarity(cards.description, :str_search) as sim from ownedcards inner join cards on ownedcards.card_id = cards.id where ownedcards.owner_id = :ownerid "
            "order by sim desc, cost asc ")
        closest_owned_card = session.execute(query_text, {"ownerid": owner.id, "str_search": search_text}).first()
        owned_card = session.query(OwnedCard).join(Card, OwnedCard.card).filter(OwnedCard.id == closest_owned_card[0]).first()
        return owned_card

    def split(self, arr, size):
        return [arr[i:i+size] for i in range(0,len(arr),size)]
    
    def represents_int(self, s):
        try: 
            int(s)
        except ValueError:
            return False
        else:
            return True