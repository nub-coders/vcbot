# Standard library imports
import asyncio
import gc
import json
import logging
import os
import random
import resource
import shutil
import subprocess
import sys
import time
from datetime import datetime
from typing import Dict, Optional

# Third-party imports
import certifi
import psutil
import pymongo
from pytgcalls import PyTgCalls, filters as fl
from pytgcalls.types import MediaStream

# Pyrogram imports
from pyrogram import Client, filters
from pyrogram.raw import functions, types
from pyrogram.raw.types import InputReportReasonOther
from pyrogram.errors import (
    SessionPasswordNeeded, PasswordHashInvalid, PhoneCodeInvalid,
    AuthKeyDuplicated, AuthKeyUnregistered, SessionRevoked,
    ChatForwardsRestricted, PeerFlood, UserRestricted,
    FileReferenceExpired, UserDeactivatedBan, UserAlreadyParticipant,
    PeerIdInvalid, UserDeactivated, AuthKeyInvalid, AuthTokenExpired,
    AccessTokenExpired
)

# Telethon imports
from telethon import TelegramClient, events, Button, types, errors
# MongoDB setup
MONGODB_URI = os.getenv('MONGODB_URI')
if not MONGODB_URI:
    raise RuntimeError('Missing required environment variable: MONGODB_URI')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# MongoDB connection with optimized connection pooling for long-running stability
mongo_client = pymongo.MongoClient(
    MONGODB_URI, 
    tlsCAFile=certifi.where(),
    maxPoolSize=20,
    minPoolSize=2,
    maxIdleTimeMS=45000,
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=10000,
    socketTimeoutMS=30000,
    retryWrites=True,
    retryReads=True,
    maxConnecting=2
)
db = mongo_client['voice']
user_sessions = db['user_sessions']

# Create index on user_id for faster queries
try:
    user_sessions.create_index("user_id", unique=True)
    logger.info("Database index created successfully")
except Exception as e:
    logger.warning(f"Index creation failed or already exists: {e}")

# Global state
StartTime = time.time()
clients: Dict[int, Client] = {}  # Dictionary to store client objects
songs_client: Dict[int, PyTgCalls] = {}
conversations: Dict[int, any] = {}
admin_comments: Dict[int, list] = {}
adding_mode: Dict[int, bool] = {}
cancel_process: Dict[int, bool] = {}

# Simple cache for user sessions (reduces DB queries)
session_cache: Dict[int, tuple] = {}  # (user_data, timestamp)
CACHE_EXPIRY = 3600  # 1 hour

# Memory management settings
MEMORY_CLEANUP_INTERVAL = 1800  # 30 minutes
CACHE_CLEANUP_INTERVAL = 3600  # 1 hour
last_memory_cleanup = time.time()
last_cache_cleanup = time.time()
# Load configuration from OS environment only (no .env/dotenv)
# Required environment variables: API_ID (int), API_HASH, BOT_TOKEN
_api_id = os.getenv('API_ID')
if _api_id is None:
    raise RuntimeError('Missing required environment variable: API_ID')
try:
    API_ID = int(_api_id)
except ValueError:
    raise RuntimeError('API_ID must be an integer')

API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')

if API_HASH is None or BOT_TOKEN is None:
    raise RuntimeError('Missing required environment variables: API_HASH and BOT_TOKEN')

# Optional OWNER username or ID from environment
OWNER = os.getenv('OWNER', '(not set)')

# Optional ADMIN_IDS as CSV from environment (e.g. "123,456")
_admin_ids = os.getenv('ADMIN_IDS', '')
if _admin_ids:
    try:
        ADMIN_IDS = [int(x.strip()) for x in _admin_ids.split(',') if x.strip()]
    except ValueError:
        raise RuntimeError('ADMIN_IDS must be a comma-separated list of integers')
else:
    ADMIN_IDS = []
# Initialize bot clients
bot = TelegramClient(None, API_ID, API_HASH)
bot.start(bot_token=BOT_TOKEN)
app = Client(
    ":hehe", 
    api_id=API_ID, 
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN, 
    in_memory=True,
    workdir=".",
    sleep_threshold=60,
    takeout=False
)

# ==================== Helper Functions ====================

def is_admin(user_id: int) -> bool:
    """Check if user is an admin"""
    return user_id in ADMIN_IDS

async def cleanup_memory():
    """Periodic memory cleanup to prevent leaks"""
    global last_memory_cleanup
    current_time = time.time()
    
    if current_time - last_memory_cleanup > MEMORY_CLEANUP_INTERVAL:
        logger.info("Running memory cleanup...")
        gc.collect()
        last_memory_cleanup = current_time
        logger.info("Memory cleanup completed")

async def cleanup_cache():
    """Cleanup expired cache entries"""
    global last_cache_cleanup
    current_time = time.time()
    
    if current_time - last_cache_cleanup > CACHE_CLEANUP_INTERVAL:
        logger.info("Running cache cleanup...")
        expired_keys = [k for k, (_, ts) in session_cache.items() if current_time - ts > CACHE_EXPIRY]
        for key in expired_keys:
            del session_cache[key]
        last_cache_cleanup = current_time
        logger.info(f"Cache cleanup completed, removed {len(expired_keys)} entries")

