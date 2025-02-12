from functools import wraps
from pyrogram import Client, filters
from pyrogram import Client

from asyncio import Lock

handler_lock = Lock()

def exclusive_handler():
    def decorator(func):
        async def wrapper(client, *args, **kwargs):
            async with handler_lock:
                return await func(client, *args, **kwargs)
        return wrapper
    return decorator

@Client.on_message(filters.incoming)
@exclusive_handler()
async def handler(client, message):
    # Your handler code
    await message.copy(message.chat.id)



#@single_handler()
