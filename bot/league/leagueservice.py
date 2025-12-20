from functools import lru_cache
import json
from os import name
import os
import traceback
from riotwatcher import LolWatcher, RiotWatcher
import riotwatcher
from riotwatcher.LolWatcher import MatchApiV5

from models.models import LeagueUser, Match

class LeagueService():
    region_riot_api = "americas"
    region_lol = "NA1"

    def __init__(self, lol_watcher: LolWatcher, riot_watcher: RiotWatcher) -> None:
        self.api_riot_watcher = riot_watcher
        self.api_lol_watcher = lol_watcher
        self.api_match : MatchApiV5 = lol_watcher.match

    def get_puuid(self, league_user: LeagueUser):
        return self.api_riot_watcher.account.by_riot_id(region=self.region_riot_api, game_name=league_user.summoner_name, tag_line=league_user.tag)['puuid']

    def get_matches(self, league_user: LeagueUser):
        return self.api_match.matchlist_by_puuid(self.region_lol, league_user.puuid)

    def get_valid_game(self, league_user: LeagueUser, trackable_users: list[LeagueUser]):
        print("get valid game for " )
        try:
            puuid = league_user.puuid
            if puuid:
                spectator_data = self.api_lol_watcher.spectator.by_summoner(self.region_lol, puuid)
            else: return None
        except:
            return None
        print ("got active game for " )

        if spectator_data['gameMode'] != "ARAM" and spectator_data['gameMode'] != "CLASSIC" and spectator_data['gameMode'] != "URF":
            print("Not a valid game mode")
            return None

        user_participant = list(map(lambda user: {'league_user': user, 'participant_json': self.find_participant(user, spectator_data['participants'])}, trackable_users))
        valid_participants = list(filter(lambda x: x['participant_json'] is not None, user_participant))

        if len(valid_participants) > 0:
            return {
                'match_type': spectator_data['gameMode'],
                'spectator_data': spectator_data,
                'valid_participants': valid_participants
            }
        else:
            print("Not enough valid players")
            return None

    def get_valid_games(self, league_users: list[LeagueUser], trackable_users: list[LeagueUser]):
        all_valid_games = []
        for league_user in league_users:
            valid_game = self.get_valid_game(league_user, trackable_users)
            if valid_game:
                all_valid_games.append(valid_game)
        unique_valid_games = {x['spectator_data']['gameId']: x for x in all_valid_games}.values()
        return unique_valid_games

    def champ_id_to_name(self, search_id):
        with open(os.path.dirname(__file__) + '/champion.json') as fp:
            champion_data = json.load(fp)
            for attribute, value in champion_data['data'].items():
                if value['key'] == str(search_id):
                    return attribute
        return "Unknown"


    def find_participant(self, user_to_find: LeagueUser, participants_to_search):
        return next(filter(lambda participant: participant['puuid'] == user_to_find.puuid, participants_to_search), None)

    def get_game(self, game_to_check: Match):
        try:
            game = self.api_lol_watcher.match.by_id(self.region_lol, f"NA1_{str(game_to_check.match_id)}")
            extra_data = {}
            try:
                our_players = game_to_check.match_players
                our_team_id = None
                damage_dealt = []
                for our_player in our_players:
                    puuid = our_player.league_user.puuid
                    participant_data = next(filter(lambda p : p['puuid'] == puuid, game['info']['participants']))
                    damage_dealt.append((our_player.league_user, participant_data['totalDamageDealtToChampions']))
                    extra_data['our_team_won'] = participant_data['win'] == True

                extra_data['damage_dealt'] = damage_dealt
                print("extra_data")
                print(extra_data)
            except Exception as e:
                print("failed to process data for game game")
                print(e)
                print(traceback.format_exc())
            return {'game_data': game, 'extra_data':extra_data}
        except:
            return None