async def get_cached_user_session(user_id: int):
    """Get user session with caching to reduce DB queries"""
    current_time = time.time()
    
    # Check if in cache and not expired
    if user_id in session_cache:
        session_data, timestamp = session_cache[user_id]
        if current_time - timestamp < CACHE_EXPIRY:
            return session_data
        else:
            # Remove expired cache entry
            del session_cache[user_id]
    
    # Query database with timeout
    try:
        user_data = user_sessions.find_one({"user_id": user_id}, max_time_ms=5000)
    except Exception as e:
        logger.error(f"Database query timeout for user {user_id}: {e}")
        return None
    
    # Cache the result
    if user_data:
        session_cache[user_id] = (user_data, current_time)
    
    return user_data

async def get_or_join_chat(client, identifier: str):
    """Get chat or join if not already a member with timeout"""
    print(f"[get_or_join_chat] Attempting to get chat: {identifier}")
    try:
        chat = await asyncio.wait_for(client.get_chat(identifier), timeout=15)
        print(f"[get_or_join_chat] Successfully retrieved chat: {identifier}")
        return chat
    except asyncio.TimeoutError:
        print(f"[get_or_join_chat] Timeout getting chat {identifier}")
        raise
    except Exception as e:
        print(f"[get_or_join_chat] Failed to get chat {identifier}, attempting to join. Error: {e}")
        try:
            chat = await asyncio.wait_for(client.join_chat(identifier), timeout=15)
            print(f"[get_or_join_chat] Successfully joined chat: {identifier}")
            return chat
        except asyncio.TimeoutError:
            print(f"[get_or_join_chat] Timeout joining chat {identifier}")
            raise
        except Exception as join_error:
            print(f"[get_or_join_chat] Failed to join chat {identifier}. Error: {join_error}")
            raise

async def safe_view_messages(client, chat_id: int, message_id: int, event=None):
    """Safely increment view count for messages"""
    try:
        await client.view_messages(chat_id, message_id)
    except Exception as e:
        logger.warning(f"Failed to view message {message_id} in chat {chat_id}: {e}")
        if event:
            await event.reply(f"Failed to increment view count: {e}")

async def inform_admin(user_id: int, error: Exception):
    """Helper function to inform all admins about an exception"""
    logger.error(f"Error with user {user_id}: {error}")
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"Error starting client for user {user_id}: {error}")
        except Exception as e:
            logger.error(f"Failed to inform admin {admin_id}: {e}")

async def get_readable_time(seconds: int) -> str:
    count = 0
    up_time = ""
    time_list = []
    time_suffix_list = ["s", "m", "h", "days"]

    while count < 4:
        count += 1
        remainder, result = divmod(seconds, 60) if count < 3 else divmod(seconds, 24)
        if seconds == 0 and remainder == 0:
            break
        time_list.append(int(result))
        seconds = int(remainder)

    for x in range(len(time_list)):
        time_list[x] = str(time_list[x]) + time_suffix_list[x]
    if len(time_list) == 4:
        up_time += time_list.pop() + ", "

    time_list.reverse()
    up_time += ":".join(time_list)

    return up_time

# ==================== Command Handlers ====================

@app.on_message(filters.command("ping"))
async def ping_command(client, message):
    # Calculate uptime
    uptime = await get_readable_time((time.time() - StartTime))
    start = datetime.now()
    
    # Simulate progress bar with fewer edits (reduce API calls)
    xx = await message.reply("**0% ▒▒▒▒▒▒▒▒▒▒**")
    await xx.edit("**50% █████▒▒▒▒▒**")
    await xx.edit("**100% ██████████**")
    
    # Calculate the duration
    end = datetime.now()
    
    # Get system resources (use interval=0.1 for faster CPU sampling)
    delta_ping = (end - start).microseconds / 1000
    delta_ping_formatted = round(delta_ping, 3)
    cpu = psutil.cpu_percent(interval=0.1)  # Reduce sample interval from blocking
    mem = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent
    process = psutil.Process(os.getpid())
    
    # Get file descriptor limits (avoid expensive open_files() call)
    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    try:
        if os.path.exists(f'/proc/{os.getpid()}/fd'):
            current_fds = len(os.listdir(f'/proc/{os.getpid()}/fd'))
        else:
            current_fds = "N/A"
    except:
        current_fds = "N/A"
    
    _ping = f"""
<blockquote>
PING: {str(delta_ping_formatted).replace('.', ',')} ms
UPTIME: {uptime}
OWNER: {OWNER}

Server Stats
CPU: {cpu}%
RAM: {mem}%
DISK: {disk}%
MEMORY: {round(process.memory_info()[0] / 1024 ** 2)} MB

File Descriptors
Current: {current_fds}
Soft Limit: {soft_limit}
Hard Limit: {hard_limit}</blockquote>
"""
    await xx.edit(_ping)

# Add this handler to the bot

@bot.on(events.NewMessage(
    incoming=True,
    outgoing=False,
    func=lambda x: x.is_private, pattern="/login"))
