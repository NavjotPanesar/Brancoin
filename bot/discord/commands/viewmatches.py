

from discord import Message
import discord
import discord.ext
import discord.ext.commands
from discord.VoteType import VoteType
from models.dbcontainer import DbService
from models.models import Match, User, Guild
from discord.basecommand import BaseCommand
from discord.ext.commands import Bot

class ViewMatches(BaseCommand):
    prefix = "bran matches"
    usage = prefix
    async def process(self, ctx, message: Message, dbservice: DbService):
        if not self.does_prefix_match(self.prefix, message.content):
            return
        
        with dbservice.Session() as session: 
            open_matches = session.query(Match).filter(Match.finished == False).all()
            context: discord.ext.commands.Context = await ctx(message)
            bot: Bot = context.bot
            for open_match in open_matches:
                embedVar = await ViewMatches.generate_embed_for_match(open_match, bot)
                await message.reply(embed=embedVar)

            if len(open_matches) == 0:
                await message.reply("No pending matches")

    @staticmethod
    async def generate_embed_for_match(match: Match, bot: Bot):
        embedVar = discord.Embed(title=f"id: {match.match_id}", description="", color=0xccccff)
        embedVar.set_author(name="ARAM in progress", icon_url="https://i.imgur.com/RXKFjqo.png")
        
        embedVar.add_field(name="\u200b", value="", inline=False)
        embedVar.add_field(name="Players: ", value="", inline=False)
        for match_player in match.match_players:
            discord_id = match_player.league_user.discord_user.user_id
            discord_user = await bot.fetch_user(discord_id)
            embedVar.add_field(name=str(discord_user.display_name), value=str(match_player.champion), inline=True)
        
        embedVar.add_field(name="\u200b", value="", inline=False)

        embedVar.add_field(name="Votes placed: ", value="", inline=False)
        for vote in match.votes:
            discord_user = await bot.fetch_user(vote.voter.user_id)
            embedVar.add_field(name=f"{VoteType(vote.type_of_vote).name}", value=f"{discord_user.display_name} {vote.brancoins}", inline=False)
        
        embedVar.add_field(name="\u200b", value="", inline=False)

        vote_time_left_seconds = 5*60 - match.get_time_since_start().seconds
        vote_time_left_seconds = vote_time_left_seconds if vote_time_left_seconds >= 0 else 0
        embedVar.add_field(name="Time left to vote: ", value = str(vote_time_left_seconds) + "s", inline=False)

        return embedVar