import os


class _EnvMeta(type):
    """Metaclass so that ``Env.some_var`` reads ``os.environ`` lazily, at the
    moment of access, rather than eagerly at import time. This lets tooling that
    only needs a subset of the config (e.g. Alembic, which only needs the
    ``POSTGRES_*`` vars) import ``Env`` without every unrelated secret having to
    be present in the environment."""

    @property
    def db_host(cls):
        return os.environ['POSTGRES_HOST']

    @property
    def db_password(cls):
        return os.environ['POSTGRES_PASSWORD']

    @property
    def db_user(cls):
        return os.environ['POSTGRES_USER']

    @property
    def db_name(cls):
        return os.environ['POSTGRES_DB']

    @property
    def db_conn_str(cls):
        return (
            f"postgresql+psycopg2://{cls.db_user}:{cls.db_password}"
            f"@{cls.db_host}/{cls.db_name}"
        )

    @property
    def discord_token(cls):
        return os.environ['DISCORD_TOKEN']

    @property
    def discord_token_debug(cls):
        return os.environ['DISCORD_TOKEN_DEBUG']

    @property
    def is_debug(cls):
        return os.environ['IS_DEBUG']

    @property
    def league_token(cls):
        return os.environ['LEAGUE_TOKEN']

    @property
    def web_port(cls):
        return os.environ['WEB_PORT']

    @property
    def active_discord_token(cls):
        return cls.discord_token if cls.is_debug == "false" else cls.discord_token_debug

    @property
    def pushover_token(cls):
        return os.environ['PUSHOVER_TOKEN']

    @property
    def pushover_user(cls):
        return os.environ['PUSHOVER_USER']


class Env(metaclass=_EnvMeta):
    pass
