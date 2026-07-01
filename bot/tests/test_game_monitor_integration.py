"""End-to-end integration test for the League game-monitor flow.

Drives the real GameMonitorCog background-task bodies against a real (in-memory
SQLite) database and a real LeagueService whose Riot watchers are mocked with
recorded payloads. Walks a single game through its lifecycle and asserts the DB
state at each step:

    STEP 1  no active game        -> no Match rows
    STEP 2  active game detected  -> one open Match (+ MatchPlayer); re-poll dedupes
    STEP 3  game finishes (win)   -> Match.finished, votes processed, brancoins paid

Only the Riot HTTP boundary and Discord are mocked; the DB, models, LeagueService
transforms, and cog logic are all real.
"""

import asyncio

from unittest.mock import MagicMock

from conftest import load_fixture, PUUID_MAIN
from botclient.VoteType import VoteType
from league.leagueservice import LeagueService
from botclient.cogs.game_monitor_cog import GameMonitorCog
from models.models import Guild, User, LeagueUser, Match, MatchPlayer, Votes


def _run(coro):
    return asyncio.run(coro)


def test_full_game_flow(db_service, discord_bot):
    # Real LeagueService with mocked watchers we reconfigure per step.
    lol = MagicMock()
    riot = MagicMock()
    service = LeagueService(lol_watcher=lol, riot_watcher=riot)
    cog = GameMonitorCog(discord_bot, db_service, service)

    # ---- baseline seed: a guild with no broadcast channel (so broadcasts no-op),
    #      a tracked league player, and a separate voter. ----
    with db_service.Session() as s:
        guild = Guild()
        guild.guild_id = "g1"
        guild.brancoins = 10
        player_user = User()
        player_user.user_id = "100"
        player_user.guild_id = "g1"
        player_user.brancoins = 0
        voter_user = User()
        voter_user.user_id = "200"
        voter_user.guild_id = "g1"
        voter_user.brancoins = 100
        s.add_all([guild, player_user, voter_user])
        s.flush()
        player_user_id, voter_user_id = player_user.id, voter_user.id

        league_user = LeagueUser()
        league_user.summoner_name = "main"
        league_user.tag = "NA1"
        league_user.trackable = True
        league_user.voteable = True
        league_user.puuid = PUUID_MAIN
        league_user.discord_user = player_user
        s.add(league_user)
        s.commit()

    # ============================ STEP 1: no active game ============================
    # Not in a game -> Riot raises -> LeagueService swallows it -> no games found.
    lol.spectator.by_summoner.side_effect = Exception("404 not in an active game")

    _run(cog.look_for_open_games.coro(cog))

    with db_service.Session() as s:
        assert s.query(Match).count() == 0, "no match should exist before a game starts"

    # ============================ STEP 2: active game ==============================
    lol.spectator.by_summoner.side_effect = None
    lol.spectator.by_summoner.return_value = load_fixture("spectator_cherry_valid.json")

    _run(cog.look_for_open_games.coro(cog))

    with db_service.Session() as s:
        matches = s.query(Match).all()
        assert len(matches) == 1
        match = matches[0]
        assert str(match.match_id) == "5601237546"
        assert match.finished is False
        assert match.match_type == "CHERRY"

        players = s.query(MatchPlayer).all()
        assert len(players) == 1
        assert players[0].league_user.puuid == PUUID_MAIN
        # champion resolved from the spectator championId, not a fallback.
        assert players[0].champion not in (None, "", "Unknown")

    # Re-polling while the same game is still live must NOT create a duplicate.
    _run(cog.look_for_open_games.coro(cog))
    with db_service.Session() as s:
        assert s.query(Match).count() == 1, "same live game should not be re-added"

    # ---- a user bets WIN on the open match ----
    with db_service.Session() as s:
        match = s.query(Match).first()
        vote = Votes()
        vote.voter_id = voter_user_id
        vote.type_of_vote = VoteType.WIN.value
        vote.brancoins = 50
        vote.processed = False
        match.votes.append(vote)
        s.commit()

    # ============================ STEP 3: game finishes ============================
    # Recorded finished match: our tracked player placed 2 -> win True.
    lol.match.by_id.return_value = load_fixture("match_cherry_win.json")

    _run(cog.handle_finished_games.coro(cog))

    with db_service.Session() as s:
        match = s.query(Match).first()
        assert match.finished is True, "match should be marked finished"

        vote = s.query(Votes).first()
        assert vote.processed is True

        voter = s.query(User).filter(User.id == voter_user_id).first()
        # WIN bet on a won game pays double the stake, added to the balance.
        assert voter.brancoins == 100 + 50 * 2

        player = s.query(User).filter(User.id == player_user_id).first()
        # every tracked player on the winning side gets a flat +50.
        assert player.brancoins == 0 + 50

    # A second finished-games pass is a no-op: the match is already finished.
    voter_balance_before = None
    with db_service.Session() as s:
        voter_balance_before = s.query(User).filter(User.id == voter_user_id).first().brancoins
    _run(cog.handle_finished_games.coro(cog))
    with db_service.Session() as s:
        assert s.query(User).filter(User.id == voter_user_id).first().brancoins == voter_balance_before, \
            "already-finished match must not pay out again"
