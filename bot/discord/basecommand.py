
import enum
import shlex
from envvars import Env


class BaseCommand():
    custom_emoji = "<:brancoin:1233204357550575636>" if Env.is_debug == "false" else "<:test:1230694305937756160>"
    async def process(self, ctx, message):
        raise NotImplementedError("Please Implement this method")
    
    def does_prefix_match(self, prefix: str, message: str):
        split_prefix = prefix.split()
        split_message = message.split()
        if len(split_message) < len(split_prefix):
            return False
        for idx, segment_prefix in enumerate(split_prefix):
            if segment_prefix.lower() != split_message[idx].lower():
                return False
        return True
    
    def get_arg_stack(self, prefix: str, message: str):
        message_breakdown = shlex.split(message.content)
        args = message_breakdown[len(prefix.split()):]
        return args
