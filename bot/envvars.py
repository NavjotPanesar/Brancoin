import os

class Env():
    db_host = os.environ['POSTGRES_HOST'] 
    db_password = os.environ['POSTGRES_PASSWORD']
    db_user = os.environ['POSTGRES_USER']
    db_name = os.environ['POSTGRES_DB']
    
    db_conn_str = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}/{db_name}"
    discord_token = os.environ['DISCORD_TOKEN']
    discord_token_debug = os.environ['DISCORD_TOKEN_DEBUG']
    is_debug = os.environ['IS_DEBUG']
    league_token = os.environ['LEAGUE_TOKEN']
    web_port = os.environ['WEB_PORT']
    active_discord_token = discord_token if is_debug == "false" else discord_token_debug

    pushover_token = os.environ['PUSHOVER_TOKEN']
    pushover_user = os.environ['PUSHOVER_USER']