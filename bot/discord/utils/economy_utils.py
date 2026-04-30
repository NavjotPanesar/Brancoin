import cachetools
from cachetools.keys import hashkey
from models.models import User


@cachetools.cached(cache=cachetools.TTLCache(maxsize=10, ttl=10), key=lambda session, guild_id: hashkey(guild_id))
def upper_class_wealth(session, guild_id: str) -> int:
    """Get the brancoins of the 3rd richest user in a guild.

    Used to calculate dynamic jackpot chances and trickle amounts.
    """
    top_3_users = session.query(User).filter(
        User.guild_id == guild_id
    ).order_by(User.brancoins.desc()).limit(3).all()
    return top_3_users[-1].brancoins if len(top_3_users) >= 3 else 0
