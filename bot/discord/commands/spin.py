

from ast import Tuple
from asyncio import AbstractEventLoop
import asyncio
import itertools
import math
from typing import List
from discord import Message
import discord
import discord.ext
import discord.ext.commands
from discord.commands.jackpot import ViewJackpot
from discord.CardBonusType import CardBonusType
from models.dbcontainer import DbService
from models.models import Card, CardBonus, Guild, OwnedCard, User
from discord.basecommand import BaseCommand
import random

import reactivex as rx
from reactivex import operators as ops
from reactivex.scheduler import ThreadPoolScheduler


class Spin(BaseCommand):
    cost = 2
    wins = [(1/500, 50), (1/50, 20), (1/18, 10), (1/6, 6), (1/4, 3), (5/8, 2)]
    jackpot_chance = None
    prefix = "bran spin"
    usage = prefix
    freebie_chance = 1/100

    spin_event_stream = rx.Subject()

    def __init__(self, loop, ctx, dbservice: DbService):
        self.dbservice = dbservice
        self.loop = loop
        
        scheduler = ThreadPoolScheduler(1)
        self.spin_event_stream.pipe(
            ops.buffer_with_time(1.0)
        ).subscribe(
            on_next=self.process_spin_buff,
            on_error=print,
            on_completed=lambda: print("Completed!"),
            scheduler=scheduler
        )
    
    def process_spin_buff(self, buff: List[discord.Message]):
        for channel_id, messages in itertools.groupby(buff, lambda x: x.channel.id):
            output_strs = []
            channel = None
            for message in list(messages):
                num_rolls = self.num_rolls_to_do(self.dbservice, message.author.id)
                for x in range(num_rolls):
                    output_strs.append(self.execute_spin(message))
                channel = message.channel
            if channel:
                asyncio.run_coroutine_threadsafe(self.output_spin_results(channel, '\n------\n'.join(output_strs)), self.loop)

    async def output_spin_results(self, channel: discord.TextChannel, message: str):
        await channel.send(message)

    def num_rolls_to_do(self, dbservice: DbService, author_id: int):
        with dbservice.Session() as session: 
            bonus_rolls = session.query(CardBonus).distinct(CardBonus.id).filter(CardBonus.bonus_type == CardBonusType.SPIN_2X.value).join(Card).join(OwnedCard).join(User).filter(User.user_id == str(author_id)).count()
            if bonus_rolls > 0:
                return 1 + bonus_rolls
        return 1

    async def process(self, ctx, message: Message, dbservice: DbService):
        if not self.does_prefix_match(self.prefix, message.content):
            return
        
        # add it to the stream and get on with our day
        self.spin_event_stream.on_next(message)

        # spin in realtime, disabled
        # output_msg = self.execute_spin(message, dbservice)
        # await message.reply(output_msg)
        
    def execute_spin(self, message: Message):
        output_msg = ""
        with self.dbservice.Session() as session: 
            is_freebie = True if random.uniform(0, 1) < self.freebie_chance else False
            source = session.query(User).filter(User.user_id == str(message.author.id), User.guild_id == str(message.guild.id)).first()
            guild = session.query(Guild).filter(Guild.guild_id == str(message.guild.id)).first()

            if guild.broadcast_channel_id is not None and str(message.channel.id) != guild.broadcast_channel_id:
                return (f"<@{message.author.id}> Wrong channel, you clown :clown:")

            coin_change = 0

            if source.brancoins < self.cost:
                return (f"<@{message.author.id}> You ain't got the facilities for that big man")

            if not is_freebie:
                coin_change -= self.cost

            spin_val = random.uniform(0, 1)
            win_val = 0
            for win in self.wins:
                if spin_val < win[0]:
                    win_val = win[1]
                    break
            
            jackpot_chance_dynamic = max(200, math.ceil(ViewJackpot.upper_class_wealth(session, str(guild.guild_id)) * 0.1))
            won_jackpot = spin_val < (1/jackpot_chance_dynamic)

            jackpot_value = guild.brancoins
            if won_jackpot:
                coin_change += jackpot_value
                guild.brancoins = 0
            else:
                guild.brancoins += self.cost
                coin_change += win_val

            source.brancoins += coin_change

            if won_jackpot:
                output_msg = (f"<@{message.author.id}> :rotating_light: :rotating_light: :rotating_light: YOU WON THE JACKPOT OF {jackpot_value} {self.custom_emoji} !!!   :rotating_light: :rotating_light: :rotating_light: ")
            else:
                if not is_freebie:
                    if win_val == 0:
                        output_msg = (f"<@{message.author.id}> Paid {self.cost} {self.custom_emoji} ...\nWon nothing... dummy... :clown:")
                    else:
                        output_msg = (f"<@{message.author.id}> Paid {self.cost} {self.custom_emoji} ...\nWon {win_val}!!!!:maracas:")
                else:
                    if win_val == 0:
                        output_msg = (f"<@{message.author.id}> Paid nothing!!! Fames Jermo has blessed you! ...\nWon nothing... it looks like this blessing is a toxic curse... :cursed:")
                    else:
                        output_msg = (f"<@{message.author.id}> Paid nothing!!! Farhan smiles upon you!!\nWon {win_val}!!!! Time to convert!!!!:maracas: <:Prayge:1038601127052193814> :maracas:")

            session.add(guild)
            session.add(source)
            session.commit()
        return output_msg
            