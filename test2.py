from pyrogram import enums
import datetime
from config import *
from pyrogram.raw.types import DataJSON
import asyncio
from pyrogram import Client
from pyrogram.raw.functions.channels import GetFullChannel
from pyrogram.raw.types import InputPeerChannel
from pyrogram.raw.functions.phone import GetCallConfig, JoinGroupCall
from pyrogram.raw.types import InputPeerSelf
from pyrogram.raw.functions.phone import EditGroupCallParticipant
from pyrogram.raw.types import InputGroupCall
import pymongo
import certifi
USER_ID = int(input("Give user_id please: ")) # Replace with the user ID to fetc>
import datetime
from pyrogram import enums
from pyrogram.errors import FloodWait
import asyncio
import random
import re
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.raw.types import MessageEntityTextUrl, MessageEntityMentionName




# MongoDB setup
mongo_client = pymongo.MongoClient('mongodb+srv://brock:brock123@cluster0.clzne.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')
db = mongo_client['voice']  #Replace 'your_database_name' with your actual database name
user_sessions = db['user_sessions']
user_data = user_sessions.find_one({"user_id": USER_ID})
string_session = user_data.get('string_session')



app = Client("hh", api_id=API_ID, api_hash=API_HASH,session_string=string_session, sleep_threshold=32, in_memory=True,)



# Listen to messages from the specific user @on9wordchainbot in a group context
@app.on_message(filters.command("change") & filters.group)
async def change_call(client,message):
    chat_id = message.chat.id
    message = await message.reply("Changing voice chat settings...")
    try:
        input_channel = await client.resolve_peer(chat_id)
        full_channel = await client.invoke(GetFullChannel(channel=input_channel))
        call = full_channel.full_chat.call

        if not call:
            await message.edit("No active group call found.")
            return
    except ChannelInvalid:
        await message.edit("Invalid channel or group.")
        return
    except Exception as e:
        await message.edit(f"Error retrieving group call: {str(e)}")
        return
    await client.invoke(
                EditGroupCallParticipant(
                    call=call,  # Pass the call object retrieved from messages.ChatFull
                    participant=InputPeerSelf()
                )
            )
    await message.edit("Successfully changed voice chat settings...")
# Listen to messages from the specific user @fuckk_uh_deeply in a group context

# Run the client
app.run()
