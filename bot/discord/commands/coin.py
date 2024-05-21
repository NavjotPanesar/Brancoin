

from discord import Message
import discord
from models.dbcontainer import DbService
from models.models import User
from discord.basecommand import BaseCommand


class Coin(BaseCommand):
    prefix = "bran coin"
    usage = prefix
    async def process(self, ctx, message: Message, dbservice: DbService):
        if not self.does_prefix_match(self.prefix, message.content):
            return
        
        with dbservice.Session() as session: 
            guy = session.query(User).filter(User.user_id == str(message.author.id), User.guild_id == str(message.guild.id)).first()
            if guy:
                embedVar = discord.Embed(title="Brancoins", description="", color=0xffcccc)
                embedVar.set_author(name=message.author.nick, icon_url=message.author.display_avatar.url)
                embedVar.add_field(name="Total Brancoins", value=str(guy.brancoins), inline=False)
                if guy.league_users and len(guy.league_users) > 0:
                    for league_user in guy.league_users:
                        embedVar.add_field(name="LoL tag", value=league_user.tag, inline=False)
                        embedVar.add_field(name="LoL username", value=league_user.summoner_name, inline=False)
                        membership_text = ""
                        if league_user.trackable:
                            membership_text = membership_text + "Clown, "
                        if league_user.voteable:
                            membership_text = membership_text + "RSquad, "
                        if not league_user.voteable and not league_user.trackable:
                            membership_text = "None"
                        membership_text = membership_text.rstrip(", ")
                        embedVar.add_field(name="Group Membership", value=membership_text, inline=False)
                else:
                    embedVar.add_field(name="Lol account", value="Not connected", inline=False)
                await message.reply(embed=embedVar)
            else:
                await message.reply("Who are you?")