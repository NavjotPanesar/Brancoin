

from discord import Message
import discord
from models.dbcontainer import DbService
from models.models import User
from discord.basecommand import BaseCommand
from discord.ext.commands import Bot


class Coins(BaseCommand):
    prefix = "bran board"
    usage = prefix
    lim = 10
    async def process(self, ctx, message: Message, dbservice: DbService):
        if not self.does_prefix_match(self.prefix, message.content):
            return
        
        with dbservice.Session() as session: 
            top_users = session.query(User).filter(User.guild_id==str(message.guild.id)).order_by(User.brancoins.desc()).limit(self.lim).all()
            context = await ctx(message)
            bot: Bot = context.bot

            embedVar = discord.Embed(title="Braincoin leaderboard", description=f"Top {str(self.lim)}", color=0xffcccc)
            for user in top_users:
                disc_user = await bot.fetch_user(user.user_id)
                if disc_user is not None:
                    embedVar.add_field(name=str(disc_user.display_name), value=f"{self.custom_emoji} {str(user.brancoins)}", inline=False)
            
            await message.reply(embed=embedVar)