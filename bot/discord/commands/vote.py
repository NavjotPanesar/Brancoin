

from discord import Message
import discord
import discord.ext
import discord.ext.commands
from discord.VoteType import VoteType
from models.dbcontainer import DbService
from models.models import Match, User, Votes
from discord.basecommand import BaseCommand


class AddVote(BaseCommand):
    prefix = "bran vote"
    usage = f"{prefix} [win/lose] [num_coins] [optional: match_id]"
    async def process(self, ctx, message: Message, dbservice: DbService):
        if not self.does_prefix_match(self.prefix, message.content):
            return

        command_breakdown = message.content.split()

        if command_breakdown[2] == "win" or command_breakdown[2] == "lose":
            await self.add_win_loss_vote(dbservice, command_breakdown[2:], message)

    async def add_win_loss_vote(self, db: DbService, arggs, message: discord.Message):
        vote_type = None
        if arggs[0] == "win":
            vote_type = VoteType.WIN
        elif arggs[0] == "lose":
            vote_type = VoteType.LOSE

        if vote_type is None:
            return

        num_coins = int(arggs[1])
        match_id = arggs[2] if 2 < len(arggs) else None

        if num_coins <= 0:
            return

        with db.Session() as session:
            source_user = session.query(User).filter(User.user_id == str(message.author.id), User.guild_id == str(message.guild.id)).first()
            if source_user.brancoins < num_coins:
                await message.reply("Stop doing gamba broke boi")
                return
            source_user.brancoins -= num_coins

            match_fetch_query = session.query(Match).filter(Match.finished == False)
            if match_id:
                match_fetch_query = match_fetch_query.filter(Match.match_id == match_id)
            target_match = match_fetch_query.first()

            for match_player in target_match.match_players:
                if vote_type == VoteType.LOSE and source_user.user_id == match_player.league_user.discord_user.user_id:
                    await message.reply("Leave the throwing to tapson, dufus")
                    return

            if target_match.get_time_since_start().seconds > 5*60:
                await message.reply("Too late idiot")
                return

            new_vote = Votes()
            new_vote.type_of_vote = vote_type.value
            new_vote.processed = False
            new_vote.voter = source_user
            new_vote.brancoins = num_coins
            target_match.votes.append(new_vote)
            
            session.add(source_user)
            session.add(target_match)
            session.commit()
        await message.reply("Vote placed")