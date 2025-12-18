
import shlex
from discord import Message
from models.dbcontainer import DbService
from models.models import BoosterCard, BoosterSegment, Card, Guild, Image
from discord.basecommand import BaseCommand

class AdminAddBooster(BaseCommand):
    prefix = "bran addbooster"
    usage = prefix + " \"pack\" \"segment\" card_id chance \n bran addbooster ls"
    admin = 114930910884790276
    async def process(self, ctx, message: Message, dbservice: DbService):
        if not self.does_prefix_match(self.prefix, message.content):
            return
        
        if message.author.id != self.admin:
            await message.reply("Unauthorized")
            return
        
        command_breakdown = shlex.split(message.content)

        if "ls" in command_breakdown[2].lower():
            with dbservice.Session() as session: 
                segments = session.query(BoosterSegment).all()
                output = ""
                for segment in segments:
                    output = output + segment.booster_pack_id + ":" + segment.id +  "\n"
                await message.reply(output)
            return
        
        pack = str(command_breakdown[2]).replace("\"","")
        seg = str(command_breakdown[3]).replace("\"","")
        card_id = int(command_breakdown[4])
        chance = int(command_breakdown[5])

        booster_card = BoosterCard()
        booster_card.booster_pack_id = pack
        booster_card.booster_segment_id = seg
        booster_card.chance = chance

        with dbservice.Session() as session: 
            card = session.query(Card).filter(Card.id == card_id).first()
            if not card:
                await message.reply("Card not found")
                return
            booster_card.card = card
            session.add(booster_card)
            session.commit()
            await message.reply("done")