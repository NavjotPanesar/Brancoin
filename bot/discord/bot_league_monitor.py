from datetime import datetime
import dis
from functools import partial, wraps
import math
import random
from sys import prefix
from threading import Thread
import threading
import discord
import asyncio
import discord.ext
import discord.ext.commands
import sqlalchemy

from discord.commands.torchdupes import DeleteDupeCards
from discord.commands.torch import DeleteCard
from discord.commands.viewcard import ViewCard
from discord.commands.viewpackcards import ViewPackCards
from discord.commands.openpack import OpenPack
from discord.commands.addcard import AdminAddCard
from discord.commands.addimage import AdminAddImage
from discord.commands.selectcard import SelectCard
from discord.commands.inventory import Inventory
from discord.commands.buy import Buy
from discord.commands.viewshop import ViewShop
from discord.commands.beg import Beg
from discord.commands.vote import AddVote
from discord.VoteType import VoteType
from discord.commands.addbroadcast import AdminAddBroadcast
from discord.repeattimer import RepeatTimer
from discord.commands.addleague import AdminAddLeague
from discord.commands.jackpot import ViewJackpot
from discord.commands.viewmatches import ViewMatches
from discord.commands.coins import Coins
from discord.commands.spin import Spin
from discord.commands.gift import Gift
from discord.commands.coin import Coin
from models.models import Guild, LeagueUser, MatchPlayer, User, Match
from discord.commands.discover import Discover
from league.leaguecontainer import LeagueContainer
from models.dbcontainer import DbContainer, DbService
from league.leagueservice import LeagueService
from dependency_injector.wiring import Provide, inject
from envvars import Env
from discord.ext import commands
import traceback