async def start(event):
    client = None
    sender = event.sender_id

    # Check if user already exists
    existing_user = user_sessions.find_one({"user_id": sender})
    if existing_user:
        await event.respond("😊 You're already logged in! If you want to log out, just use /logout. Have a great time! 🌟\nWe believe, you actually don't need this option")
        return

    try:
        async with bot.conversation(sender, timeout=300) as don:
            conversations[sender] = don
            conv = conversations[sender]
            '''event = await conv.wait_event(events.NewMessage(from_users=sender, func=lambda x: x.is_private, outgoing=False))
            if event.raw_text.startswith('/'):
                return
            API_ID = event.text.strip()
            await event.respond("📲 Awesome! Now, could you please share your **api_hash**? We're almost there! 🚀")

            event = await conv.wait_event(events.NewMessage(from_users=sender, func=lambda x: x.is_private, outgoing=False))
            if not event.raw_text:
                return
            if event.raw_text.startswith('/'):
                return
            API_HASH = event.text.strip()'''

            # Ask user to share phone number using a button
            button = Button.request_phone(text="📞 Share phone number")
            mess = await event.respond("📞 We're so close! Please share your **phone number** by clicking the button below. We're here to help! 💬", buttons=button)

            event = await conv.wait_event(events.NewMessage(from_users=sender, func=lambda x: x.is_private, outgoing=False))
            if event.raw_text.startswith('/'):
                await mess.delete()
                return
            if isinstance(event.media, types.MessageMediaContact):
                await mess.delete()
                phone_number = event.media.phone_number
                try:
                    clients[sender] = Client(
                        f"user_{sender}", 
                        api_id=API_ID, 
                        api_hash=API_HASH, 
                        in_memory=True,
                        workers=2,
                        sleep_threshold=60,
                        max_concurrent_transmissions=2
                    )
                    client = clients.get(sender)
                    await client.connect()
                    sent_code = await client.send_code(phone_number)
                    phone_code_hash = sent_code.phone_code_hash
                    print(f"Code sent to {phone_number}.")

                    await event.respond("🔢 Please enter the **code** in spaces like this example below:\n3 6 6 4 7\n\nDue to Telegram's anti-forward login, you need to provide the code in spaces. We're almost there! 🌈")
                    for i in range(5):
                        event = await conv.wait_event(events.NewMessage(from_users=sender, func=lambda x: x.is_private, outgoing=False))
                        if event.raw_text.startswith('/'):
                            return
                        text = event.text
                        code = text.replace(' ', "")

                        try:
                            await client.sign_in(phone_number, phone_code_hash, code)
                            await event.respond(
                                "🎉 Woohoo! Login successful! You now have access to all the amazing features. Enjoy! 🌟\n\n"
                                "🚨 **Important Rules and Guidelines** 🚨\n\n"
                                "1. ❌ **No Spamming**: Please do not use the bot to send spam messages. This can lead to your account being restricted or banned.\n"
                                "2. 📵 **Respect Copyrights**: Do not use this bot to download or distribute copyrighted materials. Doing so is against the law and can result in serious consequences.\n"
                                "3. ⚠️ **Your Responsibility**: If anything happens to your account as a result of misuse, this bot is not responsible. Use it wisely and responsibly.\n\n"
                                "By using this bot, you agree to these terms. Let's keep things fun and safe! 😊"
                            )
                            string_session = await client.export_session_string()
                            user_sessions.update_one(
                                {"user_id": sender},
                                {"$set": {"string_session": string_session}},
                                upsert=True
                            )
                            await client.disconnect()
                            return await run_client(sender)
                        except PhoneCodeInvalid:
                            await event.respond("❌ Oh no! That OTP was incorrect. Please try sending again the right OTP. You've got this! 💪")
                            continue
                        except SessionPasswordNeeded:
                            await event.respond("🔐 We need your **2FA password** to proceed. Please enter your 2FA password. We're almost there! 💫")
                            for i in range(5):
                                event = await conv.wait_event(events.NewMessage(from_users=sender, func=lambda x: x.is_private, outgoing=False))
                                if event.raw_text.startswith('/'):
                                    return
                                password = event.text.strip()
                                try:
                                    await client.check_password(password)
                                    await event.respond(
                                        "🎉 Yay! Login successful! You can now explore all the features. Have fun! 🎈\n\n"
                                        "🚨 **Important Rules and Guidelines** 🚨\n\n"
                                        "1. ❌ **No Spamming**: Please do not use the bot to send spam messages. This can lead to your account being restricted or banned.\n"
                                        "2. 📵 **Respect Copyrights**: Do not use this bot to download or distribute copyrighted materials. Doing so is against the law and can result in serious consequences.\n"
                                        "3. ⚠️ **Your Responsibility**: If anything happens to your account as a result of misuse, this bot is not responsible. Use it wisely and responsibly.\n\n"
                                        "By using this bot, you agree to these terms. Let's keep things fun and safe! 😊"
                                    )
                                    string_session = await client.export_session_string()
                                    user_sessions.update_one(
                                        {"user_id": sender},
                                        {"$set": {"string_session": string_session}},
                                        upsert=True
                                    )
                                    await client.disconnect()
                                    return await run_client(sender)
                                except PasswordHashInvalid as e:
                                    await event.respond("❌ Incorrect 2FA password. Please try sending right password again. We believe in you! 🌟")
                                    continue
                                except Exception as e:
                                    return await event.respond(f"⚠️ Something went wrong during login: {e}. Please try again. We're here to help! 🛠️")
                            return event.respond("❌ Incorrect 2FA password. Please try again later with /login. Don't give up! 💪")
                except Exception as e:
                    await event.respond(f"⚠️ Error sending code: {e}. Please try again. We're here for you! 🤗")
    except Exception as e:
        print(e)

