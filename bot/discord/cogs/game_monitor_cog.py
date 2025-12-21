import asyncio
import traceback
from datetime import datetime

from discord.ext import commands

from discord.repeattimer import RepeatTimer
from discord.VoteType import VoteType
from discord.commands.viewmatches import ViewMatches
from discord.cogs.broadcast_cog import BroadcastCog
from models.models import LeagueUser, Match, MatchPlayer
from models.dbcontainer import DbService
from league.leagueservice import LeagueService


class GameMonitorCog(commands.Cog):
    """Monitors League of Legends games and processes votes."""

    def __init__(self, bot, league_service: LeagueService, db_service: DbService, broadcast_cog: BroadcastCog):
        self.bot = bot
        self.league = league_service
        self.db = db_service
        self.broadcast = broadcast_cog

        self.open_game_timer = RepeatTimer(30, self.look_for_open_games)
        self.open_game_timer.start()

        self.closed_game_timer = RepeatTimer(60, self.handle_finished_games)
        self.closed_game_timer.start()

    def cog_unload(self):
        """Clean up timers when cog is unloaded."""
        self.open_game_timer.cancel()
        self.closed_game_timer.cancel()

    def look_for_open_games(self):
        """Poll for new games and create Match records."""
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
                    match.match_type = valid_game['match_type']
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
                    asyncio.run_coroutine_threadsafe(self.broadcast_open_matches(), self.bot.loop)

        except Exception as e:
            print(e)
            print(traceback.format_exc())

    def handle_finished_games(self):
        """Check for finished games and process votes."""
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

                    asyncio.run_coroutine_threadsafe(
                        self.output_votes_results(open_match.match_id, results),
                        self.bot.loop
                    )
                else:
                    print("match is not closed")

    def process_votes(self, session, match: Match, results):
        """Award coins based on vote outcomes."""
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
        """Broadcast the results of a finished match."""
        try:
            with self.db.Session() as session:
                output = ""
                match = session.query(Match).filter(Match.match_id == match_id).first()
                we_win = results['extra_data']['our_team_won']
                if we_win:
                    output += "The boys were victorious!"
                else:
                    output += "These idiots lost."
                for vote in match.votes:
                    print(vote)
                    guy = await self.bot.fetch_user(vote.voter.user_id)
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
                        guy = await self.bot.fetch_user(match_player.league_user.discord_user.user_id)
                        output += f"{guy.display_name} made 50 for winning ! :tada: \n"
                await self.broadcast.broadcast_all_str(output)
        except Exception as e:
            print(e)
            print(traceback.format_exc())

    async def broadcast_open_matches(self):
        """Broadcast all currently open matches."""
        try:
            with self.db.Session() as session:
                open_matches = session.query(Match).filter(Match.finished == False).all()
                for open_match in open_matches:
                    embedVar = await ViewMatches.generate_embed_for_match(open_match, self.bot)
                    await self.broadcast.broadcast_all(embedVar)
                    await self.broadcast.broadcast_all_str("You have 5 minutes to vote!")
        except Exception as e:
            print(e)
            print(traceback.format_exc())
