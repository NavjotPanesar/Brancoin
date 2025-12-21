"""
Tests for GameMonitorCog - game detection and vote processing.

These tests use FakeLeagueService to simulate game states without hitting the Riot API.
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from discord.cogs.game_monitor_cog import GameMonitorCog
from discord.VoteType import VoteType
from models.models import User, LeagueUser, Match, MatchPlayer, Votes


class TestGameMonitorCogInit:
    """Tests for cog initialization."""

    def test_cog_starts_timers(self, mock_bot, fake_league_service, mock_db_service, mock_broadcast_cog):
        """Cog should start both timers on init."""
        with patch('discord.cogs.game_monitor_cog.RepeatTimer') as MockTimer:
            mock_timer_instance = MagicMock()
            MockTimer.return_value = mock_timer_instance

            cog = GameMonitorCog(mock_bot, fake_league_service, mock_db_service, mock_broadcast_cog)

            assert MockTimer.call_count == 2
            assert mock_timer_instance.start.call_count == 2

    def test_cog_unload_cancels_timers(self, mock_bot, fake_league_service, mock_db_service, mock_broadcast_cog):
        """Cog should cancel timers when unloaded."""
        with patch('discord.cogs.game_monitor_cog.RepeatTimer') as MockTimer:
            mock_timer_instance = MagicMock()
            MockTimer.return_value = mock_timer_instance

            cog = GameMonitorCog(mock_bot, fake_league_service, mock_db_service, mock_broadcast_cog)
            cog.cog_unload()

            assert mock_timer_instance.cancel.call_count == 2


class TestLookForOpenGames:
    """Tests for game detection logic."""

    def test_detects_new_game(self, mock_bot, fake_league_service, mock_db_service, mock_broadcast_cog, in_memory_db, sample_spectator_data):
        """Should create a Match when a new game is detected."""
        # Setup user in DB
        with in_memory_db() as session:
            discord_user = User()
            discord_user.user_id = "123"
            discord_user.guild_id = "456"
            session.add(discord_user)
            session.flush()

            league_user = LeagueUser()
            league_user.summoner_name = "TestPlayer"
            league_user.tag = "NA1"
            league_user.puuid = "test-puuid-12345"
            league_user.trackable = True
            league_user.voteable = True
            league_user.discord_user_id = discord_user.id
            session.add(league_user)
            session.commit()

        # Inject active game
        fake_league_service.set_active_game("test-puuid-12345", sample_spectator_data)
        fake_league_service.set_champion_name(1, "Ashe")

        # Create cog with timers disabled
        with patch('discord.cogs.game_monitor_cog.RepeatTimer'):
            mock_db_service.Session = in_memory_db
            cog = GameMonitorCog(mock_bot, fake_league_service, mock_db_service, mock_broadcast_cog)
            cog.look_for_open_games()

        # Verify match was created
        with in_memory_db() as session:
            match = session.query(Match).first()
            assert match is not None
            assert match.match_id == "5000000001"
            assert match.match_type == "ARAM"
            assert match.finished is False
            assert len(match.match_players) == 1
            assert match.match_players[0].champion == "Ashe"

    def test_does_not_duplicate_existing_match(self, mock_bot, fake_league_service, mock_db_service, mock_broadcast_cog, in_memory_db, sample_spectator_data):
        """Should not create duplicate Match records."""
        # Setup existing match
        with in_memory_db() as session:
            discord_user = User()
            discord_user.user_id = "123"
            discord_user.guild_id = "456"
            session.add(discord_user)
            session.flush()

            league_user = LeagueUser()
            league_user.summoner_name = "TestPlayer"
            league_user.tag = "NA1"
            league_user.puuid = "test-puuid-12345"
            league_user.trackable = True
            league_user.voteable = True
            league_user.discord_user_id = discord_user.id
            session.add(league_user)

            existing_match = Match()
            existing_match.match_id = "5000000001"
            existing_match.finished = False
            existing_match.start_time = datetime.now()
            session.add(existing_match)
            session.commit()

        fake_league_service.set_active_game("test-puuid-12345", sample_spectator_data)

        with patch('discord.cogs.game_monitor_cog.RepeatTimer'):
            mock_db_service.Session = in_memory_db
            cog = GameMonitorCog(mock_bot, fake_league_service, mock_db_service, mock_broadcast_cog)
            cog.look_for_open_games()

        # Should still only have one match
        with in_memory_db() as session:
            match_count = session.query(Match).count()
            assert match_count == 1

    def test_no_game_when_user_not_playing(self, mock_bot, fake_league_service, mock_db_service, mock_broadcast_cog, in_memory_db):
        """Should not create Match when no active games."""
        with in_memory_db() as session:
            discord_user = User()
            discord_user.user_id = "123"
            discord_user.guild_id = "456"
            session.add(discord_user)
            session.flush()

            league_user = LeagueUser()
            league_user.summoner_name = "TestPlayer"
            league_user.tag = "NA1"
            league_user.puuid = "test-puuid-12345"
            league_user.trackable = True
            league_user.voteable = True
            league_user.discord_user_id = discord_user.id
            session.add(league_user)
            session.commit()

        # No active game set in fake service

        with patch('discord.cogs.game_monitor_cog.RepeatTimer'):
            mock_db_service.Session = in_memory_db
            cog = GameMonitorCog(mock_bot, fake_league_service, mock_db_service, mock_broadcast_cog)
            cog.look_for_open_games()

        with in_memory_db() as session:
            match_count = session.query(Match).count()
            assert match_count == 0


class TestHandleFinishedGames:
    """Tests for finished game detection."""

    def test_marks_game_finished_when_results_available(self, mock_bot, fake_league_service, mock_db_service, mock_broadcast_cog, in_memory_db):
        """Should mark match as finished when results are available."""
        with in_memory_db() as session:
            match = Match()
            match.match_id = "12345"
            match.finished = False
            match.start_time = datetime.now()
            session.add(match)
            session.commit()

        fake_league_service.finish_game(12345, our_team_won=True)

        with patch('discord.cogs.game_monitor_cog.RepeatTimer'):
            mock_db_service.Session = in_memory_db
            cog = GameMonitorCog(mock_bot, fake_league_service, mock_db_service, mock_broadcast_cog)
            cog.handle_finished_games()

        with in_memory_db() as session:
            match = session.query(Match).first()
            assert match.finished is True

    def test_does_not_mark_finished_when_no_results(self, mock_bot, fake_league_service, mock_db_service, mock_broadcast_cog, in_memory_db):
        """Should not mark match finished if results not yet available."""
        with in_memory_db() as session:
            match = Match()
            match.match_id = "12345"
            match.finished = False
            match.start_time = datetime.now()
            session.add(match)
            session.commit()

        # Don't call finish_game - results not available yet

        with patch('discord.cogs.game_monitor_cog.RepeatTimer'):
            mock_db_service.Session = in_memory_db
            cog = GameMonitorCog(mock_bot, fake_league_service, mock_db_service, mock_broadcast_cog)
            cog.handle_finished_games()

        with in_memory_db() as session:
            match = session.query(Match).first()
            assert match.finished is False


class TestProcessVotes:
    """Tests for vote processing logic."""

    def test_win_vote_doubles_on_team_win(self, mock_bot, fake_league_service, mock_db_service, mock_broadcast_cog, in_memory_db):
        """WIN vote should double coins when team wins."""
        with in_memory_db() as session:
            voter = User()
            voter.user_id = "voter123"
            voter.guild_id = "guild456"
            voter.brancoins = 100
            session.add(voter)
            session.flush()

            match = Match()
            match.match_id = "match123"
            match.finished = False
            match.start_time = datetime.now()
            session.add(match)
            session.flush()

            vote = Votes()
            vote.voter_id = voter.id
            vote.match_id = match.match_id
            vote.type_of_vote = VoteType.WIN.value
            vote.brancoins = 50
            vote.processed = False
            session.add(vote)
            session.commit()

            # Process votes
            with patch('discord.cogs.game_monitor_cog.RepeatTimer'):
                mock_db_service.Session = in_memory_db
                cog = GameMonitorCog(mock_bot, fake_league_service, mock_db_service, mock_broadcast_cog)

                results = {'extra_data': {'our_team_won': True}}
                match = session.query(Match).first()
                cog.process_votes(session, match, results)
                session.commit()

        with in_memory_db() as session:
            voter = session.query(User).first()
            assert voter.brancoins == 200  # 100 + (50 * 2)

    def test_win_vote_no_payout_on_team_loss(self, mock_bot, fake_league_service, mock_db_service, mock_broadcast_cog, in_memory_db):
        """WIN vote should not pay out when team loses."""
        with in_memory_db() as session:
            voter = User()
            voter.user_id = "voter123"
            voter.guild_id = "guild456"
            voter.brancoins = 100
            session.add(voter)
            session.flush()

            match = Match()
            match.match_id = "match123"
            match.finished = False
            match.start_time = datetime.now()
            session.add(match)
            session.flush()

            vote = Votes()
            vote.voter_id = voter.id
            vote.match_id = match.match_id
            vote.type_of_vote = VoteType.WIN.value
            vote.brancoins = 50
            vote.processed = False
            session.add(vote)
            session.commit()

            with patch('discord.cogs.game_monitor_cog.RepeatTimer'):
                mock_db_service.Session = in_memory_db
                cog = GameMonitorCog(mock_bot, fake_league_service, mock_db_service, mock_broadcast_cog)

                results = {'extra_data': {'our_team_won': False}}
                match = session.query(Match).first()
                cog.process_votes(session, match, results)
                session.commit()

        with in_memory_db() as session:
            voter = session.query(User).first()
            assert voter.brancoins == 100  # Unchanged

    def test_lose_vote_doubles_on_team_loss(self, mock_bot, fake_league_service, mock_db_service, mock_broadcast_cog, in_memory_db):
        """LOSE vote should double coins when team loses."""
        with in_memory_db() as session:
            voter = User()
            voter.user_id = "voter123"
            voter.guild_id = "guild456"
            voter.brancoins = 100
            session.add(voter)
            session.flush()

            match = Match()
            match.match_id = "match123"
            match.finished = False
            match.start_time = datetime.now()
            session.add(match)
            session.flush()

            vote = Votes()
            vote.voter_id = voter.id
            vote.match_id = match.match_id
            vote.type_of_vote = VoteType.LOSE.value
            vote.brancoins = 30
            vote.processed = False
            session.add(vote)
            session.commit()

            with patch('discord.cogs.game_monitor_cog.RepeatTimer'):
                mock_db_service.Session = in_memory_db
                cog = GameMonitorCog(mock_bot, fake_league_service, mock_db_service, mock_broadcast_cog)

                results = {'extra_data': {'our_team_won': False}}
                match = session.query(Match).first()
                cog.process_votes(session, match, results)
                session.commit()

        with in_memory_db() as session:
            voter = session.query(User).first()
            assert voter.brancoins == 160  # 100 + (30 * 2)

    def test_players_earn_coins_on_win(self, mock_bot, fake_league_service, mock_db_service, mock_broadcast_cog, in_memory_db):
        """Players in the match should earn 50 coins when team wins."""
        with in_memory_db() as session:
            discord_user = User()
            discord_user.user_id = "player123"
            discord_user.guild_id = "guild456"
            discord_user.brancoins = 100
            session.add(discord_user)
            session.flush()

            league_user = LeagueUser()
            league_user.summoner_name = "TestPlayer"
            league_user.tag = "NA1"
            league_user.puuid = "puuid123"
            league_user.trackable = True
            league_user.voteable = True
            league_user.discord_user_id = discord_user.id
            session.add(league_user)
            session.flush()

            match = Match()
            match.match_id = "match123"
            match.finished = False
            match.start_time = datetime.now()
            session.add(match)
            session.flush()

            match_player = MatchPlayer()
            match_player.match_id = match.match_id
            match_player.league_user_id = league_user.id
            match_player.champion = "Ashe"
            session.add(match_player)
            session.commit()

            with patch('discord.cogs.game_monitor_cog.RepeatTimer'):
                mock_db_service.Session = in_memory_db
                cog = GameMonitorCog(mock_bot, fake_league_service, mock_db_service, mock_broadcast_cog)

                results = {'extra_data': {'our_team_won': True}}
                match = session.query(Match).first()
                cog.process_votes(session, match, results)
                session.commit()

        with in_memory_db() as session:
            user = session.query(User).first()
            assert user.brancoins == 150  # 100 + 50


class TestFullGameLifecycle:
    """Integration tests for complete game lifecycle."""

    def test_game_detected_then_finished(self, mock_bot, fake_league_service, mock_db_service, mock_broadcast_cog, in_memory_db, sample_spectator_data):
        """Test complete flow: game detected -> tracked -> finished -> votes processed."""
        # Setup user
        with in_memory_db() as session:
            discord_user = User()
            discord_user.user_id = "123"
            discord_user.guild_id = "456"
            discord_user.brancoins = 100
            session.add(discord_user)
            session.flush()

            league_user = LeagueUser()
            league_user.summoner_name = "TestPlayer"
            league_user.tag = "NA1"
            league_user.puuid = "test-puuid-12345"
            league_user.trackable = True
            league_user.voteable = True
            league_user.discord_user_id = discord_user.id
            session.add(league_user)
            session.commit()

        mock_db_service.Session = in_memory_db

        with patch('discord.cogs.game_monitor_cog.RepeatTimer'):
            cog = GameMonitorCog(mock_bot, fake_league_service, mock_db_service, mock_broadcast_cog)

            # Step 1: Game starts
            fake_league_service.set_active_game("test-puuid-12345", sample_spectator_data)
            cog.look_for_open_games()

            # Verify match created
            with in_memory_db() as session:
                match = session.query(Match).first()
                assert match is not None
                assert match.finished is False

                # Step 2: Someone votes
                vote = Votes()
                vote.voter_id = session.query(User).first().id
                vote.match_id = match.match_id
                vote.type_of_vote = VoteType.WIN.value
                vote.brancoins = 25
                vote.processed = False
                session.add(vote)
                session.commit()

            # Step 3: Game ends
            fake_league_service.clear_active_game("test-puuid-12345")
            fake_league_service.finish_game(5000000001, our_team_won=True)
            cog.handle_finished_games()

            # Verify final state
            with in_memory_db() as session:
                match = session.query(Match).first()
                assert match.finished is True

                user = session.query(User).first()
                # 100 + (25 * 2) vote win + 50 player bonus = 200
                assert user.brancoins == 200