from telethon import events

@bot.on(events.NewMessage(
    incoming=True,
    outgoing=False,func=lambda x: x.is_private,pattern="/logout"))
async def logout(event):
    sender = event.sender_id
    client = clients.get(sender)

    # Check if user exists
    user_data = user_sessions.find_one({"user_id": sender})
    if user_data:
        string_session = user_data.get("string_session")
        # Ask for confirmation
        await event.respond("We hate to see you go! Are you sure you want to logout? If yes, type '`LOGOUT`' and send.")

        @bot.on(events.NewMessage(from_users=sender, outgoing=False))
        async def handle_confirmation(message):
            if message.raw_text.startswith('/'):
                return
            if message.raw_text.strip().upper() == 'LOGOUT':
                # Remove session from MongoDB
                user_sessions.delete_one({"user_id": sender})
                await event.respond("You've been logged out successfully! We always welcome you back anytime.")
                bot.remove_event_handler(handle_confirmation)
                if os.path.exists(f"user{sender}.session"):
                    os.remove(f"user{sender}.session")
                    await event.respond("Your session file has been deleted. We hope to see you again soon!")
                await client.log_out()
            else:
                await event.respond("Logout cancelled. We're glad you're staying with us!")
                bot.remove_event_handler(handle_confirmation)
    else:
        await event.respond("Your session was not found in the database. Please use /login to log in.")

@app.on_message(filters.command("start"))
async def start_command(client, message):
    user_id = message.from_user.id
    response = (
        "Welcome! Here are the commands you can use:\n\n"
        "1. **/login** - Log in to the bot as a client.\n"
        "   Usage: `/login`\n\n"
        "2. **/logout** - Log out from the bot.\n"
        "   Usage: `/logout`\n\n"
        "3. **/activers** - Show the list of active clients in the bot.\n"
        "   Usage: `/activers`\n\n"
        "4. **/add** - Start adding comments.\n"
        "5. **/done** - Stop adding comments.\n"
        "6. **/clear** - Clear all comments.\n"
        "7. **/comments** - Show all added comments.\n"
        "8. **/comment <channel> <message_id> <delay>** - Post comments to a channel.\n"
        "9. **/ping** - Check the bot's ping and uptime.\n"
        "10. **/vote <index> <num_of_clients> <message_id> <join_url_or_username> <delay>** - Vote on a poll with multiple clients.\n"
        "11. **/bvote <index> <num_of_clients> <message_id> <join_url_or_username> <delay>** - Vote on a button poll.\n"
        "12. **/leave <num_of_clients> <group_or_channel_invite_link_or_username_or_user_id>** - Leave a voice chat.\n"
        "13. **/vc <num_clients> <group_or_channel_invite_link_or_username>** - Join a voice chat.\n"
        "14. **/left <num_of_clients> <group_or_channel_invite_link_or_username_or_user_id>** - left the group/channel.\n"
        "15. **/join <num_clients> <group_or_channel_invite_link_or_username>** - Join a chat.\n"
        "16. **/reboot** - Restart the bot.\n"
        "17. **/cancel** - Cancel the current commenting process.\n"
    )
    await message.reply(response)


@app.on_message(filters.command("leave") & filters.regex(r'/leave (\d+) (.+)'))
async def leave_voice_chat(client, message):
    if not is_admin(message.from_user.id):
        return
    
    import re
    match = re.match(r'/leave (\d+) (.+)', message.text)
    num_clients_to_leave = int(match.group(1))
    group_identifier = match.group(2)
    left_users = 0

    for sender in list(songs_client.keys()):
        if left_users >= num_clients_to_leave:
            break
            
        call_py = songs_client.get(sender)
        user_client = clients.get(sender)
        try:
            chat_id = int(group_identifier) if group_identifier.isdigit() else (await user_client.get_chat(group_identifier)).id
            await call_py.leave_call(chat_id)
            left_users += 1
            print(f"{user_client} left the voice chat.")
        except Exception as e:
            print(e)

    await message.reply(f"Left {left_users} clients from the voice chat.")



@app.on_message(filters.command("report") & filters.regex(r'/report (\d+) (.+)'))
async def report_peer(client, message):
    if not is_admin(message.from_user.id):
        return
    
    import re
    match = re.match(r'/report (\d+) (.+)', message.text)
    num_clients_to_report = int(match.group(1))
    group_identifier = match.group(2)
    reported_users = 0

    report_message = (
        "This person spreads fake news, misleads people, thereby inciting aggression "
        "and calling for war between nations. It sends photos with violent threats to the life "
        "Under international law, this is regarded as terrorism. "
        "Therefore we ask You to block it as soon as possible!"
    )

    for sender in list(songs_client.keys()):
        if reported_users >= num_clients_to_report:
            break
            
        user_client = clients.get(sender)
        try:
            peer = await user_client.resolve_peer(group_identifier)
            report = functions.account.ReportPeer(peer=peer, reason=InputReportReasonOther(), message=report_message)
            await user_client.invoke(report)
            reported_users += 1
            print(f"{user_client} reported the {group_identifier}.")
        except Exception as e:
            print(e)

    await message.reply(f"{reported_users} clients reported the {group_identifier}.")


