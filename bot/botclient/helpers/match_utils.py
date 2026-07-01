import discord
from discord.ext.commands import Bot
from models.models import Match
from botclient.VoteType import VoteType


async def generate_embed_for_match(match: Match, bot: Bot) -> discord.Embed:
    """Generate an embed showing match details, players, and votes."""
    embedVar = discord.Embed(
        title=f"id: {match.match_id}",
        description="",
        color=0xccccff
    )
    embedVar.set_author(
        name=f"{match.match_type} in progress",
        icon_url="https://i.imgur.com/RXKFjqo.png"
    )

    embedVar.add_field(name="\u200b", value="", inline=False)
    embedVar.add_field(name="Players: ", value="", inline=False)
    for match_player in match.match_players:
        discord_id = match_player.league_user.discord_user.user_id
        discord_user = await bot.fetch_user(discord_id)
        embedVar.add_field(
            name=str(discord_user.display_name),
            value=str(match_player.champion),
            inline=True
        )

    embedVar.add_field(name="\u200b", value="", inline=False)
    embedVar.add_field(name="Votes placed: ", value="", inline=False)
    for vote in match.votes:
        discord_user = await bot.fetch_user(vote.voter.user_id)
        embedVar.add_field(
            name=f"{VoteType(vote.type_of_vote).name}",
            value=f"{discord_user.display_name} {vote.brancoins}",
            inline=False
        )

    embedVar.add_field(name="\u200b", value="", inline=False)
    vote_time_left_seconds = 5*60 - match.get_time_since_start().seconds
    vote_time_left_seconds = max(0, vote_time_left_seconds)
    embedVar.add_field(
        name="Time left to vote: ",
        value=str(vote_time_left_seconds) + "s",
        inline=False
    )

    return embedVar
