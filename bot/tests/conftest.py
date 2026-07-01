"""Shared fixtures for LeagueService characterization tests.

These tests feed *real, recorded* Riot API payloads (captured via
``league/recording_watcher.py``) through LeagueService and lock in the current
behavior. They intentionally characterize behavior as-is -- including known
quirks -- rather than asserting what the code "should" do.

The watchers are mocked, so nothing hits the network and no DB is required:
LeagueService only reads ``.puuid`` off LeagueUser and ``.match_players`` off
Match, so transient (unpersisted) model instances are enough.
"""

import json
import os
from unittest.mock import AsyncMock, MagicMock

# envvars.py reads these at import time, and importing the cog (via base_cog ->
# Env) requires them. Set harmless defaults before any such import runs.
for _k, _v in {
    "POSTGRES_HOST": "x", "POSTGRES_PASSWORD": "x", "POSTGRES_USER": "x",
    "POSTGRES_DB": "x", "DISCORD_TOKEN": "x", "DISCORD_TOKEN_DEBUG": "x",
    "IS_DEBUG": "true", "LEAGUE_TOKEN": "x", "WEB_PORT": "8081",
    "PUSHOVER_TOKEN": "x", "PUSHOVER_USER": "x",
}.items():
    os.environ.setdefault(_k, _v)

import pytest

from league.leagueservice import LeagueService
from models.base import Base
from models.models import LeagueUser, Match, MatchPlayer, User

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "league")

# The three tracked summoners present in the captured payloads. Real puuids from
# the recording run; names/tags are arbitrary (no account.by_riot_id was
# captured, so get_puuid is out of scope here).
PUUID_MAIN = "Lx3SYa3a_xYTjLwYvV08G8sUNlMAmmuVGft0JfGqOQ3EDBBakBVRxyJi7xwnmzSQSAPfZF3NS6IMag"
PUUID_KIWI = "XPlZOG-9eXcsjipFEuXIJOZEFMRwc8-3uhG2w6o2w8RxIRiEPTaOlY15wlqj42jEIilLnXBRqIlWqw"
PUUID_THIRD = "H6tW870dy2McphhQgzep78ZIK8Xr9ET0lDOvQkrM5zuqT-EXBZtTfqaXG6sWJWRnWAi-V9U9JcUoUA"


def load_fixture(name: str) -> dict:
    """Load the ``response`` payload from a curated capture fixture."""
    with open(os.path.join(FIXTURE_DIR, name)) as fp:
        return json.load(fp)["response"]


def make_league_user(puuid, summoner_name="player", tag="NA1", user_id="1",
                     trackable=True, voteable=True) -> LeagueUser:
    """Build a transient LeagueUser (not attached to any session)."""
    lu = LeagueUser()
    lu.puuid = puuid
    lu.summoner_name = summoner_name
    lu.tag = tag
    lu.trackable = trackable
    lu.voteable = voteable
    discord_user = User()
    discord_user.user_id = user_id
    discord_user.guild_id = "guild"
    discord_user.brancoins = 0
    lu.discord_user = discord_user
    return lu


def make_match(match_id, league_users, champion="Unknown") -> Match:
    """Build a transient Match with MatchPlayers for the given LeagueUsers."""
    match = Match()
    match.match_id = str(match_id)
    match.finished = False
    match.match_type = "CHERRY"
    for lu in league_users:
        mp = MatchPlayer()
        mp.league_user = lu
        mp.champion = champion
        match.match_players.append(mp)
    return match


@pytest.fixture
def make_service():
    """Factory that builds a LeagueService with mocked watchers.

    Pass ``spectator`` (a response dict or Exception) and/or ``match_by_id`` to
    control what the underlying Riot calls return.
    """
    def _factory(spectator=None, match_by_id=None):
        lol = MagicMock()
        riot = MagicMock()
        if isinstance(spectator, Exception):
            lol.spectator.by_summoner.side_effect = spectator
        elif spectator is not None:
            lol.spectator.by_summoner.return_value = spectator
        if isinstance(match_by_id, Exception):
            lol.match.by_id.side_effect = match_by_id
        elif match_by_id is not None:
            lol.match.by_id.return_value = match_by_id
        return LeagueService(lol_watcher=lol, riot_watcher=riot)
    return _factory


@pytest.fixture
def db_service():
    """A DbService-shaped object backed by a fresh in-memory SQLite DB.

    Uses StaticPool so every session shares the one in-memory connection (the
    cog opens several sessions per iteration). Function-scoped -> isolated DB
    per test.
    """
    from types import SimpleNamespace

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return SimpleNamespace(engine=engine, Session=sessionmaker(engine))


@pytest.fixture
def discord_bot():
    """A MagicMock Discord bot with async methods stubbed.

    Broadcasts are exercised but no-op at the DB level (tests don't set a
    guild broadcast_channel_id), so these just need to not blow up.
    """
    bot = MagicMock()
    user_stub = MagicMock()
    user_stub.display_name = "tester"
    bot.fetch_user = AsyncMock(return_value=user_stub)
    bot.fetch_channel = AsyncMock()
    bot.fetch_guild = AsyncMock()
    bot.wait_until_ready = AsyncMock()
    return bot