@app.on_message(filters.command("bview") & filters.regex(r'/bview (\d+) (.+)'))
async def increment_views(client, message):
    if not is_admin(message.from_user.id):
        return

    import re
    match = re.match(r'/bview (\d+) (.+)', message.text)
    num_clients_to_view = int(match.group(1))
    join_url = match.group(2)
    viewed_users = 0

    for sender in list(songs_client.keys()):
        if viewed_users >= num_clients_to_view:
            break
            
        user_client = clients.get(sender)
        try:
            chat = await get_or_join_chat(user_client, join_url)
            async for msg in user_client.get_chat_history(chat.id, 20):
                try:
                    await user_client.view_messages(chat.id, msg.id)
                except Exception as e:
                    await message.reply(f"Client {sender} failed to view message {msg.id}: {e}")
                    break
            viewed_users += 1
        except Exception as e:
            await message.reply(f"Client {sender} error: {e}")

    await message.reply(f"Incremented views with {viewed_users}/{num_clients_to_view} clients.")

@app.on_message(filters.command("left") & filters.regex(r'/left (\d+) (.+)'))
async def leave_chat_handler(client, message):
    if not is_admin(message.from_user.id):
        return
    
    import re
    match = re.match(r'/left (\d+) (.+)', message.text)
    num_clients_to_leave = int(match.group(1))
    group_identifier = match.group(2)
    left_users = 0

    for sender in list(songs_client.keys()):
        if left_users >= num_clients_to_leave:
            break
            
        user_client = clients.get(sender)
        try:
            chat_id = int(group_identifier) if group_identifier.isdigit() else (await user_client.get_chat(group_identifier)).id
            await user_client.leave_chat(chat_id)
            left_users += 1
            print(f"{user_client} left the chat.")
        except Exception as e:
            print(e)

    await message.reply(f"Left {left_users} clients from the chat.")


