

from re import A
from discord import Message
import discord
from models.dbcontainer import DbService
from models.models import LeagueUser, User
from discord.basecommand import BaseCommand
from discord.ext.commands import Bot
from dependency_injector.wiring import Provide, inject
from league.leagueservice import LeagueService
from league.leaguecontainer import LeagueContainer


class AdminAddLeague(BaseCommand):
    prefix = "bran add"
    usage = prefix + " [league_name] [league_tag] [discord_at] [t_val=True/False] [v_val=True/False]"
    admin = 114930910884790276

    def __init__(self, league_service: LeagueService = Provide[LeagueContainer.service]):
        self.league_service = league_service

    async def process(self, ctx, message: Message, dbservice: DbService):
        if not self.does_prefix_match(self.prefix, message.content):
            return
        
        if message.author.id != self.admin:
            await message.reply("Unauthorized")
            return

        try:
            tagged_user = message.mentions[0]
        except:
            await message.reply("Who?")
            return
        
        command_breakdown = message.content.split()
        print(command_breakdown)
        league_name = None
        try:
            league_name = str(command_breakdown[2]) 
        except:
            await message.reply("League name???")
            return
        
        league_tag = None
        try:
            league_tag = str(command_breakdown[3]) 
        except:
            await message.reply("League tag???")
            return
        
        tracking = False
        try:
            tracking = str(command_breakdown[5]) == "True"
        except:
            await message.reply("t val???")
            return
        
        voting = False
        try:
            voting = str(command_breakdown[6]) == "True"
        except:
            await message.reply("v val???")
            return



        with dbservice.Session() as session: 
            target_user_account = session.query(User).filter(User.guild_id==str(message.guild.id), User.user_id == str(tagged_user.id)).first()
            league_entry = LeagueUser()
            league_entry.discord_user = target_user_account
            league_entry.summoner_name = league_name
            league_entry.tag = league_tag
            league_entry.trackable = tracking
            league_entry.voteable = voting

            puuid = self.league_service.get_puuid(league_entry)
            if puuid:
                league_entry.puuid = puuid
            else:
                await message.reply("No puuid found")
                return

            session.add(league_entry)
            session.commit()
            
            await message.reply("donezo")