@inject
class DiscordMonitorClient(commands.Bot):
    commands = []
    @inject
    def __init__(self, intents, dbservice: DbService = Provide[DbContainer.service], league_service: LeagueService = Provide[LeagueContainer.service]):
        super().__init__(intents=intents, command_prefix="b ")
        self.db = dbservice
        self.league = league_service

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return
        for command in self.commands:
            try:
                await command.process(self.get_context, message, self.db)
            except Exception as e: 
                print(e)
                print(traceback.format_exc())
        if message.content.startswith("bran help"):
            await self.help(message)
        await super().on_message(message)

    async def help(self, message: discord.Message):
        output = "All commands: "
        for command in self.commands:
            if hasattr(command, 'usage'):
                if not hasattr(command, 'admin') or command.admin == message.author.id:
                    output = output + f"\n {command.usage}"
        await message.reply(output)

    async def setup_hook(self) -> None:
        open_game_timer = RepeatTimer(30, self.look_for_open_games)
        open_game_timer.start()
        
        closed_game_timer = RepeatTimer(60, self.handle_finished_games)
        closed_game_timer.start()

        jackpot_trickle_timer = RepeatTimer(60*60, self.jackpot_trickle)
        jackpot_trickle_timer.start()

        self.commands = [AdminAddLeague(), AdminAddBroadcast(),ViewPackCards(), AdminAddImage(), AdminAddCard(),
                Discover(), 
                Coin(), Gift(), Coins(), ViewJackpot(), Beg(), Spin(loop=self.loop, dbservice=self.db, ctx=self.get_context),
                ViewMatches(), AddVote(), 
                Inventory(), ViewShop(), Buy(),
                OpenPack(), ViewCard(), SelectCard(), DeleteCard(), DeleteDupeCards()]

    async def on_ready(self):
        for guild in self.guilds:
            self.create_guild(guild)
            self.populate_users(guild)

    def populate_users(self, guild: discord.Guild):
        with self.db.Session() as session:
            for member in guild.members:
                if session.query(User).filter(User.guild_id == str(guild.id), User.user_id == str(member.id)).count() == 0:
                    user = User()
                    user.guild_id = guild.id
                    user.user_id = member.id
                    session.add(user)
                    print("adding new user")
                else:
                    print("user already exists")
            session.commit()


    def create_guild(self, guild: discord.Guild):
        with self.db.Session() as session:
            if session.query(Guild).filter(Guild.guild_id == str(guild.id)).count() == 0:
                bank = Guild()
                bank.guild_id = guild.id
                bank.brancoins = 10
                session.add(bank)
                session.commit()
            else:
                print("guild entry already exists")

    def jackpot_trickle(self):
        try:
            print("trickle")
            with self.db.Session() as session: 
                guilds = session.query(Guild).all()
                for guild in guilds:
                    jackpot_soft_cap = math.ceil(ViewJackpot.upper_class_wealth(session, str(guild.guild_id)) * 0.1)
                    if guild.brancoins < jackpot_soft_cap:
                        guild.brancoins += math.ceil(jackpot_soft_cap * 0.08)
                        session.add(guild)
                session.commit()
        except Exception as e: 
            print(e)
            print(traceback.format_exc())
    
    def handle_finished_games(self):
        print("tock")
        with self.db.Session() as session: 
            open_matches = session.query(Match).filter(Match.finished == False).all()
            for open_match in open_matches:
                print("checking if match closed yet")
                results = self.league.get_game(open_match)
                if results is not None:
                    print("match closed!")
                    self.process_votes(session, open_match, results)
                    open_match.finished = True
                    session.add(open_match)
                    session.commit()
                    
                    # we're in a side thread, to output to discord we need to post to the asyncio looper
                    # session can't carryover :(
                    asyncio.run_coroutine_threadsafe(self.output_votes_results(open_match.match_id, results), self.loop)
                else:
                    print("match is not closed")

    def process_votes(self, session, match: Match, results):
        we_win = results['extra_data']['our_team_won']
        for vote in match.votes:
            if vote.type_of_vote == VoteType.WIN.value or vote.type_of_vote == VoteType.LOSE.value:
                if vote.type_of_vote == VoteType.WIN.value and we_win:
                    vote.voter.brancoins += vote.brancoins * 2
                elif vote.type_of_vote == VoteType.LOSE.value and we_win == False:
                    vote.voter.brancoins += vote.brancoins * 2
                vote.processed = True
                session.add(vote)
        if we_win:
            for match_player in match.match_players:
                match_player.league_user.discord_user.brancoins += 50
                session.add(match_player)

    async def output_votes_results(self, match_id: str, results):
        try:
            with self.db.Session() as session:
                output = ""
                match = session.query(Match).filter(Match.match_id == match_id).first()
                we_win = results['extra_data']['our_team_won']
                for vote in match.votes:
                    print(vote)
                    guy = await self.fetch_user(vote.voter.user_id)
                    if vote.type_of_vote == VoteType.WIN.value or vote.type_of_vote == VoteType.LOSE.value:
                        if vote.type_of_vote == VoteType.WIN.value:
                            if we_win:
                                output += f"{guy.display_name } won {vote.brancoins} because the squad won their game! ::tada: :tada: :tada: \n"
                            else:
                                output += f"{guy.display_name } lost {vote.brancoins} ... don't know why you put your faith in clowns... :clown:  :clown:  :clown: \n"
                        elif vote.type_of_vote == VoteType.LOSE.value:
                            if we_win == False:
                                output += f"{guy.display_name } won {vote.brancoins} because the squad is curzed! :tada: :tada: :tada: \n"
                            else:
                                output += f"{guy.display_name } lost {vote.brancoins} ... why didn't you believe in da boiz :clown:  :clown:  :clown: \n"
                if we_win:    
                    for match_player in match.match_players:
                        guy = await self.fetch_user(match_player.league_user.discord_user.user_id)
                        output += f"{guy.display_name} made 50 for winning ! :tada: \n"
                await self.broadcast_all_str(session, output)
        except Exception as e: 
            print(e)
            print(traceback.format_exc())
                

    def look_for_open_games(self):
        print("tick")
        try:
            with self.db.Session() as session:
                trackable_users = session.query(LeagueUser).filter(LeagueUser.trackable == True).all()
                valid_games = self.league.get_valid_games(trackable_users, trackable_users)
                fresh_game_added = False
                for valid_game in valid_games:
                    print("valid game found")
                    match = Match()
                    match.finished = False
                    match.match_id = valid_game['spectator_data']['gameId']
                    match.start_time = datetime.now()
                    for participant in valid_game['valid_participants']:
                        match_player = MatchPlayer()
                        match_player.league_user = participant['league_user']
                        match_player.champion = self.league.champ_id_to_name(participant['participant_json']['championId'])
                        match.match_players.append(match_player)
                    if session.query(Match).filter(Match.match_id == str(match.match_id)).count() == 0:
                        fresh_game_added = True
                        session.add(match)
                        print("adding valid game")
                    else:
                        print("game was already tracked")
                session.commit()

                if fresh_game_added:
                    # we're in a side thread, to output to discord we need to post to the asyncio looper
                    asyncio.run_coroutine_threadsafe(self.broadcast_open_matches(), self.loop)

        except Exception as e: 
            print(e)
            print(traceback.format_exc())
    
    async def broadcast_open_matches(self):
        try:
            with self.db.Session() as session:
                open_matches = session.query(Match).filter(Match.finished == False).all()
                for open_match in open_matches:
                    embedVar = await ViewMatches.generate_embed_for_match(open_match, self)
                    await self.broadcast_all(session, embedVar)
                    await self.broadcast_all_str(session, "You have 5 minutes to vote!")
        except Exception as e: 
            print(e)
            print(traceback.format_exc())

    async def broadcast_all(self, session, embed: discord.Embed):
        guilds = session.query(Guild).filter(Guild.broadcast_channel_id != None).all()
        for guild in guilds:
            broadcast_channel = await self.fetch_channel(guild.broadcast_channel_id)
            await broadcast_channel.send(embed=embed)

    async def broadcast_all_str(self, session, msg):
        guilds = session.query(Guild).filter(Guild.broadcast_channel_id != None).all()
        for guild in guilds:
            broadcast_channel = await self.fetch_channel(guild.broadcast_channel_id)
            if guild.broadcast_role_id != None:
                disc_guild_obj = await self.fetch_guild(guild.guild_id)
                disc_roles = await disc_guild_obj.fetch_roles()
                disc_role: discord.Role = discord.utils.get(disc_roles, id=int(guild.broadcast_role_id))
                msg += f"\n{disc_role.mention}"
            await broadcast_channel.send(msg)

    # def wrap(func):
    #     @wraps(func)
    #     async def run(*args, loop=None, executor=None, **kwargs):
    #         if loop is None:
    #             loop = asyncio.get_event_loop()
    #         pfunc = partial(func, *args, **kwargs)
    #         return await loop.run_in_executor(executor, pfunc)
    #     return run


    # async def my_background_task(self):
    #     await self.wait_until_ready()
    #     while not self.is_closed():
    #         print("tick")
    #         self.look_for_open_games()
    #         try:
    #             self.handle_finished_games()
    #         except Exception as e: 
    #             print("failed to process finished game")
    #             print(e)
    #             print(traceback.format_exc())
                   
    #         await asyncio.sleep(120)  # task runs every 60 seconds

def run():
    itnent = discord.Intents.default()
    itnent.members = True
    itnent.message_content  = True
    client = DiscordMonitorClient(intents=itnent)
    print(f"Debug: {Env.is_debug}")
    client.run(Env.active_discord_token)