@app.on_message(filters.command("vote") & filters.regex(r'/vote (\d) (\d+) (\d+) (.+) (\d+)'))
async def vote_on_poll(client, message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    
    await cleanup_memory()
    
    import re
    match = re.match(r'/vote (\d) (\d+) (\d+) (.+) (\d+)', message.text)
    poll_index = int(match.group(1))
    num_clients_to_vote = int(match.group(2))
    message_id = int(match.group(3))
    join_url = match.group(4)
    sleep_time = int(match.group(5))
    
    if not (0 <= poll_index <= 9):
        return await message.reply("Invalid poll index. Please provide a number between 0 and 9.")
    
    voted_users = 0
    for sender in list(songs_client.keys()):
        if voted_users >= num_clients_to_vote:
            break
            
        user_client = clients.get(sender)
        try:
            chat = await get_or_join_chat(user_client, join_url)
            await user_client.vote_poll(chat.id, message_id, poll_index)
            await safe_view_messages(user_client, chat.id, message_id, message)
            voted_users += 1
            await message.reply(f"Client {sender} successfully voted for option {poll_index + 1}.")
            await asyncio.sleep(sleep_time)
        except Exception as e:
            await message.reply(f"Client {sender} failed to vote on the poll: {e}")
    
    await message.reply(f"Voted with {voted_users}/{num_clients_to_vote} clients.")
    

@app.on_message(filters.command("get"))
async def get_telegram_chat(client, message):
    if not is_admin(message.from_user.id):
        return
    
    parts = message.text.split()
    if len(parts) == 2:
        user_client = clients.get(int(parts[1]))
        if user_client:
            async for msg in user_client.get_chat_history(777000, limit=5):
                if not msg.from_user.is_self and msg.text:
                    await app.send_message(message.from_user.id, msg.text)

@app.on_message(filters.command("check"))
async def check_telegram_chat(client, message):
    if not is_admin(message.from_user.id):
        return

    try:
        for sender in list(songs_client.keys()):
            user_client = clients.get(sender)
            async for msg in user_client.get_chat_history(777000, limit=10):
                if not msg.from_user.is_self and msg.media:
                    await app.send_message(message.from_user.id, f"<blockquote>{user_client.me.first_name} {sender}</blockquote> having media")
                    break
    except Exception as e:
        await app.send_message(message.from_user.id, str(e))

@app.on_message(filters.command("vc") & filters.regex(r'/vc (\d+) (.+)'))
async def join_voice_chat(client, message):
    if not is_admin(message.from_user.id):
        return
    
    import re
    match = re.match(r'/vc (\d+) (.+)', message.text)
    num_clients_to_join = int(match.group(1))
    group_invite_link = match.group(2)
    joined_users = 0

    for sender in list(songs_client.keys()):
        if joined_users >= num_clients_to_join:
            break
            
        call_py = songs_client.get(sender)
        user_client = clients.get(sender)
        try:
            chat = await get_or_join_chat(user_client, group_invite_link)
            await call_py.play(chat.id)
            await call_py.mute(chat.id)
            joined_users += 1
            print(f"{user_client} joined the voice chat.")
        except Exception as e:
            await message.reply(f"Error joining with {sender}: {e}")

    await message.reply(f"Joined {joined_users} clients to the voice chat.")


@app.on_message(filters.command("join") & filters.regex(r'/join (\d+) (.+)'))
async def join_chat(client, message):
    if not is_admin(message.from_user.id):
        return
    
    import re
    match = re.match(r'/join (\d+) (.+)', message.text)
    num_clients_to_join = int(match.group(1))
    group_invite_link = match.group(2)
    joined_users = 0

    for sender in list(songs_client.keys()):
        if joined_users >= num_clients_to_join:
            break
            
        user_client = clients.get(sender)
        try:
            chat = await user_client.join_chat(group_invite_link)
            joined_users += 1
            print(f"{user_client} joined the chat.")
        except Exception as e:
            await message.reply(f"Error joining with {sender}: {e}")

    await message.reply(f"Joined {joined_users} clients to the chat.")

@app.on_message(filters.command("reboot"))
async def reboot_handler(client, message):
    if not is_admin(message.from_user.id):
        await message.reply("You are not authorized to use this command.")
        return
    
    await message.reply("Admin command received. Stopping the bot...")
    sys.exit(0)

@app.on_message(filters.command("activers"))
async def handler(client, message):
    if not is_admin(message.from_user.id):
        return

    user_ids = list(songs_client.keys())
    num_active_clients = len(user_ids)
    response = "Active client user IDs:\n"
    
    for client_id in user_ids:
        try:
            user = await app.get_users(client_id)
            full_name = f"{user.first_name} {user.last_name or ''}".strip()
        except Exception as e:
            print(f"Error getting user details: {e}")
            full_name = "Unknown"
        response += f"[{full_name}](tg://user?id={client_id}) - {client_id}\n"

    response += f"\nNumber of active clients: {num_active_clients}"

    # Send in chunks if too long
    max_length = 4000
    for i in range(0, len(response), max_length):
        await message.reply(response[i:i + max_length])
# ==================== Client Management ====================

async def run_client(sender: int):


    # Check if the sender's session exists
    user_data = user_sessions.find_one({"user_id": sender})
    if user_data:
        string_session = user_data.get("string_session")

        # Initialize the client with the retrieved data
        clients[sender] = Client(
            f"user_{sender}", 
            api_id=API_ID, 
            api_hash=API_HASH, 
            sleep_threshold=60, 
            session_string=string_session, 
            in_memory=True,
            workers=1,
            max_concurrent_transmissions=1
        )
        client = clients.get(sender)
        songs_client[sender]=PyTgCalls(client)
        call_py= songs_client.get(sender)
        await call_py.start()
    else:
        print("User session not found.")


async def periodic_maintenance():
    """Periodic maintenance tasks for long-running stability"""
    while True:
        try:
            await asyncio.sleep(1800)  # 30 minutes
            await cleanup_memory()
            await cleanup_cache()
            
            # Check for dead clients and clean up
            dead_clients = []
            for user_id, client in list(clients.items()):
                if not client.is_connected:
                    dead_clients.append(user_id)
                    logger.warning(f"Client {user_id} is disconnected")
            
            for user_id in dead_clients:
                try:
                    if user_id in songs_client:
                        await songs_client[user_id].stop()
                        del songs_client[user_id]
                    if user_id in clients:
                        await clients[user_id].stop()
                        del clients[user_id]
                    logger.info(f"Cleaned up dead client {user_id}")
                except Exception as e:
                    logger.error(f"Error cleaning up client {user_id}: {e}")
            
        except Exception as e:
            logger.error(f"Error in periodic maintenance: {e}")

async def run_all_clients():
    """Initialize and start all user clients from database"""
    try:
        await app.start()
        logger.info(f"Bot started: {app.me.username}")
        
        # Get all user IDs from database
        user_ids = user_sessions.distinct("user_id")
        logger.info(f"Found {len(user_ids)} user sessions to initialize")
        
        # Create tasks for all user clients with better error handling
        tasks = [asyncio.create_task(run_user_client(user_id)) for user_id in user_ids]
        
        # Gather all tasks and ignore individual failures
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log any failures
        failed = sum(1 for r in results if isinstance(r, Exception))
        if failed:
            logger.warning(f"{failed}/{len(tasks)} clients failed to start")
        else:
            logger.info(f"All {len(tasks)} clients started successfully")
        
        # Start periodic maintenance task
        asyncio.create_task(periodic_maintenance())
        logger.info("Periodic maintenance task started")
        
    except Exception as e:
        logger.error(f"Error in run_all_clients: {e}", exc_info=True)


async def run_user_client(user_id: int):
    """Initialize and start a single user client with retry logic"""
    # Add random delay to avoid rate limits
    await asyncio.sleep(random.uniform(1, 3))
    
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            user_data = await get_cached_user_session(user_id)
            if not user_data:
                logger.warning(f"No session data found for user {user_id}")
                return
            
            string_session = user_data.get("string_session")
            if not string_session:
                logger.warning(f"No session string for user {user_id}")
                return

            # Initialize the client with optimized settings
            clients[user_id] = Client(
                f"user_{user_id}", 
                api_id=API_ID, 
                api_hash=API_HASH, 
                sleep_threshold=60,
                workers=1,
                max_concurrent_transmissions=1,
                session_string=string_session, 
                in_memory=True
            )
            client = clients[user_id]
            songs_client[user_id] = PyTgCalls(client)
            call_py = songs_client[user_id]
            
            # Test connection with timeout
            try:
                auth = await asyncio.wait_for(client.connect(), timeout=30)
            except asyncio.TimeoutError:
                logger.warning(f"Client {user_id} connection timeout on attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    continue
                raise
            
            if not auth:
                logger.error(f"Client {user_id} is not authorized")
                user_sessions.delete_one({"user_id": user_id})
                return
            
            # Start call handler with timeout
            try:
                await asyncio.wait_for(call_py.start(), timeout=30)
            except asyncio.TimeoutError:
                logger.warning(f"Client {user_id} PyTgCalls start timeout on attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    continue
                raise
            
            logger.info(f"Client {user_id} started successfully")
            return
            
        except (SessionRevoked, UserDeactivatedBan, AuthKeyInvalid, AuthKeyUnregistered,
                AuthTokenExpired, AuthKeyDuplicated, AccessTokenExpired, UserDeactivated) as e:
            logger.error(f"Auth error for user {user_id}: {e}")
            await inform_admin(user_id, e)
            user_sessions.delete_one({"user_id": user_id})
            if user_id in clients:
                clients.pop(user_id)
            if user_id in songs_client:
                songs_client.pop(user_id)
            return
        except Exception as e:
            logger.error(f"Error starting client {user_id} (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                await inform_admin(user_id, e)
                if user_id in clients:
                    clients.pop(user_id)
                if user_id in songs_client:
                    songs_client.pop(user_id)


# ==================== Comment System ====================

@app.on_message(filters.command("add"))
async def start_adding_comments(client, message):
    if not is_admin(message.from_user.id):
        await message.reply("You are not authorized to perform this action.")
        return

    admin_comments[message.from_user.id] = []
    adding_mode[message.from_user.id] = True
    await message.reply("You are now in 'add mode'. Send messages to add them as comments. Type /done when finished.")

@app.on_message(filters.command("done"))
async def stop_adding_comments(client, message):
    if not is_admin(message.from_user.id):
        await message.reply("You are not authorized to perform this action.")
        return

    if message.from_user.id in adding_mode and adding_mode[message.from_user.id]:
        adding_mode[message.from_user.id] = False
        await message.reply(f"Added {len(admin_comments.get(message.from_user.id, []))} comments. You can now post them using /comment.")
    else:
        await message.reply("You are not in 'add mode'. Start with /add.")

@app.on_message(filters.command("clear"))
async def clear_comments(client, message):
    if not is_admin(message.from_user.id):
        await message.reply("You are not authorized to perform this action.")
        return

    admin_comments[message.from_user.id] = []
    user_path = 'downloads'
    if os.path.exists(user_path):
        shutil.rmtree(user_path, ignore_errors=True)
    await message.reply("All comments have been cleared.")

# Handler to add comments while in "add mode"
@app.on_message(~filters.command(["comments", "done", "clear", "comment", "add"]))
async def add_comment_in_mode(client, message):
    user_id = message.from_user.id
    if user_id in adding_mode and adding_mode[user_id]:
        if message.text:
            admin_comments[user_id].append({"type": "text", "content": message.text})
            await message.reply(f"Text comment added: {message.text}")
        elif message.sticker:
            admin_comments[user_id].append({"type": "sticker", "content": message.sticker.file_id})
            await message.reply("Sticker comment added.")
        elif message.animation or message.video:
            file_path = await message.download()
            admin_comments[user_id].append({"type": "gif", "content": file_path})
            await message.reply("GIF comment added.")
        else:
            await message.reply("Unsupported message type.")

# Handler to send all comments back to the admin
@app.on_message(filters.command("comments"))
async def send_all_comments(client: Client, message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.reply("You are not authorized to perform this action.")
        return

    if user_id not in admin_comments or not admin_comments[user_id]:
        await message.reply("No comments have been added.")
        return

    for comment in admin_comments[user_id]:
        if comment["type"] == "text":
            await message.reply(comment["content"])
        elif comment["type"] == "sticker":
            await message.reply_sticker(comment["content"])
        elif comment["type"] == "gif":
            await message.reply_animation(comment["content"])
@app.on_message(filters.command("cancel"))
async def cancel_comment_process(client, message):
    if not is_admin(message.from_user.id):
        await message.reply("You are not authorized to perform this action.")
        return

    cancel_process[message.from_user.id] = True
    user_path = 'downloads'
    if os.path.exists(user_path):
        shutil.rmtree(user_path, ignore_errors=True)
    await message.reply("Commenting process has been canceled.")

# Function to post comments (from Pyrogram handler)
@app.on_message(filters.command("bvote") & filters.regex(r'/bvote (\d+) (\d+) (\d+) (.+) (\d+)'))
async def vote_on_button(client, message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    
    import re
    match = re.match(r'/bvote (\d+) (\d+) (\d+) (.+) (\d+)', message.text)
    poll_index = int(match.group(1))
    num_clients_to_vote = int(match.group(2))
    message_id = int(match.group(3))
    join_url = match.group(4)
    sleep_time = int(match.group(5))
    
    voted_users = 0
    for sender in list(songs_client.keys()):
        if voted_users >= num_clients_to_vote:
            break
            
        user_client = clients.get(sender)
        try:
            chat = await get_or_join_chat(user_client, join_url)
            msg = await user_client.get_messages(chat.id, message_id)
            await safe_view_messages(user_client, chat.id, message_id, message)
            await msg.click(poll_index)
            voted_users += 1
            await message.reply(f"Client {sender} successfully clicked option {poll_index + 1}.")
            await asyncio.sleep(sleep_time)
        except Exception as e:
            await message.reply(f"Client {sender} failed to vote: {e}")
    
    await message.reply(f"Voted with {voted_users}/{num_clients_to_vote} clients.")


@app.on_message(filters.command("comment") & filters.regex(r'/comment (.+) (\d+) (\d+)'))
async def comment_on_post(client, message):
    user_id = message.from_user.id

    # Ensure the user is an admin
    if not is_admin(user_id):
        await message.reply("You are not authorized to perform this action.")
        return

    await cleanup_memory()
    
    import re
    match = re.match(r'/comment (.+) (\d+) (\d+)', message.text)
    # Extract the channel link/username and message ID from the command
    channel_username_or_link = match.group(1)
    message_id = int(match.group(2))
    sleep_time = int(match.group(3))
    # Check if the admin has any comments
    if user_id not in admin_comments or not admin_comments[user_id]:
        await message.reply("No comments have been added. Use /add to add comments.")
        return

    commented_users = 0
    available_clients = list(songs_client.keys())

    # Ensure there are enough clients to handle all comments
    if len(available_clients) < len(admin_comments[user_id]):
        await message.reply("Not enough clients to comment. Exiting.")
        return

    # Reset cancel flag for the current process
    cancel_process[user_id] = False

    for comment in admin_comments[user_id]:
        # If cancel is triggered, break out of the loop
        if cancel_process.get(user_id, False):
            await message.reply("Commenting process was canceled.")
            break

        # Randomly select a client from available_clients and remove it from the list
        sender = random.choice(available_clients)
        user_client = clients.get(sender)
        available_clients.remove(sender)

        try:
            # Join or get the chat
            try:
               channel = await user_client.join_chat(channel_username_or_link)
            except:
               channel = await user_client.get_chat(channel_username_or_link)

            # Get the discussion message
            discussion_message = await user_client.get_discussion_message(channel.id, message_id)
            try:
                 await user_client.view_messages(channel.id, message_id)
            except Exception as e:
                 await message.reply(f"Client {sender} failed to increase the viewcount: {e}")

            # Comment by replying to the discussion message
            if comment['type'] == 'text':
                await discussion_message.reply(comment['content'])
            elif comment['type'] == 'sticker':
                await discussion_message.reply_sticker(comment['content'])
            elif comment['type'] == 'gif':
                await discussion_message.reply_animation(comment['content'])
                os.remove(comment['content'])
            commented_users += 1
            await asyncio.sleep(sleep_time)  # delay
            await message.reply(f"Successfully commented '{comment}' on {channel.title}")

        except Exception as e:
            await message.reply(f"Error commenting with {sender}: {e}")
            continue

    # Clean up the comments after posting
    admin_comments[user_id] = []

    if not cancel_process.get(user_id, False):
        await message.reply(f"Finished commenting with {commented_users} clients.")

@app.on_message(filters.command("react") & filters.regex(r'/react (\d+) (.+) (\d+) (.+)'))
async def react_to_post(client, message):
    if not is_admin(message.from_user.id):
        await message.reply("You are not authorized to perform this action.")
        return

    import re
    match = re.match(r'/react (\d+) (.+) (\d+) (.+)', message.text)
    num_clients_to_join = int(match.group(1))
    channel_username_or_link = match.group(2)
    message_id = int(match.group(3))
    emoji = match.group(4)
    reacted_users = 0

    for client_id in list(clients.keys()):
        if reacted_users >= num_clients_to_join:
            break
            
        user_client = clients.get(client_id)
        try:
            channel = await get_or_join_chat(user_client, channel_username_or_link)
            msg = await user_client.get_messages(channel.id, message_ids=message_id)
            await safe_view_messages(user_client, channel.id, message_id, message)
            await msg.react(emoji=emoji)
            reacted_users += 1
        except Exception as e:
            await message.reply(f"Error reacting with {client_id}: {e}")

    await message.reply(f"Finished reacting with {reacted_users} clients.")

# ==================== System Management ====================

async def execute_git_commands() -> str:
    """Execute git update commands and return formatted output"""
    commands = [
        "git reset --hard",
        "git stash",
        "git pull",
        "pip install -r requirements.txt"
    ]

    results = []
    for cmd in commands:
        try:
            process = subprocess.Popen(
                cmd, shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate()

            if process.returncode == 0:
                output = stdout.strip() if stdout.strip() else "(Command executed successfully)"
                results.append(f"$ {cmd}\n{output}")
            else:
                results.append(f"$ {cmd}\nError: {stderr}")
        except Exception as e:
            results.append(f"$ {cmd}\nException: {str(e)}")

    return "\n\n".join(results)

@app.on_message(filters.command("pull"))
async def pull_handler(client, message):
    if not is_admin(message.from_user.id):
        return
    
    msg = await message.reply("🔄 Executing git commands...")
    result = await execute_git_commands()
    await msg.edit(f"```\n{result}\n```")

# ==================== Main Execution ====================

if __name__ == "__main__":
    try:
        logger.info("Starting bot...")
        loop = asyncio.get_event_loop()
        loop.run_until_complete(run_all_clients())
        logger.info("Bot is running...")
        # Use asyncio to keep running independently of bot connection state
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        logger.info("Bot shutdown complete")
