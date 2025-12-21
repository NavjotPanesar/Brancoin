"""
Tests for FakeLeagueService to ensure the test double behaves correctly.
"""
import pytest
from league.fake_leagueservice import FakeLeagueService
from models.models import LeagueUser, Match


class TestFakeLeagueService:

    def test_no_active_game_by_default(self, fake_league_service):
        """Users should have no active game initially."""
        user = LeagueUser()
        user.puuid = "some-puuid"
        user.summoner_name = "Test"
        user.tag = "NA1"

        result = fake_league_service.get_valid_game(user, [user])
        assert result is None

    def test_set_active_game(self, fake_league_service, sample_spectator_data):
        """Setting an active game should make it discoverable."""
        user = LeagueUser()
        user.puuid = "test-puuid-12345"
        user.summoner_name = "TestPlayer"
        user.tag = "NA1"
        user.trackable = True

        fake_league_service.set_active_game(user.puuid, sample_spectator_data)

        result = fake_league_service.get_valid_game(user, [user])

        assert result is not None
        assert result['match_type'] == 'ARAM'
        assert result['spectator_data']['gameId'] == 5000000001
        assert len(result['valid_participants']) == 1

    def test_get_valid_games_deduplicates(self, fake_league_service, sample_spectator_data):
        """Multiple users in same game should return one game."""
        user1 = LeagueUser()
        user1.puuid = "test-puuid-12345"
        user1.summoner_name = "TestPlayer"
        user1.tag = "NA1"
        user1.trackable = True

        user2 = LeagueUser()
        user2.puuid = "test-puuid-67890"
        user2.summoner_name = "TestPlayer2"
        user2.tag = "NA1"
        user2.trackable = True

        # Add second user to participants
        sample_spectator_data['participants'].append({
            'puuid': 'test-puuid-67890',
            'championId': 3,
            'teamId': 100,
            'summonerName': 'TestPlayer2'
        })

        fake_league_service.set_active_game(user1.puuid, sample_spectator_data)
        fake_league_service.set_active_game(user2.puuid, sample_spectator_data)

        games = list(fake_league_service.get_valid_games([user1, user2], [user1, user2]))

        assert len(games) == 1

    def test_clear_active_game(self, fake_league_service, sample_spectator_data):
        """Clearing a game should make it undiscoverable."""
        user = LeagueUser()
        user.puuid = "test-puuid-12345"
        user.summoner_name = "TestPlayer"
        user.tag = "NA1"

        fake_league_service.set_active_game(user.puuid, sample_spectator_data)
        fake_league_service.clear_active_game(user.puuid)

        result = fake_league_service.get_valid_game(user, [user])
        assert result is None

    def test_finish_game(self, fake_league_service):
        """Finished games should be retrievable via get_game."""
        match = Match()
        match.match_id = "12345"

        fake_league_service.finish_game(12345, our_team_won=True)

        result = fake_league_service.get_game(match)

        assert result is not None
        assert result['extra_data']['our_team_won'] is True

    def test_unfinished_game_returns_none(self, fake_league_service):
        """Games not marked as finished should return None."""
        match = Match()
        match.match_id = "99999"

        result = fake_league_service.get_game(match)
        assert result is None

    def test_invalid_game_mode_rejected(self, fake_league_service):
        """Non-ARAM/CLASSIC/URF game modes should be rejected."""
        user = LeagueUser()
        user.puuid = "test-puuid"
        user.summoner_name = "Test"
        user.tag = "NA1"

        fake_league_service.set_active_game(user.puuid, {
            'gameId': 123,
            'gameMode': 'TFT',
            'participants': [{'puuid': 'test-puuid', 'championId': 1}]
        })

        result = fake_league_service.get_valid_game(user, [user])
        assert result is None

    def test_reset_clears_all_state(self, fake_league_service, sample_spectator_data):
        """Reset should clear all injected state."""
        user = LeagueUser()
        user.puuid = "test-puuid-12345"
        user.summoner_name = "Test"
        user.tag = "NA1"

        fake_league_service.set_active_game(user.puuid, sample_spectator_data)
        fake_league_service.finish_game(12345, our_team_won=True)
        fake_league_service.set_champion_name(1, "Annie")

        fake_league_service.reset()

        assert fake_league_service.get_valid_game(user, [user]) is None
        assert fake_league_service.champ_id_to_name(1) == "FakeChampion"

    def test_champion_name_lookup(self, fake_league_service):
        """Champion name can be set and retrieved."""
        fake_league_service.set_champion_name(1, "Annie")
        fake_league_service.set_champion_name(2, "Olaf")

        assert fake_league_service.champ_id_to_name(1) == "Annie"
        assert fake_league_service.champ_id_to_name(2) == "Olaf"
        assert fake_league_service.champ_id_to_name(999) == "FakeChampion"

    def test_get_puuid_generates_fake(self, fake_league_service):
        """PUUID should be generated if not explicitly set."""
        user = LeagueUser()
        user.summoner_name = "TestPlayer"
        user.tag = "NA1"

        puuid = fake_league_service.get_puuid(user)

        assert puuid == "fake-puuid-TestPlayer-NA1"

    def test_get_puuid_uses_set_value(self, fake_league_service):
        """Explicitly set PUUID should be returned."""
        user = LeagueUser()
        user.summoner_name = "TestPlayer"
        user.tag = "NA1"

        fake_league_service.set_puuid("TestPlayer", "NA1", "custom-puuid-123")

        puuid = fake_league_service.get_puuid(user)
        assert puuid == "custom-puuid-123"
