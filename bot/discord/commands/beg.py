from discord import Message
from models.dbcontainer import DbService
from models.models import User
from discord.basecommand import BaseCommand


class Beg(BaseCommand):
    prefix = "bran uwu pwease gimme"
    usage = prefix
    dum_cache = []
    async def process(self, ctx, message: Message, dbservice: DbService):
        if not self.does_prefix_match(self.prefix, message.content):
            return
        with dbservice.Session() as session: 
            guy = session.query(User).filter(User.user_id == str(message.author.id), User.guild_id == str(message.guild.id)).first()
            if guy and guy.brancoins <= 0  and guy.id not in self.dum_cache:
                guy.brancoins = 10
                session.add(guy)
                session.commit()
                self.dum_cache.append(guy.id)
                await message.reply(f"Enjoy, you brokie \n {self.custom_emoji * 10}")