"""
Pytest configuration and fixtures for Brancoin tests.
"""
import asyncio
import os
import sys

# Set up test environment variables BEFORE importing any app modules
os.environ.setdefault('POSTGRES_HOST', 'localhost')
os.environ.setdefault('POSTGRES_PASSWORD', 'test')
os.environ.setdefault('POSTGRES_USER', 'test')
os.environ.setdefault('POSTGRES_DB', 'brancoin_test')
os.environ.setdefault('DISCORD_TOKEN', 'fake-discord-token')
os.environ.setdefault('DISCORD_TOKEN_DEBUG', 'fake-discord-token-debug')
os.environ.setdefault('IS_DEBUG', 'true')
os.environ.setdefault('LEAGUE_TOKEN', 'fake-league-token')
os.environ.setdefault('WEB_PORT', '8080')
os.environ.setdefault('PUSHOVER_TOKEN', 'fake-pushover-token')
os.environ.setdefault('PUSHOVER_USER', 'fake-pushover-user')

# Add bot directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.base import Base
from models.models import User, LeagueUser, Match, MatchPlayer, Guild, Votes
from league.fake_leagueservice import FakeLeagueService


@pytest.fixture
def fake_league_service():
    """Provides a fresh FakeLeagueService instance for each test."""
    service = FakeLeagueService()
    yield service
    service.reset()


@pytest.fixture
def in_memory_db():
    """Creates an in-memory SQLite database for testing."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    yield Session
    engine.dispose()


@pytest.fixture
def mock_db_service(in_memory_db):
    """Creates a mock DbService that uses the in-memory database."""
    mock_service = MagicMock()
    mock_service.Session = in_memory_db
    return mock_service


@pytest.fixture
def mock_bot():
    """Creates a mock Discord bot."""
    bot = MagicMock()
    bot.loop = MagicMock()
    bot.fetch_user = AsyncMock(return_value=MagicMock(display_name="TestUser"))
    bot.fetch_channel = AsyncMock(return_value=MagicMock(send=AsyncMock()))
    bot.fetch_guild = AsyncMock(return_value=MagicMock(fetch_roles=AsyncMock(return_value=[])))
    return bot


@pytest.fixture(autouse=True)
def mock_asyncio_run_coroutine_threadsafe():
    """
    Mock asyncio.run_coroutine_threadsafe to properly close coroutines.

    In GameMonitorCog, async methods like broadcast_open_matches() are scheduled
    via run_coroutine_threadsafe. In tests, these coroutines are created but never
    run, causing "coroutine never awaited" warnings. This fixture properly closes them.
    """
    original = asyncio.run_coroutine_threadsafe

    def mock_run(coro, loop):
        # Close the coroutine to prevent the warning
        coro.close()
        return MagicMock()

    with patch.object(asyncio, 'run_coroutine_threadsafe', side_effect=mock_run):
        yield


@pytest.fixture
def mock_broadcast_cog():
    """Creates a mock BroadcastCog."""
    cog = MagicMock()
    cog.broadcast_all = AsyncMock()
    cog.broadcast_all_str = AsyncMock()
    return cog


@pytest.fixture
def sample_league_user(in_memory_db):
    """Creates a sample LeagueUser with associated Discord User."""
    with in_memory_db() as session:
        discord_user = User()
        discord_user.user_id = "123456789"
        discord_user.guild_id = "987654321"
        discord_user.brancoins = 100
        session.add(discord_user)
        session.flush()

        league_user = LeagueUser()
        league_user.summoner_name = "TestPlayer"
        league_user.tag = "NA1"
        league_user.trackable = True
        league_user.voteable = True
        league_user.puuid = "test-puuid-12345"
        league_user.discord_user_id = discord_user.id
        session.add(league_user)
        session.commit()

        session.refresh(league_user)
        yield league_user


@pytest.fixture
def sample_spectator_data():
    """Sample spectator data that mimics Riot API response."""
    return {
        'gameId': 5000000001,
        'gameMode': 'ARAM',
        'participants': [
            {
                'puuid': 'test-puuid-12345',
                'championId': 1,
                'teamId': 100,
                'summonerName': 'TestPlayer'
            },
            {
                'puuid': 'enemy-puuid-1',
                'championId': 2,
                'teamId': 200,
                'summonerName': 'Enemy1'
            }
        ]
    }
