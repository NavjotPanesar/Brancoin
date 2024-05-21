
from discord import Message
from models.dbcontainer import DbService
from models.models import Guild
from discord.basecommand import BaseCommand

class AdminAddBroadcast(BaseCommand):
    prefix = "bran broadcast"
    usage = prefix
    admin = 114930910884790276
    async def process(self, ctx, message: Message, dbservice: DbService):
        if not self.does_prefix_match(self.prefix, message.content):
            return
        
        if message.author.id != self.admin:
            await message.reply("Unauthorized")
            return

        new_broadcast_channel_id = message.channel.id
        new_broadcast_role = message.role_mentions[0] if len(message.role_mentions) > 0 else None

        with dbservice.Session() as session: 
            guild = session.query(Guild).filter(Guild.guild_id==str(message.guild.id)).first()
            guild.broadcast_channel_id = str(new_broadcast_channel_id)
            guild.broadcast_role_id = str(new_broadcast_role.id)
            session.add(guild)
            session.commit()
            await message.reply("joever")