from pyrogram import enums
import datetime
from config import *
from pyrogram.raw.types import DataJSON
import asyncio
from pyrogram import Client
from pyrogram.raw.functions.channels import GetFullChannel
from pyrogram.raw.types import InputPeerChannel
from pyrogram.raw.functions.phone import GetCallConfig, JoinGroupCall
from pyrogram.raw.types import InputGroupCall
import pymongo
import certifi

# MongoDB setup
mongo_client = pymongo.MongoClient('mongodb+srv://brock:brock123@cluster0.clzne.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')
db = mongo_client['voice']  #Replace 'your_database_name' with your actual database name
user_sessions = db['user_sessions']
# Async function to extract string session and join group call
async def join_group_call(api_id, api_hash, user_id, group_id):
    # Fetch the string session from MongoDB
    user_data = user_sessions.find_one({"user_id": user_id})
    if not user_data:
        print("User session not found in the database.")
        return

    string_session = user_data.get('string_session')
    if not string_session:
        print("No string session found for the user.")
        return

    # Initialize the Pyrogram Client with string session
    async with Client("hh", api_id=api_id, api_hash=api_hash, session_string=string_session, sleep_threshold=32, in_memory=True, no_updates=True) as client:
        try:
           await status(client)
        except Exception as e:
            print(f"Error occurred: {e}")
            # Resolve the group peer

# Define your API credentials and target group
USER_ID = int(input("Give user_id please: ")) # Replace with the user ID to fetch the session
GROUP_ID = -1001806816712  # Replace with your target group ID
import datetime
from pyrogram import enums
from pyrogram.errors import FloodWait
import asyncio

async def status(client):
    start = datetime.datetime.now()

    u = 0  # Private messages count
    g = 0  # Groups count
    sg = 0  # Supergroups count
    c = 0  # Channels count
    b = 0  # Bots count
    um = 0  # Unread mentions count
    up = 0  # Unread messages count
    total_messages_sent = 0  # Total messages sent by the user
    top_chat = None  # To store the top chat
    top_chat_messages = 0  # To store the message count for the top chat
    last_24_hours = datetime.datetime.now() - datetime.timedelta(days=1)

    # Store message counts in a dictionary for chats
    message_counts = {}

    async for dialog in client.get_dialogs():
        um += dialog.unread_mentions_count
        up += dialog.unread_messages_count
        
        if dialog.chat.type == enums.ChatType.PRIVATE:
            u += 1
        elif dialog.chat.type == enums.ChatType.BOT:
            b += 1
        elif dialog.chat.type == enums.ChatType.GROUP:
            g += 1
        elif dialog.chat.type == enums.ChatType.SUPERGROUP:
            sg += 1
            user_s = await dialog.chat.get_member(int(client.me.id))
            if user_s.status in (
                enums.ChatMemberStatus.OWNER,
                enums.ChatMemberStatus.ADMINISTRATOR,
            ):
                a_chat += 1
        elif dialog.chat.type == enums.ChatType.CHANNEL:
            c += 1

        try:
            async for message in client.get_chat_history(dialog.chat.id, limit=10):  # Limit to last 10 messages
                if message.from_user and message.from_user.id == client.me.id:
                    total_messages_sent += 1
                    if message.date >= last_24_hours:
                        message_counts[dialog.chat.id] = message_counts.get(dialog.chat.id, 0) + 1

        except FloodWait as e:
            await asyncio.sleep(e.x)  # Wait for the specified amount of time
            continue  # Retry processing the next dialog

    # Determine the top chat
    for chat_id, count in message_counts.items():
        if count > top_chat_messages:
            top_chat_messages = count
            top_chat = await client.get_chat(chat_id)

    end = datetime.datetime.now()
    ms = (end - start).seconds

    print(
        """`Your Stats Obtained in {} seconds`
<blockquote>`You have {} Private Messages.`
`You are in {} Groups.`
`You are in {} Super Groups.`
`You Are in {} Channels.`
`You Are Admin in {} Chats.`
`Bots = {}`
`Total Messages Sent = {}`
`Top Chat: {} ({} messages in the last 24 hours)`
`Unread messages {}`
`Unread mentions {}`</blockquote>""".format(
            ms, u, g, sg, c, a_chat, b, total_messages_sent, 
            top_chat.title if top_chat else "N/A", top_chat_messages, 
            up, um
        )
    )

# Run the async function
if __name__ == "__main__":
    asyncio.run(join_group_call(API_ID, API_HASH, USER_ID, GROUP_ID))
