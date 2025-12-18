

import shlex
from discord import Message
import discord
from discord.drawutils import DrawUtils
from models.dbcontainer import DbService
from models.models import Card, Guild, Image
from discord.basecommand import BaseCommand

class AdminAddCard(BaseCommand):
    prefix = "bran addcard"
    usage = prefix + ' [save=True/False] [title="Title"] [description="desc"] [level] [atk] [defe] [card_style=normal] [attribute=Earth] [type="Monster/Cool"] [image_label] [cost] [shoppable = True/False]' 
    admin = 114930910884790276
    async def process(self, ctx, message: Message, dbservice: DbService):
        if not self.does_prefix_match(self.prefix, message.content):
            return
        
        if message.author.id != self.admin:
            await message.reply("Unauthorized")
            return
        

        command_breakdown = shlex.split(message.content)
        save = bool(command_breakdown[2] == "True")

        card = Card()
        card.title = str(command_breakdown[3]).replace("\"","")
        card.description = str(command_breakdown[4]).replace("\"","")
        card.level = str(command_breakdown[5])
        card.atk = "" if command_breakdown[6] == "0" else str(command_breakdown[6])
        card.defe = "" if command_breakdown[7] == "0" else str(command_breakdown[7])
        card.card_style = str(command_breakdown[8])
        card.attribute = str(command_breakdown[9])
        card.type = str(command_breakdown[10]).replace("\"","")
        card.image_label = str(command_breakdown[11])
        card.cost = int(command_breakdown[12])
        card.shoppable = bool(command_breakdown[13] == "True")

        if save:
            with dbservice.Session() as session: 
                session.add(card)
                session.commit()
                await message.reply(f"done {card.id}")
        else:
            with dbservice.Session() as session: 
                card.image = session.query(Image).filter(Image.label == card.image_label).first()
            await message.reply(file=discord.File(DrawUtils.card_to_byte_image(card), filename="preview.png"))
            