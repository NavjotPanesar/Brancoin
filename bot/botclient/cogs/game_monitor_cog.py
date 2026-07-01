from datetime import datetime
import traceback
import discord
from discord.ext import commands, tasks
from models.dbcontainer import DbService
from models.models import Guild, LeagueUser, Match, MatchPlayer
from botclient.VoteType import VoteType
from botclient.helpers.match_utils import generate_embed_for_match
from league.leagueservice import LeagueService
from .base_cog import BaseCog


class GameMonitorCog(BaseCog):
    """Background tasks for monitoring League of Legends games."""

    def __init__(self, bot: commands.Bot, db_service: DbService, league_service: LeagueService):
        super().__init__(bot, db_service)
        self.league = league_service

    async def cog_load(self):
        """Start background tasks when cog is loaded."""
        self.look_for_open_games.start()
        self.handle_finished_games.start()

    async def cog_unload(self):
        """Stop background tasks when cog is unloaded."""
        self.look_for_open_games.cancel()
        self.handle_finished_games.cancel()

    @tasks.loop(seconds=30)
    async def look_for_open_games(self):
        """Check for new games from tracked League users."""
        try:
            with self.db.Session() as session:
                trackable_users = session.query(LeagueUser).filter(
                    LeagueUser.trackable == True
                ).all()
                valid_games = self.league.get_valid_games(trackable_users, trackable_users)
                fresh_game_added = False

                for valid_game in valid_games:
                    match = Match()
                    match.finished = False
                    match.match_id = valid_game['spectator_data']['gameId']
                    match.match_type = valid_game['match_type']
                    match.start_time = datetime.now()

                    for participant in valid_game['valid_participants']:
                        match_player = MatchPlayer()
                        match_player.league_user = participant['league_user']
                        match_player.champion = self.league.champ_id_to_name(
                            participant['participant_json']['championId']
                        )
                        match.match_players.append(match_player)

                    if session.query(Match).filter(Match.match_id == str(match.match_id)).count() == 0:
                        fresh_game_added = True
                        session.add(match)

                session.commit()

                if fresh_game_added:
                    await self._broadcast_open_matches()

        except Exception as e:
            print(e)
            print(traceback.format_exc())

    @look_for_open_games.before_loop
    async def before_look_for_open_games(self):
        """Wait until bot is ready before starting task."""
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=60)
    async def handle_finished_games(self):
        """Check for finished games and process votes."""
        try:
            with self.db.Session() as session:
                open_matches = session.query(Match).filter(Match.finished == False).all()
                for open_match in open_matches:
                    results = self.league.get_game(open_match)
                    if results is not None:
                        self._process_votes(session, open_match, results)
                        open_match.finished = True
                        session.add(open_match)
                        session.commit()

                        await self._output_votes_results(open_match.match_id, results)

        except Exception as e:
            print(e)
            print(traceback.format_exc())

    @handle_finished_games.before_loop
    async def before_handle_finished_games(self):
        """Wait until bot is ready before starting task."""
        await self.bot.wait_until_ready()

    def _process_votes(self, session, match: Match, results):
        """Process vote outcomes after a match finishes."""
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

    async def _output_votes_results(self, match_id: str, results):
        """Broadcast vote results to all configured channels."""
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
                    guy = await self.bot.fetch_user(vote.voter.user_id)
                    if vote.type_of_vote == VoteType.WIN.value or vote.type_of_vote == VoteType.LOSE.value:
                        if vote.type_of_vote == VoteType.WIN.value:
                            if we_win:
                                output += f"\n{guy.display_name} won {vote.brancoins} because the squad won their game! :tada: :tada: :tada:"
                            else:
                                output += f"\n{guy.display_name} lost {vote.brancoins} ... don't know why you put your faith in clowns... :clown: :clown: :clown:"
                        elif vote.type_of_vote == VoteType.LOSE.value:
                            if we_win == False:
                                output += f"\n{guy.display_name} won {vote.brancoins} because the squad is curzed! :tada: :tada: :tada:"
                            else:
                                output += f"\n{guy.display_name} lost {vote.brancoins} ... why didn't you believe in da boiz :clown: :clown: :clown:"

                if we_win:
                    for match_player in match.match_players:
                        guy = await self.bot.fetch_user(match_player.league_user.discord_user.user_id)
                        output += f"\n{guy.display_name} made 50 for winning! :tada:"

                await self._broadcast_all_str(session, output)

        except Exception as e:
            print(e)
            print(traceback.format_exc())

    async def _broadcast_open_matches(self):
        """Broadcast new open matches to all configured channels."""
        try:
            with self.db.Session() as session:
                open_matches = session.query(Match).filter(Match.finished == False).all()
                for open_match in open_matches:
                    embedVar = await generate_embed_for_match(open_match, self.bot)
                    await self._broadcast_all(session, embedVar)
                    await self._broadcast_all_str(session, "You have 5 minutes to vote!")
        except Exception as e:
            print(e)
            print(traceback.format_exc())

    async def _broadcast_all(self, session, embed: discord.Embed):
        """Broadcast an embed to all configured broadcast channels."""
        guilds = session.query(Guild).filter(Guild.broadcast_channel_id != None).all()
        for guild in guilds:
            broadcast_channel = await self.bot.fetch_channel(guild.broadcast_channel_id)
            await broadcast_channel.send(embed=embed)

    async def _broadcast_all_str(self, session, msg: str):
        """Broadcast a string message to all configured broadcast channels."""
        guilds = session.query(Guild).filter(Guild.broadcast_channel_id != None).all()
        for guild in guilds:
            broadcast_channel = await self.bot.fetch_channel(guild.broadcast_channel_id)
            final_msg = msg
            if guild.broadcast_role_id is not None:
                disc_guild_obj = await self.bot.fetch_guild(guild.guild_id)
                disc_roles = await disc_guild_obj.fetch_roles()
                disc_role: discord.Role = discord.utils.get(disc_roles, id=int(guild.broadcast_role_id))
                if disc_role:
                    final_msg += f"\n{disc_role.mention}"
            await broadcast_channel.send(final_msg)
