"""Characterization tests for LeagueService.

These lock in the CURRENT behavior of the League-of-Legends monitor's data
transforms, driven by real recorded Riot payloads. They are a regression net,
not a spec: where current behavior looks buggy it is captured as-is and called
out with a `QUIRK:` comment so a later fix is a deliberate, visible change.

Fixtures (bot/tests/fixtures/league/) were captured from live games:
  * spectator_cherry_valid      - CHERRY (Arena), tracked player in game
  * spectator_cherry_other_game - a different CHERRY game, tracked player in it
  * spectator_kiwi_reject       - KIWI mode (NOT in valid_game_modes)
  * match_cherry_win            - finished CHERRY, tracked player placed 2 (win)
  * match_cherry_loss           - finished CHERRY, tracked player placed 4 (loss)
"""

from conftest import (
    load_fixture,
    make_league_user,
    make_match,
    PUUID_MAIN,
    PUUID_KIWI,
    PUUID_THIRD,
)


# --------------------------------------------------------------------------
# get_valid_game
# --------------------------------------------------------------------------

def test_valid_cherry_game_is_accepted(make_service):
    main = make_league_user(PUUID_MAIN)
    kiwi = make_league_user(PUUID_KIWI)
    svc = make_service(spectator=load_fixture("spectator_cherry_valid.json"))

    game = svc.get_valid_game(main, [main, kiwi])

    assert game is not None
    assert game["match_type"] == "CHERRY"
    assert game["spectator_data"]["gameId"] == 5601237546
    # Only the tracked user actually in this game is returned as a participant.
    assert len(game["valid_participants"]) == 1
    assert game["valid_participants"][0]["league_user"] is main
    assert game["valid_participants"][0]["participant_json"]["puuid"] == PUUID_MAIN


def test_kiwi_mode_is_rejected(make_service):
    # KIWI is not in valid_game_modes (ARAM/CLASSIC/URF/CHERRY) -> rejected.
    kiwi = make_league_user(PUUID_KIWI)
    svc = make_service(spectator=load_fixture("spectator_kiwi_reject.json"))

    assert svc.get_valid_game(kiwi, [kiwi]) is None


def test_no_tracked_participant_returns_none(make_service):
    # Query a real game, but the only "trackable" user isn't in it.
    main = make_league_user(PUUID_MAIN)
    stranger = make_league_user(PUUID_THIRD)
    svc = make_service(spectator=load_fixture("spectator_cherry_valid.json"))

    assert svc.get_valid_game(main, [stranger]) is None


def test_missing_puuid_short_circuits(make_service):
    # No puuid -> returns None without ever calling spectator.
    no_puuid = make_league_user(None)
    svc = make_service(spectator=load_fixture("spectator_cherry_valid.json"))

    assert svc.get_valid_game(no_puuid, [no_puuid]) is None
    svc.api_lol_watcher.spectator.by_summoner.assert_not_called()


def test_spectator_error_is_swallowed(make_service):
    # Not-in-game -> Riot raises -> bare except returns None. QUIRK: any error
    # (network, auth, schema) is indistinguishable from "not in a game".
    main = make_league_user(PUUID_MAIN)
    svc = make_service(spectator=Exception("404 not in game"))

    assert svc.get_valid_game(main, [main]) is None


# --------------------------------------------------------------------------
# get_valid_games (aggregation + dedup by gameId)
# --------------------------------------------------------------------------

def test_valid_games_dedupes_same_game(make_service):
    # Two tracked users whose lookups resolve to the SAME game collapse to one.
    main = make_league_user(PUUID_MAIN)
    kiwi = make_league_user(PUUID_KIWI)
    svc = make_service(spectator=load_fixture("spectator_cherry_valid.json"))

    games = list(svc.get_valid_games([main, kiwi], [main, kiwi]))

    assert len(games) == 1
    assert games[0]["spectator_data"]["gameId"] == 5601237546


def test_valid_games_keeps_distinct_games(make_service):
    # Two lookups resolving to different games are both kept (both contain the
    # tracked player). side_effect returns a different game per call.
    main = make_league_user(PUUID_MAIN)
    svc = make_service()
    svc.api_lol_watcher.spectator.by_summoner.side_effect = [
        load_fixture("spectator_cherry_valid.json"),       # game 5601237546
        load_fixture("spectator_cherry_other_game.json"),  # game 5601506853
    ]

    games = list(svc.get_valid_games([main, main], [main]))

    assert {g["spectator_data"]["gameId"] for g in games} == {5601237546, 5601506853}


# --------------------------------------------------------------------------
# get_game (post-match result extraction)
# --------------------------------------------------------------------------

def test_get_game_win(make_service):
    main = make_league_user(PUUID_MAIN, summoner_name="main")
    svc = make_service(match_by_id=load_fixture("match_cherry_win.json"))

    result = svc.get_game(make_match("5601237546", [main]))

    assert result["extra_data"]["our_team_won"] is True
    # Arena placement 2 -> win True; damage is carried through per player.
    assert result["extra_data"]["damage_dealt"] == [(main, 36878)]
    assert result["game_data"]["info"]["gameMode"] == "CHERRY"


def test_get_game_loss(make_service):
    main = make_league_user(PUUID_MAIN, summoner_name="main")
    svc = make_service(match_by_id=load_fixture("match_cherry_loss.json"))

    result = svc.get_game(make_match("5601398536", [main]))

    assert result["extra_data"]["our_team_won"] is False  # placement 4
    assert result["extra_data"]["damage_dealt"] == [(main, 44795)]


def test_get_game_error_returns_none(make_service):
    main = make_league_user(PUUID_MAIN)
    svc = make_service(match_by_id=Exception("500"))

    assert svc.get_game(make_match("123", [main])) is None


def test_get_game_our_team_won_reflects_last_player_only(make_service):
    # QUIRK: our_team_won is assigned inside the per-player loop, so with
    # multiple tracked players in one game it keeps only the LAST player's win
    # flag rather than combining them. This synthetic payload has two of our
    # players with opposite win values; the second one processed wins out.
    p_win = make_league_user("PUUID_WINNER", summoner_name="winner")
    p_lose = make_league_user("PUUID_LOSER", summoner_name="loser")
    synthetic = {
        "info": {
            "gameMode": "CHERRY",
            "participants": [
                {"puuid": "PUUID_WINNER", "win": True, "totalDamageDealtToChampions": 100},
                {"puuid": "PUUID_LOSER", "win": False, "totalDamageDealtToChampions": 200},
            ],
        }
    }
    svc = make_service(match_by_id=synthetic)

    # match_players ordered [winner, loser] -> loser processed last -> False.
    result = svc.get_game(make_match("999", [p_win, p_lose]))
    assert result["extra_data"]["our_team_won"] is False


# --------------------------------------------------------------------------
# pure helpers
# --------------------------------------------------------------------------

def test_champ_id_to_name(make_service):
    svc = make_service()
    assert svc.champ_id_to_name(266) == "Aatrox"
    assert svc.champ_id_to_name(999999) == "Unknown"


def test_find_participant(make_service):
    svc = make_service()
    spectator = load_fixture("spectator_cherry_valid.json")
    participants = spectator["participants"]

    found = svc.find_participant(make_league_user(PUUID_MAIN), participants)
    assert found is not None and found["puuid"] == PUUID_MAIN

    assert svc.find_participant(make_league_user("nope"), participants) is None
