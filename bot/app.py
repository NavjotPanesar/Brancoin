from datetime import datetime, time
import random
from threading import Thread
from sqlalchemy import create_engine, select
import discord.bot_league_monitor
from models.dbcontainer import DbContainer, DbService
from models.models import LeagueUser, Match, MatchPlayer
from league.leagueservice import LeagueService
from dependency_injector.wiring import Provide, inject
from league.leaguecontainer import LeagueContainer
from envvars import Env
import webserver
import webserver.web
import http.client, urllib

@inject
def main(dbservice: DbService = Provide[DbContainer.service], league_service: LeagueService = Provide[LeagueContainer.service]):
    with dbservice.Session() as session:
        # print(league_service.api_riot_watcher.account.by_riot_id("americas", "BofaJoeMamas", "0001"))
        # print(league_service.api_riot_watcher.account.by_riot_id("americas", "AwkwardPandas", "NA1"))
        statement = select(Match).filter(Match.finished == False)
        john = session.scalars(statement).first()
        print(john)
        print(league_service.get_game(john))
        # print(league_service.is_in_game(john))
        # print(league_service.get_valid_game(john, [john]))

def notify_pushover(msg: str):
    conn = http.client.HTTPSConnection("api.pushover.net:443")
    conn.request("POST", "/1/messages.json",
    urllib.parse.urlencode({
        "token": Env.pushover_token,
        "user": Env.pushover_user,
        "message": msg,
    }), { "Content-type": "application/x-www-form-urlencoded" })
    conn.getresponse()

container = LeagueContainer()
container.init_resources()
container.wire(modules=[__name__,  discord.bot_league_monitor])


container2 = DbContainer()
container2.init_resources()
container2.wire(modules=[__name__, webserver.web, discord.bot_league_monitor])

random.seed()

# main()

web_server_thread = Thread(target = webserver.web.start)
web_server_thread.start()

notify_pushover("starting bot")
retry_count = 0
retry_max = 10
while retry_count < retry_max:
    monitor = discord.bot_league_monitor.run()
    retry_count = retry_count + 1
    time.sleep(retry_count*retry_count)
    notify_pushover(f"failed, retry {retry_count}")

notify_pushover(f"failed, exit")