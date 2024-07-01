

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


class DeleteDupeCards(BaseCommand):
    prefix = "bran torchdupes"
    usage = prefix
    async def process(self, ctx, message: Message, dbservice: DbService):
        if not self.does_prefix_match(self.prefix, message.content):
            return
        
        with dbservice.Session() as session: 
            guy = session.query(User).filter(User.user_id == str(message.author.id), User.guild_id == str(message.guild.id)).first()
            if guy:
                query_text = text(
                    "select id FROM "
                    "( "
                        "select ownedcards.card_id, min(ownedcards.id) as saved_id "
                        "from ownedcards "
                        "where owner_id=:ownerid "
                        "group by ownedcards.card_id having count(*) > 1 "
                    ") as dupes_to_keep "
                    "INNER JOIN " 
                    "ownedcards "
                    "on ownedcards.card_id = dupes_to_keep.card_id "
                    "where ownedcards.id > dupes_to_keep.saved_id AND owner_id=:ownerid limit 10"
                )
                dupe_owned_card_ids = session.execute(query_text, {"ownerid": guy.id}).scalars()
                outputs = []
                for dupe_owned_card_id in dupe_owned_card_ids:
                    dupe_owned_card = session.query(OwnedCard).filter(OwnedCard.id == dupe_owned_card_id).first()
                    value = dupe_owned_card.card.cost
                    title = dupe_owned_card.card.title
                    guy.brancoins += math.ceil(value/6)
                    session.add(guy)
                    session.query(OwnedCard).filter(OwnedCard.id == dupe_owned_card_id).delete()
                    outputs.append(f"{title} for {math.ceil(value/6)}{self.custom_emoji}")
                output = ','.join(outputs)
                await message.reply(f"torching: {output}")
                session.commit()
            else:
                await message.reply("???")
