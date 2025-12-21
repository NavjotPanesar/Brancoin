"""
FakeLeagueService - A test double for LeagueService that allows controlled game state simulation.

Usage:
    fake = FakeLeagueService()

    # Simulate a user in an active game
    fake.set_active_game(league_user.puuid, {
        'gameId': 12345,
        'gameMode': 'ARAM',
        'participants': [{'puuid': 'xxx', 'championId': 1, ...}]
    })

    # Later, simulate the game finishing
    fake.finish_game(12345, our_team_won=True)

    # Clear all state
    fake.reset()
"""

from models.models import LeagueUser, Match


class FakeLeagueService:
    """
    A controllable fake implementation of LeagueService for testing.

    Allows you to:
    - Inject active games for specific users
    - Simulate games finishing with specific results
    - Control champion name lookups
    """

    def __init__(self):
        self.reset()

    def reset(self):
        """Clear all fake state."""
        self._active_games = {}  # puuid -> spectator_data
        self._finished_games = {}  # match_id (int) -> results dict
        self._puuids = {}  # (summoner_name, tag) -> puuid
        self._champion_names = {}  # champion_id -> name

    # ========== Control methods (for test setup) ==========

    def set_active_game(self, puuid: str, spectator_data: dict):
        """
        Inject an active game for a user.

        Args:
            puuid: The player's PUUID
            spectator_data: Dict with at minimum:
                - gameId: int
                - gameMode: str (ARAM, CLASSIC, URF)
                - participants: list of dicts with 'puuid' and 'championId'
        """
        self._active_games[puuid] = spectator_data

    def clear_active_game(self, puuid: str):
        """Remove an active game (simulates game ending but not yet fetchable)."""
        self._active_games.pop(puuid, None)

    def finish_game(self, match_id: int, our_team_won: bool, damage_dealt: list = None):
        """
        Mark a game as finished with results.

        Args:
            match_id: The game ID (int)
            our_team_won: Whether the tracked team won
            damage_dealt: Optional list of (LeagueUser, damage_amount) tuples
        """
        self._finished_games[match_id] = {
            'game_data': {'info': {'gameId': match_id}},
            'extra_data': {
                'our_team_won': our_team_won,
                'damage_dealt': damage_dealt or []
            }
        }

    def set_puuid(self, summoner_name: str, tag: str, puuid: str):
        """Set the PUUID that will be returned for a summoner name/tag combo."""
        self._puuids[(summoner_name, tag)] = puuid

    def set_champion_name(self, champion_id: int, name: str):
        """Set the champion name for a given ID."""
        self._champion_names[champion_id] = name

    # ========== LeagueService interface implementation ==========

    def get_puuid(self, league_user: LeagueUser) -> str:
        key = (league_user.summoner_name, league_user.tag)
        if key in self._puuids:
            return self._puuids[key]
        return f"fake-puuid-{league_user.summoner_name}-{league_user.tag}"

    def get_valid_game(self, league_user: LeagueUser, trackable_users: list):
        """Check if user is in an active game."""
        puuid = league_user.puuid
        if not puuid or puuid not in self._active_games:
            return None

        spectator_data = self._active_games[puuid]

        if spectator_data.get('gameMode') not in ('ARAM', 'CLASSIC', 'URF'):
            return None

        valid_participants = []
        for user in trackable_users:
            participant = self.find_participant(user, spectator_data.get('participants', []))
            if participant:
                valid_participants.append({
                    'league_user': user,
                    'participant_json': participant
                })

        if not valid_participants:
            return None

        return {
            'match_type': spectator_data['gameMode'],
            'spectator_data': spectator_data,
            'valid_participants': valid_participants
        }

    def get_valid_games(self, league_users: list, trackable_users: list):
        """Get all valid games for tracked users, deduplicated by gameId."""
        all_valid_games = []
        for league_user in league_users:
            valid_game = self.get_valid_game(league_user, trackable_users)
            if valid_game:
                all_valid_games.append(valid_game)

        unique_valid_games = {
            x['spectator_data']['gameId']: x for x in all_valid_games
        }.values()
        return unique_valid_games

    def get_game(self, game_to_check: Match):
        """Get finished game results."""
        match_id = int(game_to_check.match_id)
        return self._finished_games.get(match_id)

    def champ_id_to_name(self, search_id: int) -> str:
        """Convert champion ID to name."""
        return self._champion_names.get(search_id, "FakeChampion")

    def find_participant(self, user_to_find: LeagueUser, participants_to_search: list):
        """Find a participant by PUUID."""
        return next(
            (p for p in participants_to_search if p.get('puuid') == user_to_find.puuid),
            None
        )

    def get_matches(self, league_user: LeagueUser):
        """Get match history - returns empty list in fake."""
        return []
