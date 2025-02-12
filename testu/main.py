
import sys
import asyncio
from pytgcalls import filters as call_filters
import os
from tools import *
from config import *
from fonts import *
from pyrogram import enums
from pyrogram import Client, filters
from pytgcalls.types import ChatUpdate
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message, ChatPrivileges
from pyrogram.enums import ChatType, ChatMemberStatus
import importlib
from telethon import  Button
from pyrogram.errors.exceptions import InviteHashExpired , ChannelPrivate ,GroupcallForbidden, AccessTokenExpired, UserDeactivated
from pyrogram.errors.exceptions import SessionRevoked, UserDeactivatedBan, AuthKeyInvalid, AuthKeyUnregistered, SessionRevoked, AuthTokenExpired, AuthKeyDuplicated
from pytgcalls.exceptions import NotInCallError
import time
import queue
import certifi
import datetime
import random
from pytgcalls.exceptions import (
    AlreadyJoinedError,
    NoActiveGroupCall,
)
import base64
import subprocess
import re
import json
from pytgcalls import idle, PyTgCalls
from pytgcalls.types import AudioQuality
from pytgcalls.types import MediaStream
from pytgcalls.types import VideoQuality
from telethon import TelegramClient, events, errors
import yt_dlp
# Define the main bot client (app)
import random
import string

def generate_client_id():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10))


# Auth handler
@bot.on(events.NewMessage(
    incoming=True,
    outgoing=False,
    func=lambda x: x.is_private, pattern="/host"))
async def host_handler(event):
   user_bot_token = None
   user_id = event.sender_id
   existing_user = user_sessions.find_one({"user_id": user_id})
   if existing_user:
        return await event.reply("😊 You're already logged in to the bot!\nYou can use /restart to restart your music bot or /logout to lougout from bot")
    # Prompt user for bot token
   prem = is_premium(user_id)
   if not prem:
      try:
         await stop_user(user_id)
      except:
           pass
      return await event.respond(f"""
<b>🚫 Your Trial /plans Has Ended</b>

<blockquote><b>💡 Get Premium</b>: Purchase one of our premium plans to continue enjoying exclusive features.</blockquote>

👉 Check out /plans for more details."""
,parse_mode="html")

   prompt_message = None
   try:
      async with bot.conversation(user_id, timeout=60) as don:
        conversations[user_id] = don
        conv = conversations[user_id]
        prompt_message = await conv.send_message("Please send the bot token to authorize your bot. You have 60 seconds to respond.\nUse @BotFather to get bot token")
        # Wait for the user's response with a timeout of 60 seconds
        event = await conv.get_response()
        user_bot_token = event.text
        if user_bot_token in user_sessions.distinct("bot_token"):
            return await event.reply("This bot already in use\nTry with another bot token")

        try:
            # Create and start the user client using the bot token
            user_client = Client(
                f"{generate_client_id()}",
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=user_bot_token,in_memory=True, sleep_threshold=32
            )
            await user_client.start()
            client_name = f"{user_client.me.first_name} {user_client.me.last_name or ''}".strip()
            owners[user_client.me.id] = user_id
            await event.respond(f"Bot authorized successfully! 🎉 Authorized as: @{user_client.me.username}")
            await user_client.stop(block=False)
            temporary[user_id] = user_bot_token
        except Exception as e:
            await event.reply(f"Failed to authorize the bot. Error: {e}")
            if user_id in clients:
                clients.pop(user_id)
            return

   except asyncio.TimeoutError:
        await prompt_message.edit("Timed out! Please use /host again to start over.")
        try:
           user_client = temporary.get(user_id)
           clients.pop(user_id)
           await user_client.stop(block=False)
        except:
           pass
        return
   await asyncio.sleep(2)
   try:
     async with bot.conversation(user_id, timeout=60) as don:
        conversations[user_id] = don
        conv = conversations[user_id]
        # Prompt for session string
        session_prompt = await conv.send_message(f"Send your assistant's string session within 60 seconds.", buttons=[Button.url("Generate session str","https://t.me/nub_Session_gen_bot")],parse_mode="html")
        event = await conv.get_response()
        user_session_string = event.text
        if user_session_string in user_sessions.distinct("string_session"):
            try:
               user_client = clients.get(user_id)
               await user_client.stop(block=False)
            except:
                  pass
            return await event.reply("This userbot already in use\nTry with another userbot string session")

        try:
            user_client = Client(
                f"{generate_client_id()}",
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token= temporary[user_id], workers =5,
                plugins=dict(root="plugins"),in_memory=True,
    sleep_threshold=30,  # Increased from default 10
            )
            clients[user_id] = user_client
            bot_maintenance = asyncio.create_task(
            maintain_connection(
                user_id=user_id,
                client=user_client,
                is_bot=True,
                check_interval=100,  # 5 minutes
                retry_delay=60       # 1 minute
            )
        )
        
            # Create and start the session client
            session_client = Client(
                f"user_{user_id}_session",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=user_session_string,
                workers =1,in_memory=True, sleep_threshold=32)
            auth = await session_client.connect()
            if not auth:
                 try:
                      user_client = clients.get(user_id)
                      await user_client.stop(block=False)
                 except:
                    pass
                 print(f"Client is not authorized for {user_id}. Please authorize first.")
            await session_client.disconnect()
            call_py = PyTgCalls(session_client)
            clients[f"{user_id}_session"] = session_client
            call_py.add_handler(end, call_filters.stream_end)
            call_py.add_handler(hd_stream_closed_kicked, call_filters.chat_update(ChatUpdate.Status.CLOSED_VOICE_CHAT) | call_filters.chat_update(ChatUpdate.Status.KICKED))
            await user_client.start()
            await call_py.start()
            await asyncio.sleep(2)
            songs_client[session_client.me.id] = call_py
            client_name = f"{session_client.me.first_name} {session_client.me.last_name or ''}".strip()
            await event.reply(f"Session string authorized successfully! 🎉 Authorized as: {client_name}")
            try:
                   await session_client.join_chat("nub_coder_s")
                   await session_client.join_chat("nub_coder_updates")
            except:
                   pass

            # Add to connector dictionary
            connector[user_client.me.username] = user_id
            queues[f"dic_{user_client.me.id}"] = {}
            linkage[session_client.me.id] = user_client
            active[user_client.me.username] = []

            # Add play handler to user_client using MessageHandler
            user_sessions.update_one({"user_id": user_id},
                                        {"$set": {"string_session": user_session_string,'bot_token': user_bot_token}},
                                        upsert=True
                                    )
            user_client = clients.get(user_id)
            await event.respond(f"Your music bot is ready 🎉\n start your bot: @{user_client.me.username}")
            drem = is_dremium(user_id)
            if not drem:
                    storre_user(user_id, int(time.time()) + (2 * 24 * 60 * 60))
                    await bot.send_message(user_id, f"Congratulations👏🎉,\nYour bot's premium trial activated for 48 hours.")
                    pass
            session_maintenance = asyncio.create_task(
            maintain_connection(
                user_id=user_id,
                client=session_client,
                is_bot=False,
                check_interval=100,  # 5 minutes
                retry_delay=60       # 1 minute
            )
        )
        
        except Exception as e:
            try:
                      user_client = clients.get(user_id)
                      await user_client.stop(block=False)
            except:
                pass
            await event.reply(f"Failed to authorize with the session string. Error: {e}")
            if user_id in clients:
                clients.pop(user_id)
            return

   except asyncio.TimeoutError:
        await session_prompt.edit("Timed out! Please use /host again to start over.")
        try:
           user_client = clients.get(user_id)
           clients.pop(user_id)
           await user_client.stop(block=False)
        except:
           pass
        return

async def remove_active_chat(user_client, chat_id):
    if chat_id in active[user_client.me.username]:
        active[user_client.me.username].remove(chat_id)



def storre_user(user_id, timestamp):
    collection.update_one(
        {"user_id": user_id},
        {"$set": {"timestamp": timestamp}},
        upsert=True
    )

import asyncio
import logging
from typing import Optional
from pyrogram import Client

async def maintain_app( client: Client,  
                            check_interval: int = 60, retry_delay: int = 60, 
                            max_retries: int = 3) -> None:
    """
    Maintains connection for both bot and session clients with proper validation.
    
    Args:
        user_id: Telegram user ID
        client: The Pyrogram Client instance to maintain
        is_bot: Whether this is a bot client (True) or session client (False)
        check_interval: Time between connection checks in seconds
        retry_delay: Time to wait between retry attempts in seconds
        max_retries: Maximum number of consecutive retry attempts
    """
    consecutive_failures = 0
    
    while True:
        try:
            # First check if user_id exists in clients dict
            # Connection check
            try:
                await client.get_me()
                print(f"Connection check successful for app client of user @{client.me.username} ")
                consecutive_failures = 0
            except Exception as e:
                print(f"Connection check failed, attempting to reconnect: {str(e)}")
                
                # Stop client
                try:
                    await client.stop(block=False)
                except Exception as e:
                    print(f"Error stopping client: {e}")
                
                # Attempt to reconnect
                try:
                    await client.start()
                    # Verify connection
                    await client.get_me()
                    print(f"Successfully reconnected app client for user @{client.me.username}")
                    consecutive_failures = 0
                except Exception as e:
                    raise ConnectionError(f"Failed to verify connection: {e}")

            await asyncio.sleep(check_interval)
            
        except Exception as e:
            if str(e) == 'Client is already connected':
                  continue
            consecutive_failures += 1
            print(f"Connection maintenance failed (attempt {consecutive_failures}) for user @{client.me.username}: {str(e)}")
            
            # If max retries reached, try to notify admins
            if consecutive_failures >= max_retries:
                print(f"Maximum retry attempts ({max_retries}) reached for user @{client.me.username}")
                
                # Try to notify admins
                admin_file = f"{ggg}/admin.txt"
                if os.path.exists(admin_file):
                    with open(admin_file, "r") as file:
                        admin_ids = [int(line.strip()) for line in file.readlines()]
                        for admin_id in admin_ids:
                            try:
                                await bot.send_message(
                                    admin_id, 
                                    f"Connection maintenance failed for user @{client.me.username} "
                                    f": {str(e)}"
                                )
                            except Exception:
                                pass
                await asyncio.sleep(retry_delay * 2)
                consecutive_failures = 0
            else:
                await asyncio.sleep(retry_delay)

async def maintain_connection(user_id: int, client: Client, is_bot: bool = False, 
                            check_interval: int = 60, retry_delay: int = 60, 
                            max_retries: int = 3) -> None:
    """
    Maintains connection for both bot and session clients with proper validation.
    
    Args:
        user_id: Telegram user ID
        client: The Pyrogram Client instance to maintain
        is_bot: Whether this is a bot client (True) or session client (False)
        check_interval: Time between connection checks in seconds
        retry_delay: Time to wait between retry attempts in seconds
        max_retries: Maximum number of consecutive retry attempts
    """
    consecutive_failures = 0
    
    while True:
        try:
            # First check if user_id exists in clients dict
            if user_id not in clients:
                print(f"User {user_id} not found in clients dictionary. Stopping maintenance.")
                break

            # Get the appropriate client for comparison
            if is_bot:
                stored_client = clients.get(user_id)
                if not stored_client or stored_client.name != client.name:
                    print(f"Bot client mismatch for user {user_id}. Stopping maintenance.")
                    break
            else:
                stored_client = clients.get(f"{user_id}_session")
                if not stored_client or stored_client.name != client.name:
                    print(f"Session client mismatch for user {user_id}. Stopping maintenance.")
                    break

            # Connection check
            try:
                await client.get_me()
                print(f"Connection check successful for {'bot' if is_bot else 'session'} client of user {user_id}")
                consecutive_failures = 0
            except Exception as e:
                print(f"Connection check failed, attempting to reconnect: {str(e)}")
                
                # Stop client
                try:
                    await client.stop(block=False)
                except Exception as e:
                    print(f"Error stopping client: {e}")
                
                # Attempt to reconnect
                try:
                    await client.start()
                    # Verify connection
                    await client.get_me()
                    print(f"Successfully reconnected {'bot' if is_bot else 'session'} client for user {user_id}")
                    consecutive_failures = 0
                except Exception as e:
                    raise ConnectionError(f"Failed to verify connection: {e}")

            await asyncio.sleep(check_interval)
            
        except Exception as e:
            if str(e) == 'Client is already connected':
                  continue
            consecutive_failures += 1
            print(f"Connection maintenance failed (attempt {consecutive_failures}) for user {user_id}: {str(e)}")
            
            # If max retries reached, try to notify admins
            if consecutive_failures >= max_retries:
                print(f"Maximum retry attempts ({max_retries}) reached for user {user_id}")
                
                # Try to notify admins
                admin_file = f"{ggg}/admin.txt"
                if os.path.exists(admin_file):
                    with open(admin_file, "r") as file:
                        admin_ids = [int(line.strip()) for line in file.readlines()]
                        for admin_id in admin_ids:
                            try:
                                await app.send_message(
                                    admin_id, 
                                    f"Connection maintenance failed for user {user_id} "
                                    f"({'bot' if is_bot else 'session'} client): {str(e)}"
                                )
                            except Exception:
                                pass
                
                # Try to notify user
                try:
                    await bot.send_message(
                        user_id,
                        f"Connection maintenance failed for your {user_id} "
                        f"{'bot' if is_bot else 'session'} client:\n{str(e)}"
                    )
                except Exception:
                    pass
                
                await asyncio.sleep(retry_delay * 2)
                consecutive_failures = 0
            else:
                await asyncio.sleep(retry_delay)



def is_admin(user_id):
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id in admin_ids:
                return True

from telethon import TelegramClient, events
import asyncio
import traceback
import os

@bot.on(events.NewMessage(pattern='/trace'))
async def check_clients_command(event):
    """Command to check and maintain all client connections"""
    user_id = event.sender_id

    # Check if the user is an admin
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                await event.respond("🚫 You are not authorized to use this command.")
                return

    # Send initial message and get message object for editing
    status_msg = await event.respond(
        "🔍 Checking client connections...\n\n"
        "📋 Legend:\n"
        "✅ = Passed check\n"
        "❌ = Failed check\n"
        "Each client has 3 connection checks:"
        " Connect -> Restart -> Reinitialize\n"
    )
    
    results = await check_clients(user_id, status_msg)
    await status_msg.edit(f"{status_msg.text}\n\n{results}")

async def check_clients(admin_id, status_msg):
    """Check and maintain all client connections with live updates"""
    report = []
    total_clients = int(len(clients)//2)
    processed = 0

    for user_id, client in list(clients.items()):
        if not str(user_id).isdigit():
            continue

        processed += 1
        emoji_status = ["✅", "✅", "✅"]  # 3 check system
        try:
            if not await is_connected(client):
                # First show checking status
                status_line = f"Client {user_id}: (⟳⟳⟳)"
                await status_msg.edit(f"{status_msg.text}\n{status_line}")
                await asyncio.sleep(0.2)
                
                # Then update with actual status
                emoji_status = await handle_disconnected_client(user_id, client, emoji_status)
                status_line = f"Client {user_id}: ({''.join(emoji_status)})"
            else:
                status_line = f"Client {user_id}: (✅✅✅)"
        
        except Exception as e:
            status_line = f"Client {user_id}: (❌❌❌) [Error: {str(e)}]"

        # Update progress with proper line breaks
        progress = f"{processed}" if total_clients > 0 else ""
        new_line = f"{progress} {status_line}"
        report.append(new_line)
        
        # Edit message with organized formatting
        await status_msg.edit(
            f"{status_msg.text.split('・')[0]}\n" +  # Keep original header
            "\n".join(report)  # New line-separated list
        )
        await asyncio.sleep(0.3)

    completion_text = "✅ Client check completed!"
    return f"\n\n{report}\n\n{completion_text}"


async def handle_disconnected_client(user_id, client, emoji_status):
    """Handle reconnection attempts and modify status emojis"""
    # First check: Normal connect
    try:
        await client.connect()
        if await is_connected(client):
            return emoji_status  # All checks passed
    except Exception:
        emoji_status[0] = "❌"

    # Second check: Restart
    try:
        await client.restart()
        if await is_connected(client):
            return emoji_status
    except Exception:
        emoji_status[1] = "❌"

    # Final check: Full reinitialization
    try:
        await restart_client(user_id)
        return emoji_status  # Keep existing status (some checks failed but operation succeeded)
    except Exception:
        emoji_status[2] = "❌"
        return emoji_status


async def is_connected(client):
    """Check if client is properly connected"""
    try:
        return await client.get_me() is not None
    except Exception as e:
        print(f"Connection check failed: {str(e)}")
        return False



async def restart_client(user_id):
    """Full client restart procedure"""
    try:
        # Stop existing client
        if user_id in clients:
            old_client = clients.pop(user_id)
            await old_client.stop(block=False)
        
        # Reinitialize from scratch
        await run_user(user_id)
    except Exception as e:
        raise Exception(f"Restart failed: {str(e)}")

# Add this to your bot startup
    
    # Start Telethon monitor bot
@bot.on(events.NewMessage(pattern='/bheekh'))
async def loud_message(event):
    user_id = event.sender_id

    # Check if the user is an admin by comparing their user ID with the ones in admin.txt
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return

    # Get all stored user IDs from MongoDB
    stored_user_ids = [user["user_id"] for user in collection.find()]
    xx=0
    try:
       reply_message =(
                    "Your trial /plans plan has been ended\n"
                    "You need to purchase our premium plans\n\n"
                    "Checkout /plans to more")
       if reply_message:
            for user_id in stored_user_ids:
               prem = is_premium(user_id)
               if not prem:
                    await asyncio.sleep(2)
                    try:
                        await bot.send_message(user_id, reply_message)
                        xx+=1
                    except Exception as e:
                        print(f"Failed to forward message: {e}")
            await event.respond(f"Broadcasted to {xx} users")
    except Exception as e:
            print(f"Failed to forward message: {e}")

@bot.on(events.NewMessage(pattern='/repo'))
async def handle_repo(event):
    caption = """Why not code it yourself? 😎

Helpful Resources:
- Telethon Docs: https://docs.telethon.dev
- Pyrogram Docs: https://docs.pyrogram.org
- Python-Telegram-Bot: https://python-telegram-bot.org
- Telegram Bot API: https://core.telegram.org/bots/api

Start building yourself! 🚀"""

    # Replace 'path/to/repo.mp4' with your actual video file path
    video_path = 'repo.mp4'
    
    try:
        await bot.send_file(
            event.chat_id,
            video_path,
            caption=caption,
            reply_to=event.message.id
        )
    except Exception as e:
        await event.reply("Error sending video. Please try again later.")


from pyrogram.enums import ChatMemberStatus, ChatType

@bot.on(events.NewMessage(
    incoming=True,
    outgoing=False,
    func=lambda x: x.is_private, 
    pattern=r"/set_log_group"))
async def handle_log_group(event):
    sender = event.sender_id
    user_data = user_sessions.find_one({"user_id": sender})
    
    if not user_data:
        return await event.respond(f"**MF\n\nTHIS IS OWNER'S COMMAND...**")

    user_client = clients.get(sender)
    if not user_client:
        return await event.respond("Error: Client session not found.")

    message_text = event.message.message
    match = re.match(r"/set_log_group\s+(-?\d+)", message_text)
    
    if not match:
        return await event.reply(
            "Invalid command. Correct Usage:\n"
            "/set_log_group <group/channel ID>"
        )

    group_id = int(match.group(1))

    try:
        chat = await user_client.get_chat(group_id)
        
        try:
            bot_member = await user_client.get_chat_member(
                chat_id=group_id,
                user_id=user_client.me.id
            )
        except Exception:
            return await event.reply(
                "Error: I'm not a member of this group/channel. "
                "Please add me first."
            )

        if bot_member.status not in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
            return await event.reply(
                f"Error: @{user_client.me.username} need to be an admin in the group/channel to set it as log group."
            )

        # Define required permissions based on chat type
        required_permissions = ["can_delete_messages", "can_restrict_members"]
        if chat.type == enums.ChatType.CHANNEL:
            required_permissions.append("can_post_messages")

        missing_permissions = [
            perm for perm in required_permissions 
            if not getattr(bot_member.privileges, perm, False)
        ]

        if missing_permissions:
            formatted_permissions = "\n".join(f"- {perm.replace('_', ' ').title()}" 
                                           for perm in missing_permissions)
            return await event.reply(
                "Error: Missing required permissions. Please grant these permissions:\n"
                f"{formatted_permissions}"
            )

        members_count = await user_client.get_chat_members_count(group_id)
        set_gvar(sender, "log_group", str(group_id))
        
        chat_type = "Channel" if chat.type == enums.ChatType.CHANNEL else "Group"
        response = f"**Successfully set log {chat_type.lower()}!**\n\n"
        response += f"**Chat Details:**\n"
        response += f"• Name: {chat.title}\n"
        response += f"• ID: `{group_id}`\n"
        response += f"• Type: {chat_type}\n"
        response += f"• Username: @{chat.username if chat.username else 'Private Group/Channel'}\n"
        response += f"• Total Members: {members_count}\n"
        response += f"• Description: {chat.description or 'No description'}\n"
        
        try:
            test_msg = await user_client.send_message(
                chat_id=group_id,
                text="🔄 Testing log group permissions... ✅"
            )
            await test_msg.delete()
            response += "\n✅ **Permission Test:** Successful"
        except Exception:
            response += "\n⚠️ **Warning:** Could not send test message"

        await event.reply(response)

    except Exception as e:
        error_message = str(e).lower()
        if "not found" in error_message:
            await event.reply(f"Error: Invalid group/channel ID or @{user_client.me.username} cannot access it.")
        elif "kicked" in error_message:
            await event.reply(f"Error: @{user_client.me.username} is banned from this group/channel.")
        else:
            await event.reply(
                f"Error: Unable to set log group. Make sure:\n"
                "1. The ID is correct\n"
                f"2. @{user_client.me.username} is member of the group/channel\n"
                f"3. @{user_client.me.username} have required admin permissions\n"
                f"Error details: {str(e)}"
            )

@bot.on(events.NewMessage(
    incoming=True,
    outgoing=False,
    func=lambda x: x.is_private, pattern=r"/set_support"))
async def handle_url(event):
    client = app
    sender = event.sender_id
    user_data = user_sessions.find_one({"user_id": sender})
    if not user_data:
      return await event.respond(f"**MF\n\nTHIS IS OWNER'S COMMAND...**")

    # Extract the URL from the message
    message_text = event.message.message
    match = re.match(r"/set_support\s+(http[s]?://[^\s]+)", message_text)
    if match:
        url = match.group(1)  # Extract the URL
        print(f"Detected URL: {url}")
        await event.reply(f"SUCCESSFULLY CHANGED SUPPORT CHAT TO: {url}")
        set_gvar(sender, "support", url)
    else:
        await event.reply(f"Invalid command. Correct Usage:\n"
                                       "/set_support <group/channel link>")
    # Check if user exists



@bot.on(events.NewMessage(pattern='/loud'))
async def loud_message(event):
    user_id = event.sender_id

    # Check if the user is an admin by comparing their user ID with the ones in admin.txt
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return

    # Get all stored user IDs from MongoDB
    stored_user_ids = [user["user_id"] for user in collection.find()]
    xx=0
    if event.is_reply:
        try:
            reply_message = await event.get_reply_message()
            if reply_message:
                for user_id in stored_user_ids:
                    await asyncio.sleep(2)
                    try:
                        await bot.forward_messages(user_id, reply_message)
                        xx+=1
                    except Exception as e:
                           print(f"Failed to forward message: {e}")
                await event.respond(f"Broadcasted to {xx} users")
        except Exception as e:
            print(f"Failed to forward message: {e}")


@bot.on(events.NewMessage(pattern='/users'))
async def list_users(event):
    user_id = event.sender_id

    # Check if the user is an admin by comparing their user ID with the ones in admin.txt
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return
    user_ids = [str(user["user_id"]) for user in collection.find()]
    if user_ids:
        user_list = "\n".join(user_ids)

        user_list += f"\nTotal users: {str(len(user_ids))}"
        chunk_size = 4000
        chunks = [user_list[i:i+chunk_size] for i in range(0, len(user_list), chunk_size)]
        for chunk in chunks:
            await event.respond(chunk)
    else:
        await event.respond("No users found.")

def get_user_id_by_client(user_id, client):
  for id in clients:
    if id == user_id:
      user_client = clients.get(user_id)
      if user_client.me.id == client.me.id:
          return client.me.id
  return False

def get_owner_id_by_client(client):
    """Returns the user ID associated with the given client object.  Returns None if not found."""
    try:
      for user_id, user_client in clients.items():
        if user_client.me and user_client.me.id == client.me.id:  #Directly compare client objects
            return user_id
    except:
      user_id = owners.get(client.me.id)
      return user_id

from pyrogram import Client, filters
import asyncio
import datetime
from pyrogram import enums








@app.on_message(filters.command("gc"))
async def gc_handler(client, message):
    
    if not is_admin(message.from_user.id):
        return await message.reply(f"**MF\n\nTHIS IS OWNER'S COMMAND...**")
    objects_before = len(gc.get_objects())
    
    # Perform garbage collection
    start_time = time.time()
    collected = gc.collect()
    gc_time = time.time() - start_time
    
    # Get count after collection
    objects_after = len(gc.get_objects())
    await message.reply_text(f"""
✅ Garbage collection completed!

Collected {collected} objects
Objects before: {objects_before}
Objects after: {objects_after}
Collection time: {gc_time:.2f} seconds""")

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# Store temporary format selections
stored_format = {}

def get_format_keyboard(current_format: int):
    """Generate format selection keyboard with current selection marked"""
    keyboard = []  # Create 4 rows of buttons

    # Create buttons for numbers 1 to 15
    for i in range(0, 16, 4):
        row = []
        for j in range(1, 5):
            num = i + j
            # Mark selected format with brackets
            text = f"[{num}]" if num == current_format else str(num)
            row.append(InlineKeyboardButton(text, callback_data=f"format_{num}"))
        keyboard.append(row)

    # Add the last button for '16' and 'Done' in the last row
    keyboard.append([InlineKeyboardButton("Done ✅", callback_data="format_done")])

    return InlineKeyboardMarkup(keyboard)

def format_message(format_num: int):
    """Generate preview message showing current format"""
    queue_preview = queue_styles[format_num].format(superscript("MUSIC"), superscript("Sample Title"), "3:45", "1")
    play_preview = play_styles[format_num].format(superscript("MUSIC"), superscript("Sample Title"), "3:45", "User")
    
    return (
        "Selected format:\n"
        "───────────────\n"
        f"<blockquote>Queue Format:</blockquote>\n{queue_preview}\n\n"
        f"<blockquote>Play Format:</blockquote>\n{play_preview}"
    )
@app.on_message(filters.command("format"))
async def format_command(client, message):
    """Handle /format command"""
    owner_id = message.from_user.id
    user_data = user_sessions.find_one({"user_id": owner_id})
    if not user_data:
        return await message.reply("User data not found. Please /host first.")

    
    # Get current format with proper error handling
    try:
        format_value = gvarstatus(owner_id, "format")
        if format_value is not None:
            current_format = int(format_value)
        else:
            current_format = stored_format.get(owner_id, 16)
    except ValueError:
        current_format = stored_format.get(owner_id, 16)
    
    # Create preview message with format selection keyboard
    await message.reply(
        format_message(current_format),
        reply_markup=get_format_keyboard(current_format)
    )

@app.on_callback_query(filters.regex("^format_"))
async def format_callback(client, callback_query: CallbackQuery):
    """Handle format selection callbacks"""
    owner_id = callback_query.from_user.id
    data = callback_query.data.split("_")[1]
    user_data = user_sessions.find_one({"user_id": owner_id})
    if not user_data:
        return await callback_query.answer("User data not found. Please /host first.")
    if data == "done":
        # Check if user has selected a format
        if owner_id in stored_format:
            # Save the format
            set_gvar(owner_id, "format", str(stored_format[owner_id]))
            await callback_query.message.edit_text(
                f"✅ Format style #{stored_format[owner_id]} has been saved!"
            )
            # Clean up temporary storage
            stored_format.pop(owner_id, None)
        else:
            await callback_query.answer(
                "❌ Please select a format first!",
                show_alert=True
            )
        return
    
    # Handle number button clicks
    format_num = int(data)
    stored_format[owner_id] = format_num
    
    # Update message with new format preview
    await callback_query.message.edit_text(
        format_message(format_num),
        reply_markup=get_format_keyboard(format_num)
    )
    
    await callback_query.answer(f"Selected format style #{format_num}")



from typing import Dict, List, Optional, Tuple, NamedTuple
from pyrogram import Client, filters, enums
from pyrogram.types import Message, Chat
import asyncio

class BotStats(NamedTuple):
    """Container for bot statistics including identification info."""
    bot_id: int
    username: str
    count: int

@bot.on(events.NewMessage(pattern=r"(?i)/stats"))
async def all_stats_handler(event):
    """Handler for /stats command that aggregates stats across all clients."""
    if not is_admin(event.sender_id):
        await event.reply("**MF\n\nTHIS IS OWNER'S COMMAND...**")
        return

    loading_message = await event.reply("Getting stats please wait...")
    start = datetime.datetime.now()

    # Filter out inactive clients and get their stats
    client_stats = []
    for user_id, client_instance in clients.items():
        try:
            if client_instance.me and client_instance.me.id:
                await asyncio.sleep(2)
                stats = await get_client_stats(client_instance)
                if stats:
                    client_stats.append((
                        client_instance.me.id,
                        client_instance.me.username,
                        stats
                    ))
        except Exception:
            continue

    # Aggregate total stats
    total_stats = {
        'private': 0,
        'groups': 0,
        'supergroups': 0,
        'channels': 0,
        'admin': 0
    }

    # Find top performers with usernames
    top_performers = {
        'private': BotStats(0, "", 0),
        'groups': BotStats(0, "", 0),
        'supergroups': BotStats(0, "", 0),
        'channels': BotStats(0, "", 0),
        'admin': BotStats(0, "", 0)
    }

    # Calculate totals and find top performers
    for bot_id, username, stats in client_stats:
        for key in total_stats:
            total_stats[key] += stats[key]
            if stats[key] > top_performers[key].count:
                top_performers[key] = BotStats(bot_id, username or "No username", stats[key])

    await loading_message.delete()
    
    elapsed_seconds = (datetime.datetime.now() - start).seconds
    
    # Format the main stats message
    response = (
    f"<b>🏆 Multi-Bot Performance Report</b>\n"
    f"<b>━━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
    f"🔢 <b>Analyzed Bots:</b> <code>{int(len(client_stats)//2)}</code>\n"
    f"⏱ <b>Collection Time:</b> <code>{elapsed_seconds}s</code>\n\n"
    
    f"<b>📈 Combined Statistics</b>\n"
    f"┌─────────────────────────────\n"
    f"│ 🔒 <b>Private Chats:</b> <code>{total_stats['private']:,}</code>\n"
    f"│ 👥 <b>Groups:</b> <code>{total_stats['groups']:,}</code>\n"
    f"│ 🌐 <b>Super Groups:</b> <code>{total_stats['supergroups']:,}</code>\n"
    f"│ 📢 <b>Channels:</b> <code>{total_stats['channels']:,}</code>\n"
    f"│ 👑 <b>Admin Positions:</b> <code>{total_stats['admin']:,}</code>\n"
    f"└─────────────────────────────\n\n"
    
    f"<b>🏅 Top Performers</b>\n"
    f"▫️ <b>Private Chat King:</b>\n"
    f"   @{top_performers['private'].username} (<code>{top_performers['private'].count:,}</code>)\n\n"
    f"▫️ <b>Group Dominator:</b>\n"
    f"   @{top_performers['groups'].username} (<code>{top_performers['groups'].count:,}</code>)\n\n"
    f"▫️ <b>Supergroup Leader:</b>\n"
    f"   @{top_performers['supergroups'].username} (<code>{top_performers['supergroups'].count:,}</code>)\n\n"
    f"▫️ <b>Admin Supreme:</b>\n"
    f"   @{top_performers['admin'].username} (<code>{top_performers['admin'].count:,}</code>)\n\n"
    
    f"<b>━━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
    f"<i>⚡ Real-time analytics powered by YourBotSystem</i>"
)
    await event.reply(response, parse_mode="html")

async def get_chat_type(client: Client, chat_id: int) -> Optional[enums.ChatType]:
    """Get chat type safely with error handling."""
    try:
        chat = await client.get_chat(chat_id)
        return chat.type
    except FloodWait as e:
        print(f"Rate limited! Sleeping for {e.value} seconds.")
        await asyncio.sleep(e.value)
    except Exception as e:
        print(f"Error getting chat type for {chat_id}: {str(e)}")
        return None

async def get_client_stats(client: Client) -> Optional[Dict[str, int]]:
    """Gets statistics for a single client instance."""
    stats = {
        'private': 0,
        'groups': 0,
        'supergroups': 0,
        'channels': 0,
        'admin': 0
    }

    user_data = collection.find_one({"user_id": client.me.id})
    if not user_data:
        return None

    users: List[int] = user_data.get('users', [])
    
    # Process chats in batches to avoid overwhelming the server
    BATCH_SIZE = 50
    for i in range(0, len(users), BATCH_SIZE):
        batch = users[i:i + BATCH_SIZE]
        chat_types = await asyncio.gather(
            *[get_chat_type(client, chat_id) for chat_id in batch],
            return_exceptions=True
        )
        
        for j, chat_type in enumerate(chat_types):
            if not isinstance(chat_type, enums.ChatType):
                continue

            if chat_type == enums.ChatType.PRIVATE:
                stats['private'] += 1
            elif chat_type == enums.ChatType.GROUP:
                stats['groups'] += 1
            elif chat_type == enums.ChatType.SUPERGROUP:
                stats['supergroups'] += 1
                try:
                    member = await client.get_chat_member(batch[j], client.me.id)
                    if member.status in (
                        enums.ChatMemberStatus.OWNER,
                        enums.ChatMemberStatus.ADMINISTRATOR
                    ):
                        stats['admin'] += 1
                except Exception as e:
                    print(f"Error checking admin status in {batch[j]}: {str(e)}")
            elif chat_type == enums.ChatType.CHANNEL:
                stats['channels'] += 1

    return stats

from telethon import events
from telethon.tl.types import User

@bot.on(events.NewMessage(pattern=r"(?i)/activebots"))
async def activebot_handler(event):
    # Send initial loading message
    loading_message = await event.reply("🔄 <b>Scanning Active Music Bots...</b>",parse_mode="html")

    # Initialize counters
    total_active_voice = 0
    num_active_clients = 0
    paid_users = referral_users = trial_users = 0
    users_data = []

    # Collect and process data
    for user_id in clients:
        try:
            if not str(user_id).isdigit():
                continue

            user_client = clients.get(user_id)
            userbot = clients.get(f"{user_id}_session")
            if not user_client or not userbot:
                continue

            num_active_clients += 1
            status_mess = ''
            premium_by = "TRIAL"
            time_difference = 0

            # Get user data from database
            user_data = collection.find_one({"user_id": user_id})
            if user_data:
                current_time = int(time.time())
                stored_time = user_data.get("timestamp", 0)
                time_difference = stored_time - current_time
                premium_by = user_data.get("premium_by", "TRIAL")

                # Update counters
                if premium_by == "PAID":
                    paid_users += 1
                elif premium_by == "REFERRAL":
                    referral_users += 1
                else:
                    trial_users += 1

                # Calculate time remaining with large value handling
                if time_difference > 0:
                    total_seconds = abs(time_difference)
                    days = total_seconds // (24 * 3600)
                    remaining_seconds = total_seconds % (24 * 3600)
                    hours = remaining_seconds // 3600
                    remaining_seconds %= 3600
                    minutes = remaining_seconds // 60

                    formatted_days = f"{days:,}d " if days > 0 else ""
                    status_mess = f"{formatted_days}{hours}h {minutes}m | {premium_by}"

            # Get user information (first name only)
            user = await bot.get_entity(user_id)
            first_name = (user.first_name or "User").split()[0] if isinstance(user, User) else "User"

            # Get active calls
            call_py = songs_client.get(userbot.me.id)
            active_voice = len(await call_py.group_calls) if call_py else 0
            total_active_voice += active_voice

            # Store user data
            users_data.append({
                'first_name': first_name,
                'bot_username': user_client.me.username if user_client.me else "",
                'active_voice': active_voice,
                'status_mess': status_mess,
                'premium_by': premium_by,
                'time_difference': time_difference
            })

        except Exception as e:
            print(f"Error processing user {user_id}: {str(e)}")
            continue

    # Sort users: PAID > REFERRAL > TRIAL, then by time remaining
    users_data.sort(key=lambda x: (
        {"PAID": 0, "REFERRAL": 1, "TRIAL": 2}[x['premium_by']],
        -x['time_difference']
    ))

    # Build message based on admin status
    if is_admin(event.sender_id):  # Changed from message.from_user.id
        # ADMIN VIEW
        message_text = (
            f"<b>🎵 Active Music Bots Analysis</b>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>📊 Statistics</b>\n"
            f"│ ▪️ <b>Total Bots:</b> <code>{num_active_clients}</code>\n"
            f"│ ▪️ <b>Active Calls:</b> <code>{total_active_voice}</code>\n"
            f"│ ▪️ <b>Paid Users:</b> <code>{paid_users}</code>\n"
            f"│ ▪️ <b>Referral Users:</b> <code>{referral_users}</code>\n"
            f"│ ▪️ <b>Trial Users:</b> <code>{trial_users}</code>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
            f"<b>🔍 Bot List</b>\n"
        )

        # Add bot list entries
        for index, user in enumerate(users_data, start=1):
            status_emoji = {
                "PAID": "💎",
                "REFERRAL": "🎁",
                "TRIAL": "⏳"
            }.get(user['premium_by'], "⏳")

            bot_entry = (
                f"<b>{index}.</b> ━━━━━━━━━━━━━━━━━━━\n"
                f"│ <b>Name:</b> <code>{user['first_name']}</code>\n"
                f"│ <b>Bot:</b> @{user['bot_username']}\n"
                f"│ <b>Active Calls:</b> <code>{user['active_voice']}</code>\n"
            )

            if user['status_mess']:
                bot_entry += f"│ <b>Status:</b> {status_emoji} {user['status_mess']}\n"

            message_text += bot_entry + "\n"

        message_text += f"\n<b>🆔 System ID:</b> <code>{len(clients) //2 }</code>"
    else:
        message_text = (
            f"<b>🎵 Active Music Bots</b>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"│ ▪️ <b>Total Bots:</b> <code>{int(num_active_clients)//2}</code>\n"
            f"│ ▪️ <b>Active Calls:</b> <code>{total_active_voice}</code>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"\n🔒 Detailed statistics are admin-only"
        )

    # Delete loading message and send results
    await loading_message.delete()

    # Split and send message
    max_length = 4096
    for i in range(0, len(message_text), max_length):
        chunk = message_text[i:i + max_length]
        await event.reply(
            chunk,
            parse_mode='html',
            link_preview=False
        )

#@app.on_message(filters.command("activebots"))
async def activebots_handler(client, message: Message):
    # Send initial loading message
    loading_message = await message.reply("🔄 <b>Scanning Active Music Bots...</b>")

    # Initialize counters
    total_active_voice = 0
    num_active_clients = 0
    paid_users = referral_users = trial_users = 0
    users_data = []

    # Collect and process data
    for user_id in clients:
        try:
            if not str(user_id).isdigit():
                continue

            bot = clients.get(user_id)
            userbot = clients.get(f"{user_id}_session")
            if not bot or not userbot:
                continue

            num_active_clients += 1
            status_mess = ''
            premium_by = "TRIAL"
            time_difference = 0

            # Get user data from database
            user_data = collection.find_one({"user_id": user_id})
            if user_data:
                current_time = int(time.time())
                stored_time = user_data.get("timestamp", 0)
                time_difference = stored_time - current_time
                premium_by = user_data.get("premium_by", "TRIAL")

                # Update counters
                if premium_by == "PAID":
                    paid_users += 1
                elif premium_by == "REFERRAL":
                    referral_users += 1
                else:
                    trial_users += 1

                # Calculate time remaining with large value handling
                if time_difference > 0:
                    total_seconds = abs(time_difference)
                    days = total_seconds // (24 * 3600)
                    remaining_seconds = total_seconds % (24 * 3600)
                    hours = remaining_seconds // 3600
                    remaining_seconds %= 3600
                    minutes = remaining_seconds // 60

                    formatted_days = f"{days:,}d " if days > 0 else ""
                    status_mess = f"{formatted_days}{hours}h {minutes}m | {premium_by}"

            # Get user information (first name only)
            user = await client.get_users(user_id)
            first_name = (user.first_name or "User").split()[0]

            # Get active calls
            call_py = songs_client.get(userbot.me.id)
            active_voice = len(await call_py.group_calls) if call_py else 0
            total_active_voice += active_voice

            # Store user data
            users_data.append({
                'first_name': first_name,
                'bot_username': bot.me.username if bot.me else "",
                'active_voice': active_voice,
                'status_mess': status_mess,
                'premium_by': premium_by,
                'time_difference': time_difference
            })

        except Exception as e:
            print(f"Error processing user {user_id}: {str(e)}")
            continue

    # Sort users: PAID > REFERRAL > TRIAL, then by time remaining
    users_data.sort(key=lambda x: (
        {"PAID": 0, "REFERRAL": 1, "TRIAL": 2}[x['premium_by']],
        -x['time_difference']
    ))

    # Build message based on admin status
    if is_admin(message.from_user.id):
        # ADMIN VIEW
        message_text = (
            f"<b>🎵 Active Music Bots Analysis</b>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>📊 Statistics</b>\n"
            f"│ ▪️ <b>Total Bots:</b> <code>{num_active_clients}</code>\n"
            f"│ ▪️ <b>Active Calls:</b> <code>{total_active_voice}</code>\n"
            f"│ ▪️ <b>Paid Users:</b> <code>{paid_users}</code>\n"
            f"│ ▪️ <b>Referral Users:</b> <code>{referral_users}</code>\n"
            f"│ ▪️ <b>Trial Users:</b> <code>{trial_users}</code>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
            f"<b>🔍 Bot List</b>\n"
        )

        # Add bot list entries
        for index, user in enumerate(users_data, start=1):
            status_emoji = {
                "PAID": "💎",
                "REFERRAL": "🎁",
                "TRIAL": "⏳"
            }.get(user['premium_by'], "⏳")

            bot_entry = (
                f"<b>{index}.</b> ━━━━━━━━━━━━━━━━━━━\n"
                f"│ <b>Name:</b> <code>{user['first_name']}</code>\n"
                f"│ <b>Bot:</b> @{user['bot_username']}\n"
                f"│ <b>Active Calls:</b> <code>{user['active_voice']}</code>\n"
            )
            
            if user['status_mess']:
                bot_entry += f"│ <b>Status:</b> {status_emoji} {user['status_mess']}\n"
            
            message_text += bot_entry + "\n"

        message_text += f"\n<b>🆔 System ID:</b> <code>{len(clients) //2 }</code>"
    else:
        # NON-ADMIN VIEW
        message_text = (
            f"<b>🎵 Active Music Bots</b>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"│ ▪️ <b>Total Bots:</b> <code>{int(num_active_clients)//2}</code>\n"
            f"│ ▪️ <b>Active Calls:</b> <code>{total_active_voice}</code>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"\n🔒 Detailed statistics are admin-only"
        )

    # Delete loading message and send results
    await loading_message.delete()
    
    # Split and send message
    max_length = 4096
    for i in range(0, len(message_text), max_length):
        chunk = message_text[i:i + max_length]
        await message.reply(
            text=chunk,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )


def currently_playing(user_client, message):
    song_queue = queues.get(f"dic_{user_client.me.id}")
    try:
        if len(song_queue[message.chat.id]) <=1:
           return False
        return True
    except KeyError:
        True


import datetime
from pyrogram import filters

# Add to existing imports

# Add new handler for tracking played songs
@app.on_message(filters.command("allstreams"))
async def songs_played_handler(client, message):
    jjj = await message.reply("Getting calls.....")
    user_id = message.from_user.id
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if not message.from_user.id in admin_ids:
                 return await message.reply(f"**MF\n\nTHIS IS OWNER'S COMMAND...**")
    twenty_four_hours_ago = datetime.datetime.now() - datetime.timedelta(hours=24)
    bot_stats = []

    # Collect and clean data first
    for user_id in clients:
        try:
            if not str(user_id).isdigit():
                continue

            bot = clients.get(user_id)
            if not bot or not hasattr(bot.me, 'id'):
                continue

            # Clean old entries
            collection.update_one(
                {"user_id": bot.me.id},
                {"$pull": {"dates": {"$lt": twenty_four_hours_ago}}}
            )

            # Get current count
            user_data = collection.find_one({"user_id": bot.me.id})
            play_count = len(user_data.get('dates', [])) if user_data else 0

            if play_count > 0:
                bot_stats.append((play_count, bot.me.username))

        except Exception as e:
            print(f"Error processing bot {user_id}: {e}")

    # Sort in descending order
    bot_stats.sort(reverse=True, key=lambda x: (x[0], x[1]))

    # Build response
    response = "🎵 Top bots in streaming (24 Hours)\n\n"
    total_count = 0
    
    for index, (count, username) in enumerate(bot_stats, start=1):
        response += f"{index}. @{username}: {count} songs\n"
        total_count += count

    if total_count == 0:
        response = "🔇 No media stream in the last 24 hours"
    else:
        response += f"\n📊 Total streams: {total_count}"

    # Send message with pagination
    try:
      await jjj.delete()
    except:
      pass
    max_length = 4096
    for i in range(0, len(response), max_length):
        chunk = response[i:i + max_length]
        await message.reply(chunk)


async def hd_stream_closed_kicked(client, update):
   print(update)
   session_client = client._mtproto
   user_client = linkage.get(session_client.me.id)
   song_queue_key = f"dic_{user_client.me.id}"
   song_queue = queues.get(song_queue_key)
   try:
      await remove_active_chat(user_client, update.chat_id)
      song_queue[update.chat_id].clear()
      playing[update.chat_id].clear()
   except Exception as e:
      print(e)

async def end(client, update):
  session_client = client._mtproto
  user_client = linkage.get(session_client.me.id)
  try:
        collection.update_one(
            {"user_id": user_client.me.id},
            {"$push": {'dates': datetime.datetime.now()}},
            upsert=True
        )
  except Exception as e:
        print(f"Error saving playtime: {e}")

  if user_client is None:
    print(f"User client not found for session: {session_client}")
    return

  song_queue_key = f"dic_{user_client.me.id}"
  print(f"Song queue key: {song_queue_key}")
  song_queue = queues.get(song_queue_key)

  if song_queue is None:
    print(f"Song queue not found for user: {user_client.me.id}")
    await client.leave_call(update.chat_id)
    await remove_active_chat(user_client, update.chat_id)
    return playing[update.chat_id].clear()

  try:
    if update.chat_id in song_queue and song_queue[update.chat_id]:
      next_song = song_queue[update.chat_id].pop(0)
      playing[update.chat_id] = next_song
      await join_call(next_song['message'], next_song['title'],
next_song['session'], next_song['yt_link'], next_song['chat'], next_song['by'], next_song['duration'], next_song['mode'], next_song['thumb'])
    else:
      print(f"Song queue for chat {update.chat_id} is empty.")
      await client.leave_call(update.chat_id)
      await remove_active_chat(user_client, update.chat_id)
      playing[update.chat_id].clear()
  except Exception as e:
    print(f"Error in end function: {e}")


from yt_dlp import YoutubeDL

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
async def join_call(message, title, user_client, youtube_link, chat, by, duration, mode, thumb):
    audio_flags = MediaStream.Flags.IGNORE if mode == "audio" else None
    song_queue = queues.get(f"dic_{user_client.me.id}")
    position = len(song_queue.get(message.chat.id)) if song_queue.get(message.chat.id) else 0

    try:

        bot_username = user_client.me.username
        session_client_id = connector.get(bot_username)

        if session_client_id is None:
            await message.edit("No session client connected. Please authorize first with /host.")
            return await remove_active_chat(user_client, message.chat.id)

        # Retrieve the session client from the clients dictionary
        session_client = clients.get(f"{session_client_id}_session")
        if not session_client:
            await message.edit("Session client not found. Please re-authorize with /host.")
            return await remove_active_chat(user_client, message.chat.id)

        call_py = songs_client.get(session_client.me.id)
        await call_py.play(
            chat.id,
            MediaStream(
                youtube_link,
                AudioQuality.STUDIO,
                VideoQuality.HD_720p,
                video_flags=audio_flags,
                ytdlp_parameters='--cookies cookies.txt',
            ),
        )
        played[message.chat.id] =time.time()
        owner_id = get_owner_id_by_client(user_client)
        # Creating the inline keyboard with buttons arranged in two rows
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(text="▷", callback_data="resume"),
                InlineKeyboardButton(text="II", callback_data="pause"),
                InlineKeyboardButton(text="‣‣I" if position <1 else f"‣‣I({position})", callback_data="skip"),
                InlineKeyboardButton(text="▢", callback_data="end"),
            ],
        [                                                                                           InlineKeyboardButton(
                text=f"{smallcap('Add to group')}", url=f"https://t.me/{user_client.me.username}?startgroup=true"
            ),
            InlineKeyboardButton(
	                text=f"{smallcap('ᴜᴘᴅᴀᴛᴇs')}", url= gvarstatus(owner_id, "support") or "https://t.me/nub_coder_updates"
            )
        ],
        ])
        sent_message = await user_client.send_photo(
            message.chat.id, thumb, play_styles[int(gvarstatus(owner_id, "format") or 16)].format(superscript(mode), superscript(title), superscript(duration), by.mention()),
            reply_markup=keyboard        )
        asyncio.create_task(autoleave_vc(user_client, call_py, sent_message, duration))
        asyncio.create_task(update_progress_button(sent_message, duration, call_py))
        try:
            await message.delete()
        except Exception as e:
            print(e)
    except NoActiveGroupCall:
        await user_client.send_message(chat.id, "ERROR: No active group calls")
        return await remove_active_chat(user_client, message.chat.id)
    except GroupcallForbidden:
        await user_client.send_message(chat.id, "ERROR: Telegram internal server error")
        return await remove_active_chat(user_client, message.chat.id)
    except Exception as e:
        await user_client.send_message(chat.id, f"ERROR: {e}")
        return await remove_active_chat(user_client, message.chat.id)

def format_duration(duration):
  hours = duration // 3600
  minutes = (duration % 3600) // 60
  seconds = duration % 60

  if hours > 0:
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
  elif minutes > 0:
    return f"{minutes:02d}:{seconds:02d}"
  else:
    return f"{seconds:02d}"


async def stop_user(sender):
                try:
                  user_client = clients.get(sender)
                  bot_username = user_client.me.username
                  session_client_id = connector.get(bot_username)
                  session_client = clients.get(f"{session_client_id}_session")
                  call_py = songs_client.get(session_client.me.id)
                  song_queue = queues.get(f"dic_{user_client.me.id}")
                  for chat_id in song_queue:
                    try:
                       await call_py.leave_call(chat_id)
                    except:
                      pass
                    try:
                       await remove_active_chat(user_client, chat_id)
                       song_queue[chat_id].clear()
                    except:
                      pass
                except:
                      pass
                try:
                   user_client = clients.get(sender)
                   await user_client.terminate()
                   del user_client
                except Exception as e:
                   print(e)
                try:
                   user_client = clients.get(sender)
                   await user_client.stop(block=False)
                   del user_client
                except Exception as e:
                   print(e)
                try:
                   session_client = clients.get(f"{sender}_session")
                   await session_client.terminate()
                   del session_client
                except Exception as e:
                   print(e)
                try:
                   session_client = clients.get(f"{sender}_session")
                   await session_client.stop(block=False)
                   del session_client
                except Exception as e:
                   print(e)
                try:
                   clients.pop(sender)
                except Exception as e:
                   print(e)


from telethon import events
import os

@bot.on(events.NewMessage(
    incoming=True,
    outgoing=False,
    func=lambda x: x.is_private,
    pattern="/stop"
))
async def stopping(event):
    # Split the message to check for arguments
    command_parts = event.raw_text.split()
    sender = event.sender_id
    
    # Check if there's a second argument (trying to stop another user's session)
    if len(command_parts) > 1:
        # First check if the command sender is an admin
        admin_file = f"{ggg}/admin.txt"
        is_admin = False
        if os.path.exists(admin_file):
            with open(admin_file, "r") as file:
                admin_ids = [int(line.strip()) for line in file.readlines()]
                is_admin = sender in admin_ids
        
        if not is_admin:
            await event.respond("Only admins can stop other users' sessions.")
            return
            
        try:
            target_user = int(command_parts[1])
        except ValueError:
            await event.respond("Invalid user ID provided.")
            return
            
        # If we get here, the sender is an admin and the target user ID is valid
        user_to_stop = target_user
    else:
        # Regular /stop command without arguments - user stopping their own session
        user_to_stop = sender
    
    # Check if target user exists in database
    user_data = user_sessions.find_one({"user_id": user_to_stop})
    if user_data:
        await event.respond("Stopping the music bot\n\nPlease wait....")
        await stop_user(user_to_stop)
        await event.respond("Stopped the music bot successfully.\nWe always welcome you back anytime.")
    else:
        await event.respond("The session was not found in the database. Please use /host to log in.")



@bot.on(events.NewMessage(
    incoming=True,
    outgoing=False,
    func=lambda x: x.is_private,
    pattern="/restart"
))
async def starting(event):
    # Split the message to check for arguments
    command_parts = event.raw_text.split()
    sender = event.sender_id
    
    # Check if there's a second argument (trying to restart another user's session)
    if len(command_parts) > 1:
        # First check if the command sender is an admin
        admin_file = f"{ggg}/admin.txt"
        is_admin = False
        if os.path.exists(admin_file):
            with open(admin_file, "r") as file:
                admin_ids = [int(line.strip()) for line in file.readlines()]
                is_admin = sender in admin_ids
        
        if not is_admin:
            await event.respond("Only admins can restart other users' sessions.")
            return
            
        try:
            target_user = int(command_parts[1])
        except ValueError:
            await event.respond("Invalid user ID provided.")
            return
            
        # If we get here, the sender is an admin and the target user ID is valid
        user_to_restart = target_user
    else:
        # Regular /restart command without arguments - user restarting their own session
        user_to_restart = sender

    # Check if user exists in database
    user_data = user_sessions.find_one({"user_id": user_to_restart})
    if user_data:
        # If it's a regular user restarting their own session, check premium status
        if user_to_restart == sender:
            drem = is_dremium(user_to_restart)
            prem = is_premium(user_to_restart)
            if not prem:
                await stop_user(user_to_restart)
                return await bot.send_message(user_to_restart,
                    "ERROR: Your trial /plans plan has been ended\n"
                    "You need to purchase our premium plans\n\n"
                    "Checkout /plans to more")
        
        await event.respond("Restarting the music bot\n\nPlease wait....")
        asyncio.create_task(stop_user(user_to_restart))
        await asyncio.sleep(5)
        await run_user(user_to_restart)
    else:
        await event.respond("The session was not found in the database. Please use /host to log in.")

def reload_all_plugins():
    # Reload plugins from the current directory
    current_dir_plugins = ['tools', 'fonts']
    for plugin_name in current_dir_plugins:
        try:
            module = importlib.import_module(plugin_name)
            importlib.reload(module)
            print(f"Reloaded plugin: {plugin_name}")
        except Exception as e:
            print(f"Failed to reload plugin {plugin_name}: {e}")

    # Original plugin directory reload
    plugin_dir = "plugins"
    for file in os.listdir(plugin_dir):
        if file.endswith(".py") and not file.startswith("*"):  # Ignore *init_>
            module_name = file[:-3]  # Remove .py extension
            try:
                module = importlib.import_module(f"{plugin_dir}.{module_name}")
                importlib.reload(module)  # Reload the module
                print(f"Reloaded plugin: {module_name}")
            except Exception as e:
                print(f"Failed to reload plugin {module_name}: {e}")

async def run_user(user_id):
    reload_all_plugins()
    user_data = user_sessions.find_one({"user_id": user_id})
    user_session_string = user_data.get("string_session")
    user_bot_token = user_data.get("bot_token")
    
    try:
        # Create and start the user client using the bot token
        user_client = Client(
            f"{generate_client_id()}",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=user_bot_token,
            workers=5,
            plugins=dict(root="plugins"),
            in_memory=True, sleep_threshold=32,
        )
        await user_client.start()
        client_name = f"{user_client.me.first_name} {user_client.me.last_name or ''}".strip()
        print(f"Bot authorized successfully! 🎉 Authorized as: {client_name}")
        clients[user_id] = user_client
        owners[user_client.me.id] = user_id
        bot_maintenance = asyncio.create_task(
            maintain_connection(
                user_id=user_id,
                client=user_client,
                is_bot=True,
                check_interval=100,  # 5 minutes
                retry_delay=60       # 1 minute
            )
        )
        

    except (SessionRevoked, UserDeactivatedBan, AuthKeyInvalid, AuthKeyUnregistered, 
            SessionRevoked, AuthTokenExpired, AuthKeyDuplicated, AccessTokenExpired, 
            UserDeactivated) as e:
        try:
            user_client = clients.get(user_id)
            await user_client.stop(block=False)
        except:
            pass
        user_sessions.delete_one({"user_id": user_id})
        if user_id in clients:
            clients.pop(user_id)
            
    except AttributeError:
        print("The object is None; it doesn't have an 'id' attribute.")
        
    except Exception as e:
        try:
            user_client = clients.get(user_id)
            await user_client.stop(block=False)
        except:
            pass
        try:
            await app.send_message(user_id, f"Error starting your music: {e}")
        except:
            pass
            
        # Notify admins about the error
        admin_file = f"{ggg}/admin.txt"
        if os.path.exists(admin_file):
            with open(admin_file, "r") as file:
                admin_ids = [int(line.strip()) for line in file.readlines()]
                for admin_id in admin_ids:
                    try:
                        await app.send_message(admin_id, f"Error starting client for user {user_id}: {e}")
                    except:
                        pass
                        
        if user_id in clients:
            clients.pop(user_id)
        return

    try:
        # Create and start the session client
        session_client = Client(
            f"user_{user_id}_session",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=user_session_string,
workers =1,            in_memory=True, sleep_threshold=32
        )
        auth = await session_client.connect()
        if not auth:
            try:
                user_client = clients.get(user_id)
                await user_client.stop(block=False)
            except:
                pass
            await app.send_message(user_id, f"Client is not authorized for {user_id}. Please authorize first.")
            await session_client.disconnect()
            user_sessions.delete_one({"user_id": user_id})
            return

        await session_client.disconnect()
        call_py = PyTgCalls(session_client)
        call_py.add_handler(end, call_filters.stream_end)
        call_py.add_handler(hd_stream_closed_kicked, call_filters.chat_update(ChatUpdate.Status.CLOSED_VOICE_CHAT) | call_filters.chat_update(ChatUpdate.Status.KICKED))
        await call_py.start()
        await asyncio.sleep(2)
        clients[f"{user_id}_session"] = session_client
        songs_client[session_client.me.id] = call_py
        client_name = f'{session_client.me.first_name if session_client.me else ""} {session_client.me.last_name or "" if session_client.me else ""}'.strip()
        user_client = clients.get(user_id)
        await app.send_message(user_id, f"Your music bot rebooted successfully 🎉 bot as: @{user_client.me.username}\nAssistant as: {client_name}")
        print(f"Username authorized successfully! 🎉 Authorized as: {client_name}")

        try:
            await session_client.join_chat("nub_coder_s")
            await session_client.join_chat("nub_coder_updates")
        except:
            pass

        connector[user_client.me.username] = user_id
        queues[f"dic_{user_client.me.id}"] = {}
        linkage[session_client.me.id] = user_client
        active[user_client.me.username] = []
        session_maintenance = asyncio.create_task(
            maintain_connection(
                user_id=user_id,
                client=session_client,
                is_bot=False,
                check_interval=100,  # 5 minutes
                retry_delay=60       # 1 minute
            )
        )
        
    except (SessionRevoked, UserDeactivatedBan, AuthKeyInvalid, AuthKeyUnregistered, 
            SessionRevoked, AuthTokenExpired, AuthKeyDuplicated, AccessTokenExpired, 
            UserDeactivated) as e:
        user_sessions.delete_one({"user_id": user_id})
        try:
            user_client = clients.get(user_id)
            await user_client.stop(block=False)
        except:
            pass
        if user_id in clients:
            clients.pop(user_id)
            
    except AttributeError:
        print("The object is None; it doesn't have an 'id' attribute.")
        
    except Exception as e:
        try:
            user_client = clients.get(user_id)
            await user_client.stop(block=False)
        except:
            pass
        try:
            await app.send_message(user_id, f"Error starting your music: {e}")
        except:
            pass
            
        # Notify admins about the error
        admin_file = f"{ggg}/admin.txt"
        if os.path.exists(admin_file):
            with open(admin_file, "r") as file:
                admin_ids = [int(line.strip()) for line in file.readlines()]
                for admin_id in admin_ids:
                    try:
                        await app.send_message(admin_id, f"Error starting client for user {user_id}: {e}")
                    except:
                        pass
                        
        if user_id in clients:
            clients.pop(user_id)



def is_premium(user_id):
    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})

    if user_data:
        stored_time = user_data.get("timestamp")
        if not stored_time:
          return True
        time_difference =  stored_time - current_time
        if time_difference > 0:
            return True
        return False
    return True


async def run_user_client(user_id):
    reload_all_plugins()
    user_data = user_sessions.find_one({"user_id": user_id})
    user_session_string = user_data.get("string_session")
    user_bot_token = user_data.get("bot_token")
    drem = is_dremium(user_id)
    prem = is_premium(user_id)
    if not prem:
        return
    await asyncio.sleep(delay=random.randint(5, 100))
    try:
        # Create and start the user client using the bot token
        user_client = Client(
            f"{generate_client_id()}",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=user_bot_token, workers =5,
plugins=dict(root="plugins"),in_memory=True,
    sleep_threshold=30,  # Increased from default 10
        )
        await user_client.start()
        client_name = f"{user_client.me.first_name} {user_client.me.last_name or ''}".strip()
        print(f"Bot authorized successfully! 🎉 Authorized as: {client_name}")
        clients[user_id] = user_client
        owners[user_client.me.id] = user_id
        bot_maintenance = asyncio.create_task(
            maintain_connection(
                user_id=user_id,
                client=user_client,
                is_bot=True,
                check_interval=100,  # 5 minutes
                retry_delay=60       # 1 minute
            )
        )
        
    except (SessionRevoked, UserDeactivatedBan, AuthKeyInvalid, AuthKeyUnregistered, SessionRevoked, AuthTokenExpired, AuthKeyDuplicated, AccessTokenExpired, UserDeactivated):
        user_sessions.delete_one({"user_id": user_id})
        if user_id in clients:
            clients.pop(user_id)
        admin_file = f"{ggg}/admin.txt"
        if os.path.exists(admin_file):
            with open(admin_file, "r") as file:
                admin_ids = [int(line.strip()) for line in file.readlines()]
                for admin_id in admin_ids:
                    try:
                        await app.send_message(admin_id, f"Error starting client for user {user_id}: {e}")
                    except:
                        pass
    except Exception as e:
        admin_file = f"{ggg}/admin.txt"
        if os.path.exists(admin_file):
            with open(admin_file, "r") as file:
                admin_ids = [int(line.strip()) for line in file.readlines()]
                for admin_id in admin_ids:
                    try:
                        await app.send_message(admin_id, f"Error starting client for user {user_id}: {e}")
                    except:
                        pass

    try:
        # Create and start the session client
        session_client = Client(
            f"user_{user_id}_session",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=user_session_string,
workers =1,            in_memory=True, sleep_threshold=32)
        auth = await session_client.connect()
        if not auth:
            try:
                      user_client = clients.get(user_id)
                      await user_client.stop(block=False)
            except:
                    pass
            print(f"Client is not authorized for {user_id}. Please authorize first.")
            await session_client.stop(block=False)
            user_sessions.delete_one({"user_id": user_id})
            return
        await session_client.disconnect()
        call_py = PyTgCalls(session_client)
        clients[f"{user_id}_session"] = session_client
        call_py.add_handler(end, call_filters.stream_end)
        call_py.add_handler(hd_stream_closed_kicked, call_filters.chat_update(ChatUpdate.Status.CLOSED_VOICE_CHAT) | call_filters.chat_update(ChatUpdate.Status.KICKED))
        await call_py.start()
        await asyncio.sleep(2)
        songs_client[session_client.me.id] = call_py
        client_name = f'{session_client.me.first_name if session_client.me else ""} {session_client.me.last_name or "" if session_client.me else ""}'.strip()
        print(f"Username authorized successfully! 🎉 Authorized as: {client_name}")
        try:
                   await session_client.join_chat("nub_coder_s")
                   await session_client.join_chat("nub_coder_updates")
        except:
                   pass
        # Add to connector dictionary
        connector[user_client.me.username] = user_id
        queues[f"dic_{user_client.me.id}"] = {}
        linkage[session_client.me.id] = user_client
        active[user_client.me.username] = []
        session_maintenance = asyncio.create_task(
            maintain_connection(
                user_id=user_id,
                client=session_client,
                is_bot=False,
                check_interval=100,  # 5 minutes
                retry_delay=60       # 1 minute
            )
        )
        
        # Add play handler to user_client using MessageHandler
    except AttributeError:
        print("The object is None; it doesn't have an 'id' attribute.")
    except (SessionRevoked, UserDeactivatedBan, AuthKeyInvalid, AuthKeyUnregistered, SessionRevoked, AuthTokenExpired, AuthKeyDuplicated, AccessTokenExpired, UserDeactivated) as e:
        try:
                      user_client = clients.get(user_id)
                      await user_client.stop(block=False)
        except:
                    pass
        user_sessions.delete_one({"user_id": user_id})
        if user_id in clients:
            clients.pop(user_id)
        admin_file = f"{ggg}/admin.txt"
        if os.path.exists(admin_file):
            with open(admin_file, "r") as file:
                admin_ids = [int(line.strip()) for line in file.readlines()]
                for admin_id in admin_ids:
                    try:
                        await app.send_message(admin_id, f"Error starting client for user {user_id}: {e}")
                    except:
                        pass
    except Exception as e:
        print(e)
        admin_file = f"{ggg}/admin.txt"
        if os.path.exists(admin_file):
            with open(admin_file, "r") as file:
                admin_ids = [int(line.strip()) for line in file.readlines()]
                for admin_id in admin_ids:
                    try:
                        await app.send_message(admin_id, f"Error starting client for user {user_id}: {e}")
                    except:
                        pass
        try:
                             await bot.send_message(user_id,f"Error starting your client:\n{e}")
        except:
                                pass



def is_dremium(user_id):
    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})
    if user_data:
        stored_time = user_data.get("timestamp")
        premium_by = user_data.get("premium_by")
        if not stored_time:
          storre_user(user_id, int(time.time()) + (2 * 24 * 60 * 60))
          return False
        if not premium_by:
            collection.update_one(
                {"user_id": user_id},
                {"$set": {"premium_by": "TRIAL"}},
                upsert=True
            )
        time_difference =  stored_time - current_time
        if time_difference > 0:
             return True
        return False
    return False


async def run_all_clients():
  reload_all_plugins()
  results = []
  app_maintenance = asyncio.create_task(
           maintain_app(
                client = app,
                check_interval=100,  # 5 minutes
                retry_delay=60       # 1 minute                                              
)
        )
  user_ids = user_sessions.distinct("user_id")
  tasks = [asyncio.create_task(run_user_client(user_id))
             for user_id in user_ids]

  await asyncio.gather(*tasks)

def set_gvar(user_id, key, value):
    set_user_data(user_id, key, value)

def get_user_data(user_id, key):
    user_data = user_sessions.find_one({"user_id": user_id})
    if user_data and key in user_data:
        return user_data[key]
    return None

def set_user_data(user_id, key, value):
    user_sessions.update_one({"user_id": user_id}, {"$set": {key: value}}, upsert=True)

def gvarstatus(user_id, key):
    return get_user_data(user_id, key)

def unset_user_data(user_id, key):
     user_sessions.update_one({"user_id": user_id}, {"$unset": {key: ''}}, upsert=True)


def rename_file(old_name, new_name):
    try:
        # Rename the file
        os.rename(old_name, new_name)

        # Get the absolute path of the renamed file
        new_file_path = os.path.abspath(new_name)
        print(f'File renamed from {old_name} to {new_name}')
        return new_file_path  # Return the new file location
    except FileNotFoundError:
        print(f'The file {old_name} does not exist.')
    except FileExistsError:
        print(f'The file {new_name} already exists.')
    except Exception as e:
        print(f'An error occurred: {e}')
import magic

mime = magic.Magic(mime=True)


import psutil
import os


@bot.on(events.NewMessage(pattern='/ping'))
async def ping_command(event):
    # Calculate uptime
    uptime = get_readable_time((time.time() - StartTime))
    start = datetime.datetime.now()

    # Simulate progress bar
    xx = await event.reply("**0% ▒▒▒▒▒▒▒▒▒▒**")
    await xx.edit("**20% ██▒▒▒▒▒▒▒▒**")
    await xx.edit("**40% ████▒▒▒▒▒▒**")
    await xx.edit("**60% ██████▒▒▒▒**")
    await xx.edit("**80% ████████▒▒**")
    await xx.edit("**100% ██████████**")

    # Calculate the duration
    end = datetime.datetime.now()
    delta_ping = (end - start).microseconds / 1000
    delta_ping_formatted = round(delta_ping, 3)
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent
    process = psutil.Process(os.getpid())
    _ping = f"""
<blockquote>
PING: {str(delta_ping_formatted).replace('.', ',')} ms
UPTIME: {uptime}
OWNER: @fuck_you_deeply

Server Stats
CPU: {cpu}%
RAM: {mem}%
DISK: {disk}%
MEMORY: {round(process.memory_info()[0] / 1024 ** 2)} MB</blockquote>
"""
    await xx.edit(_ping,parse_mode="html")



from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import MessageEntityType



@bot.on(events.NewMessage(incoming=True, outgoing=False, func=lambda x: x.is_private, pattern='/resetwelcome'))
async def reset_welcome_handler(event):
    user_id = event.sender_id
    sender_id = event.sender_id
    user_data = user_sessions.find_one({"user_id": sender_id})
    
    if not user_data:
        return await event.reply("User data not found. Please /host first.")
    
    # Reset both LOGO and WELCOME
    unset_user_data(user_id, 'LOGO')
    unset_user_data(user_id, 'WELCOME')
    
    await event.respond("Welcome logo and message successfully reset")


@app.on_message(filters.command("setwelcome") & filters.private)
async def set_welcome_handler(client, message):
    try:
        sender_id = message.from_user.id
        user_data = user_sessions.find_one({"user_id": sender_id})
        user_client = clients.get(sender_id)
        if not user_data or not user_client:
            return await message.reply_text("User data not found. Please /host first.")

        session_name = f'user_{user_client.me.id}'
        user_dir = f"{ggg}/{session_name}"
        os.makedirs(user_dir, exist_ok=True)

        replied_msg = message.reply_to_message
        if not replied_msg:
            usage_text = (
                "Please reply to a message to set it as welcome message.\n\n"
                "You can set:\n"
                "• Text message\n"
                "• Media (photo/video/gif/sticker)\n"
                "• Media with caption\n\n"
                "Available placeholders:\n"
                "• {name} - User's name\n"
                "• {id} - User's ID\n"
                "• {botname} - Bot's username\n\n"
                "Size limits:\n"
                "• Text: Maximum 4096 characters\n"
                "• Media: Maximum 5MB\n\n"
                "Example usage:\n"
                "• 'Welcome {name}! Your ID is {id}'\n"
                "• Reply to a photo/video with caption 'Welcome to {botname}!'"
            )
            return await message.reply_text(usage_text)

        updates = []
        
        # Handle text if present
        if replied_msg.text or replied_msg.caption:
            welcome_text = (replied_msg.text or replied_msg.caption).strip()
            if len(welcome_text) > 4096:
                return await message.reply_text("Welcome message too long. Maximum 4096 characters allowed.")

            entities = sorted(
                (replied_msg.entities or replied_msg.caption_entities or []),
                key=lambda x: (x.offset, -x.length)
            )

            ENTITY_TO_HTML = {
                MessageEntityType.BOLD: ('b', 'b'),
                MessageEntityType.ITALIC: ('i', 'i'),
                MessageEntityType.UNDERLINE: ('u', 'u'),
                MessageEntityType.STRIKETHROUGH: ('s', 's'),
                MessageEntityType.SPOILER: ('spoiler', 'spoiler'),
                MessageEntityType.CODE: ('code', 'code'),
                MessageEntityType.PRE: ('pre', 'pre'),
                MessageEntityType.BLOCKQUOTE: ('blockquote', 'blockquote')
            }

            def convert_to_html(text, msg_entities):
                tag_positions = []
                
                for entity in msg_entities:
                    if entity.type in ENTITY_TO_HTML:
                        start_tag, end_tag = ENTITY_TO_HTML[entity.type]
                        
                        if entity.type == MessageEntityType.PRE and getattr(entity, 'language', None):
                            tag_positions.append((entity.offset, f'<pre language="{entity.language}">', True))
                        else:
                            tag_positions.append((entity.offset, f'<{start_tag}>', True))
                        
                        tag_positions.append((entity.offset + entity.length, f'</{end_tag}>', False))

                tag_positions.sort(key=lambda x: (x[0], x[2]))
                
                result = []
                current_pos = 0
                
                for pos, tag, _ in tag_positions:
                    if pos > current_pos:
                        result.append(text[current_pos:pos])
                    result.append(tag)
                    current_pos = pos
                
                if current_pos < len(text):
                    result.append(text[current_pos:])
                    
                return ''.join(result)

            processed_text = convert_to_html(welcome_text, entities)

            # Validate placeholders
            ALLOWED_PLACEHOLDERS = {"{name}", "{id}", "{botname}"}
            placeholder_regex = r'\{([^{}]+)\}'
            found_placeholders = set(re.findall(placeholder_regex, processed_text))
            
            invalid_placeholders = [f"{{{p}}}" for p in found_placeholders 
                                  if f"{{{p}}}" not in ALLOWED_PLACEHOLDERS]
            
            if invalid_placeholders:
                error_msg = "❌ Invalid placeholders found:\n"
                error_msg += "\n".join(f"• {p}" for p in invalid_placeholders)
                error_msg += "\n\nAllowed placeholders:\n"
                error_msg += "\n".join(f"• {p}" for p in sorted(ALLOWED_PLACEHOLDERS))
                error_msg += "\n\nExample usage:\n"
                error_msg += "• Welcome {name}!\n"
                error_msg += "• Your ID: {id}\n"
                error_msg += "• Welcome to {botname}!"
                return await message.reply_text(error_msg)

            set_gvar(sender_id, "WELCOME", processed_text)
            updates.append("welcome message")

        # Handle media if present
        if replied_msg.media:
            m_d = None
            try:
                # Check if media type is allowed
                if not (replied_msg.photo or replied_msg.video or 
                       replied_msg.sticker or replied_msg.animation):
                    return await message.reply_text("Only photos, videos, GIFs, and stickers are allowed.")

                # Check file size (5MB = 5 * 1024 * 1024 bytes)
                file_size = getattr(replied_msg, 'file_size', 0)
                if file_size > 5242880:  # 5MB in bytes
                    return await message.reply_text("Media size cannot exceed 5MB.")

                # Process media based on type
                if replied_msg.sticker:
                    m_d = await convert_to_image(replied_msg, user_client)
                else:
                    m_d = await replied_msg.download()

                if m_d:
                    with open(m_d, "rb") as imageFile:
                        logo_data = base64.b64encode(imageFile.read())
                    os.remove(m_d)
                    set_gvar(sender_id, "LOGO", logo_data)
                    updates.append("logo")

            except Exception as e:
                if m_d and os.path.exists(m_d):
                    os.remove(m_d)
                return await message.reply_text(f"Error processing media: {str(e)}")

        if not updates:
            return await message.reply_text("Nothing to update. Message must contain text and/or media.")

        # Send confirmation and preview
        success_msg = f"✅ Updated {' and '.join(updates)}!"
        await client.send_message(message.chat.id, success_msg + "\n\nPreview:")

        # Show preview
        try:
            logo = gvarstatus(sender_id, "LOGO")
            if not logo and user_client.me.photo:
                photos = await user_client.get_profile_photos("me")
                if photos:
                    logo = await user_client.download_media(photos[0].file_id, f"{user_dir}/logo.jpg")
            if not logo:
                logo = "music.jpg"

            alive_logo = logo
            if isinstance(logo, bytes):
                alive_logo = f"{user_dir}/logo.jpg"
                with open(alive_logo, "wb") as fimage:
                    fimage.write(base64.b64decode(logo))
                if 'video' in mime.from_file(alive_logo):
                    alive_logo = rename_file(alive_logo, f"{user_dir}/logo.mp4")

            welcome_text = gvarstatus(sender_id, "WELCOME") or f"""

╔══════ ≪ °❈° ≫ ══════
✧ 𝙒𝙀𝙇𝘾𝙊𝙈𝙀 𝙏𝙊 𝙈𝙐𝙎𝙄𝘾 𝘽𝙊𝙏 ✧
╚══════ ≪ °❈° ≫ ══════
🎭 𝙏𝙃𝙀 𝙐𝙇𝙏𝙄𝙈𝘼𝙏𝙀 𝙈𝙐𝙎𝙄𝘾 𝙀𝙓𝙋𝙀𝙍𝙄𝙀𝙉𝘾𝙀 🎭
┏━━━━━━━━━━━━━━━━━
✨𝙋𝙍𝙀𝙈𝙄𝙐𝙈 𝙁𝙀𝘼𝙏𝙐𝙍𝙀𝙎 ✨
┗━━━━━━━━━━━━━━━━━
🎵 𝘾𝙍𝙔𝙎𝙏𝘼𝙇-𝘾𝙇𝙀𝘼𝙍 𝘼𝙐𝘿𝙄𝙊
🎬 𝙃𝘿 𝙑𝙄𝘿𝙀𝙊 𝙎𝙏𝙍𝙀𝘼𝙈𝙄𝙉𝙂
⚡ 𝙇𝙄𝙂𝙃𝙏𝙉𝙄𝙉𝙂-𝙁𝘼𝙎𝙏
🎮 𝙎𝙈𝘼𝙍𝙏 𝘾𝙊𝙉𝙏𝙍𝙊𝙇𝙎

• 𝙀𝙓𝙋𝙀𝙍𝙄𝙀𝙉𝘾𝙀 𝙏𝙃𝙀 𝙈𝘼𝙂𝙄𝘾! •
"""
            d_ata = collection.find_one({"user_id": sender_id})
            premium_by = d_ata.get("premium_by", "PAID")
            if premium_by in ("REFERRAL", "TRIAL"):
               welcome_text += f"""\n\nᴘᴏᴡᴇʀᴇᴅ ʙʏ [⚡](http://t.me/{app.me.username}?start={sender_id})"""
            
            if alive_logo.endswith(".mp4"):
                await client.send_video(
                    message.chat.id,
                    alive_logo,
                    caption=welcome_text,
                )
            else:
                await client.send_photo(
                    message.chat.id,
                    alive_logo,
                    caption=welcome_text,
                )

        except Exception as e:
            print(f"Error showing preview: {str(e)}")
            welcome_text = gvarstatus(sender_id, "WELCOME")
            if welcome_text:
                await client.send_message(
                    message.chat.id,
                    welcome_text,
                )

    except Exception as e:
        error_msg = f"❌ Error: `{str(e)}`"
        print(f"Error for user {message.from_user.id}: {str(e)}")
        return await message.reply_text(error_msg)



from telethon import events, Button
from telethon.tl.types import User

@bot.on(events.NewMessage(pattern="/logout"))
async def deauth_handler(event):
    sender = event.sender_id
    user_data = user_sessions.find_one({"user_id": sender})
    
    if not user_data:
        await event.reply("Your session was not found in the database. Please use /host to log in.")
        return

    buttons = [
        [
            Button.inline("Yes, Logout", b"confirm_logout"),
            Button.inline("No, Cancel", b"cancel_logout")
        ]
    ]

    async with bot.conversation(sender, timeout=60) as don:
        conversations[sender] = don
        conv = conversations[sender]
        # Send the confirmation message with buttons
        confirmation_msg = await conv.send_message(
            "We hate to see you go! Are you sure you want to logout?",
            buttons=buttons
        )
        
        try:
            # Wait for button response
            response = await conv.wait_event(events.CallbackQuery(sender))
            
            if response.data == b"confirm_logout":
                # Remove session from MongoDB
                user_sessions.delete_one({"user_id": sender})
                
                # Stop and cleanup clients
                try:
                    user_client = clients.get(sender)
                    if user_client:
                        await user_client.stop(block=False)
                except Exception as e:
                    print(f"Error stopping user client: {e}")
                    
                try:
                    session_client = clients.get(f"{sender}_session")
                    if session_client:
                        await session_client.stop(block=False)
                except Exception as e:
                    print(f"Error stopping session client: {e}")
                    
                try:
                    clients.pop(sender)
                except Exception as e:
                    print(f"Error removing client from dict: {e}")

                await confirmation_msg.edit("You've been logged out successfully! We always welcome you back anytime.", buttons=None)
                
            elif response.data == b"cancel_logout":
                await confirmation_msg.edit("Logout cancelled. We're glad you're staying with us!", buttons=None)
                
        except TimeoutError:
            await confirmation_msg.edit("Logout cancelled as timed out. We're glad you're staying with us!", buttons=None)


from telethon import events
import os
import sys

@bot.on(events.NewMessage(pattern=r'/reboot'))
async def reboot_handler(event):
    user_id = event.sender_id
    
    # Check if the user is an admin
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id in admin_ids:
                await event.reply("Admin command received. Stopping the bot...")
                os.system(f"kill -9 {os.getpid()}")  # Kill the current process
            else:
                await event.reply("You are not authorized to use this command.")
    else:
        await event.reply("Admin file not found. Please contact the bot admin.")


create_custom_filter = filters.create(lambda _, __, message: any(m.is_self for m in (message.new_chat_members if message.new_chat_members else [])))


@app.on_message(filters.command("start") | (filters.group & create_custom_filter))
async def app_start_handler(client, message):
    try:
        user_id = message.chat.id
        user_name = message.from_user.first_name if message.from_user else "User"
        user_data = collection.find_one({"user_id": user_id})

        # Handle referral system
        if not user_data:
            parts = message.text.split()
            if len(parts) == 2:
                try:
                    referrer_id = int(parts[1])
                    # Update referrer's points
                    collection.update_one(
                        {"user_id": referrer_id},
                        {"$inc": {"premium_points": 1}},
                        upsert=True
                    )
                    
                    # Notify referrer with styled message
                    referral_msg = f"""
🎉 **Wonderful News!**
└ New referral from: `{user_name}`
└ Premium points increased: `+1`
└ Check your points with /plans

*Thank you for growing our community!* ✨
"""
                    await app.send_message(referrer_id, referral_msg)

                except Exception as e:
                    print(f"Referral processing error: {str(e)}")

            # Create new user record
            user_data = {"user_id": user_id, "joined_date": datetime.datetime.now()}
            collection.replace_one({"user_id": user_id}, user_data, upsert=True)

        # Welcome message with styled commands
        welcome_message = f"""
╔══「 🎵 𝐌𝐮𝐬𝐢𝐜 𝐁𝐨𝐭 𝐇𝐨𝐬𝐭𝐞𝐫 」
║
║ 👋 𝐘𝐨𝐮𝐫 𝐔𝐥𝐭𝐢𝐦𝐚𝐭𝐞 𝐌𝐮𝐬𝐢𝐜 𝐁𝐨𝐭 𝐂𝐫𝐞𝐚𝐭𝐢𝐨𝐧 𝐏𝐥𝐚𝐭𝐟𝐨𝐫𝐦!
║ ⚡ 𝐁𝐮𝐢𝐥𝐝 𝐌𝐮𝐬𝐢𝐜 𝐁𝐨𝐭𝐬 𝐅𝐚𝐬𝐭, 𝐍𝐨 𝐕𝐏𝐒, 𝐍𝐨 𝐂𝐨𝐝𝐞! ⚙️
║ ✨ 𝐂𝐮𝐬𝐭𝐨𝐦𝐢𝐳𝐞 𝐀𝐧𝐲𝐭𝐡𝐢𝐧𝐠, 𝐀𝐧𝐲𝐭𝐢𝐦𝐞, 𝐈𝐧𝐬𝐭𝐚𝐧𝐭𝐥𝐲! 🚀
╚══════════════════════


📍 **ᴄᴏᴍᴍᴀɴᴅs:**

⚡️ **ᴇssᴇɴᴛɪᴀʟs:**
├ /start » ʟᴀᴜɴᴄʜ ᴛʜᴇ ʜᴏsᴛᴇʀ
├ /host » ʜᴏsᴛ ʏᴏᴜʀ ᴍᴜsɪᴄ ʙᴏᴛ
├ /logout » sɪɢɴ ᴏᴜᴛ
├ /ping » ᴄʜᴇᴄᴋ sᴛᴀᴛᴜs
└ /activebots » ʟɪsᴛ ʙᴏᴛs

🎮 **ᴄᴏɴᴛʀᴏʟs:**
├ /stop » sᴛᴏᴘ ʏᴏᴜʀ ᴍᴜsɪᴄ
└ /restart » ʀᴇsᴛᴀʀᴛ ʏᴏᴜʀ ᴍᴜsɪᴄ ʙᴏᴛ

⚙️ **sᴇᴛᴛɪɴɢs:**
├ /setwelcome » sᴇᴛ ᴡᴇʟᴄᴏᴍᴇ ᴍᴇssᴀɢᴇ
├ /format » ᴄʜᴀɴɢᴇ ᴛʜᴇ ᴘʟᴀʏ ᴀɴᴅ ǫᴜᴇᴜᴇ ᴛᴇxᴛ ғᴏʀᴍᴀᴛ
└ /resetwelcome » ʀᴇsᴇᴛ ᴡᴇʟᴄᴏᴍᴇ ᴍᴇssᴀɢᴇ ᴀɴᴅ ʟᴏɢᴏ

📝 **ɴᴏᴛᴇs:**
- ᴄʜᴀᴛ ɪᴅs ᴡɪʟʟ ʙᴇ sᴛᴏʀᴇᴅ ꜰᴏʀ ʙʀᴏᴀᴅᴄᴀsᴛs
- ʙʟᴏᴄᴋᴇᴅ ᴜsᴇʀs ᴅᴀᴛᴀ ᴡɪʟʟ ʙᴇ sᴛᴏʀᴇᴅ
- ᴀᴜᴛʜ ᴜsᴇʀs & sᴇᴛᴛɪɴɢs sᴛᴏʀᴇᴅ ɪɴ ᴅʙ
- ᴀʟʟ ᴅᴀᴛᴀ ᴡɪʟʟ ʙᴇ ᴄʟᴇᴀʀᴇᴅ ᴏɴ ʟᴏɢᴏᴜᴛ
"""
        # Send welcome message with animation effect
        sent_msg = await client.send_message(user_id, "🎵 Loading your musical experience...")
        await asyncio.sleep(1)
        buttons = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(text="Support Group 💭", url="https://t.me/nub_coder_s"),
            InlineKeyboardButton(text="Updates Channel 📢", url="https://t.me/nub_coder_updates"),
        ],
    ]
)
        await sent_msg.edit_text(welcome_message,
        reply_markup=buttons,
        disable_web_page_preview=True,)
        
    except Exception as e:
        error_msg = f"❌ An error occurred: {str(e)}"
        await client.send_message(user_id, error_msg)




async def status(client, message):
  """Handles the /status command using a list of user IDs."""
  Man = await message.reply_text("Collecting stats...")
  start = datetime.datetime.now()
  u = g = sg = c = b = um = a_chat = up = 0 # Initialize counters
  user_data = collection.find_one({"user_id": client.me.id})

  if user_data:
    users = user_data.get('users', [])
    progress_msg = ""


    # Use asyncio.gather for efficient parallel processing
    chat_types = await asyncio.gather(
      *[get_chat_type(client, chat_id) for chat_id in users]
    )
    for i, chat_type in enumerate(chat_types):
      if chat_type is None:
        continue # Skip if chat type could not be fetched

      if chat_type == enums.ChatType.PRIVATE:
        u += 1
      elif chat_type ==  enums.ChatType.GROUP:
        g += 1
      elif chat_type == enums.ChatType.SUPERGROUP:
        sg += 1
        try:
          user_s = await client.get_chat_member(users[i], int(client.me.id))
          if user_s.status in (
            enums.ChatMemberStatus.OWNER,
                enums.ChatMemberStatus.ADMINISTRATOR,
          ):
            a_chat += 1
        except Exception as e:
          print(f"Error getting chat member status for {users[i]}: {e}")
      elif chat_type == enums.ChatType.CHANNEL:
        c += 1

      #Update the progress message every 10 iterations.
      if i % 10 == 0:
        progress_msg = (
          f"Collecting stats...\n"
          f"Private: {u}\n"
          f"Groups: {g}\n"
          f"Super Groups: {sg}\n"
          f"Channels: {c}\n"
          f"Admin in: {a_chat}"
        )
        await Man.edit_text(progress_msg)

    end = datetime.datetime.now()
    ms = (end - start).seconds

    await Man.edit_text(
      f"""Bot's Stats Obtained in {ms} seconds
Bot have {u} Private Messages.
Bot is in {g} Groups.
Bot is in {sg} Super Groups.
Bot is in {c} Channels.
Bot is Admin in {a_chat} Chats.
"""
    )
  else:
    await Man.edit_text("No user data found.")




import asyncio
import time
import razorpay
from telethon import Button, events

# Razorpay Configuration
KEY_ID = "rzp_live_whGnMZeGzeGe2l"
KEY_SECRET = "QBzrGMNofkapxcHZfd7nt160"
razor_client = razorpay.Client(auth=(KEY_ID, KEY_SECRET))

# Plan Configuration
PLANS = {
    "standard": {"amount": 4900, "duration": 20},   # ₹49 for 20 days
    "premium": {"amount": 6900, "duration": 30},    # ₹69 for 30 days
    "pro": {"amount": 12900, "duration": 60}        # ₹129 for 60 days
}

@bot.on(events.NewMessage(pattern='/plans'))
async def premium_handler(event):
    user_id = event.sender_id
    user_data = collection.find_one({"user_id": user_id})
    premium_points = user_data.get("premium_points", 0) if user_data else 0
    points_needed = max(0, 20 - premium_points)

    premium_message = f"""
🌟 <b>PREMIUM MEMBERSHIP PLANS</b> 🌟
💎 <b>Exclusive Features:</b>
- Powerful Broadcasting Capabilities
- Advanced Sudo Commands Access
- Priority Support
- Custom Command Creation
- Enhanced Bot Management
- Exclusive Updates Access

🎯 <b>Choose Your Plan:</b>
┏━━━━━━━━━━━━━━━━━
┣ 📍 Standard Plan
┣ • Duration: 20 Days
┣ • Price: ₹49 ($0.61)
┣ • Cost per day: ₹2.45
┗━━━━━━━━━━━━━━━━━

┏━━━━━━━━━━━━━━━━━
┣ 📍 Premium Plan
┣ • Duration: 30 Days
┣ • Price: ₹69 ($0.86)
┣ • Cost per day: ₹2.30
┣ • Save 5.9% vs Standard
┗━━━━━━━━━━━━━━━━━

┏━━━━━━━━━━━━━━━━━
┣ 📍 Pro Plan
┣ • Duration: 60 Days
┣ • Price: ₹129 ($1.65)
┣ • Cost per day: ₹2.15
┣ • Save 12.13% vs Standard
┗━━━━━━━━━━━━━━━━━

🎁 <b>FREE Premium Alternative:</b>
- Current Points: {premium_points}
- Points Needed: {points_needed}
- Earn 1 Point per Referral!"""

    buttons = [
        [Button.url("🔗 Refer Me", 
         f"https://t.me/share/url?url=t.me/{app.me.username}?start={user_id}")],
        [Button.inline("💎 Get Premium", data="paisa")],
        [Button.inline("💸 Buy with Razorpay", data="razorpay_choose_plan")]
    ]
    
    await event.respond(premium_message, buttons=buttons, parse_mode='html')

@bot.on(events.CallbackQuery(data='razorpay_choose_plan'))
async def choose_plan_handler(event):
    buttons = [
        [Button.inline("Standard (20 Days - ₹49)", data="plan:standard")],
        [Button.inline("Premium (30 Days - ₹69)", data="plan:premium")],
        [Button.inline("Pro (60 Days - ₹129)", data="plan:pro")]
    ]
    await event.edit("💎 Choose a Premium Plan:", buttons=buttons)

@bot.on(events.CallbackQuery(pattern=r'plan:(standard|premium|pro)'))
async def create_payment_handler(event):
    await event.delete()
    user_id = event.sender_id
    plan_type = event.pattern_match.group(1).decode()
    plan = PLANS[plan_type]
    
    try:
        qr = await asyncio.to_thread(
            razor_client.qrcode.create,
            {
                "type": "upi_qr",
                "name": f"{plan_type.capitalize()} Plan",
                "usage": "single_use",
                "fixed_amount": True,
                "payment_amount": plan["amount"],
                "close_by": int(time.time()) + 900
            }
        )
    except Exception as e:
        return await event.answer("❌ Payment gateway error. Please try later.")

    buttons = [
        [Button.url("🆘 Get Help", "https://t.me/nub_coder_s")],
        [Button.inline("✅ I've Paid", data=f"verify:{qr['id']}")]
    ]
    user_dir = f"{ggg}/user_{user_id}"
    os.makedirs(user_dir, exist_ok=True)
    qr_image_response = requests.get(qr["image_url"])
    if qr_image_response.status_code == 200:
       with open(f"{ggg}/user_{user_id}/razorpay_qr.png", "wb") as file:
          file.write(qr_image_response.content)
    else:
        print("Failed to download QR code image.")
    qr_message = await event.respond(
        f"**Scan this QR to pay ₹{plan['amount']/100}:**\n"
        "_(Valid for 15 minutes)_",
        file=qr["image_url"] if not os.path.exists(f"{ggg}/user_{user_id}/razorpay_qr.png") else f"{ggg}/{user_id}/razorpay_qr.png",
        buttons=buttons , attributes=
        DocumentAttributeImageSize(w=400, h=400)  # Adjust dimensions as needed
    )

    asyncio.create_task(payment_status_checker(user_id, qr['id'], plan_type, qr_message))


from telethon.tl.types import DocumentAttributeImageSize


async def payment_status_checker(user_id, qr_id, plan_type, qr_message):
    plan = PLANS[plan_type]
    start_time = time.time()
    ldays = 0
    user_data = collection.find_one({"user_id": user_id})
    stored_time = user_data.get("timestamp", 0)
    time_difference = stored_time - int(time.time())
    if time_difference > 0:
       ldays = time_difference // (24 * 3600)
    while time.time() - start_time < 900:
        await asyncio.sleep(15)
        
        try:
            status = await asyncio.to_thread(razor_client.qrcode.fetch, qr_id)
            if status["payments_amount_received"] >= plan["amount"]:
                # Payment successful
                days = plan["duration"]
                timestamp = int(time.time()) + ((days + ldays) * 24 * 60 * 60)
                print(timestamp)
                # Update user data in the database
                storre_user(user_id, timestamp)
                collection.update_one(
                    {"user_id": user_id},
                    {"$set": {
                        "premium_by": "PAID"
                    }},
                    upsert=True
                )

                # Notify the user
                await bot.send_message(
                    user_id,
                    f"🎉 Premium activated for {plan['duration']} days!\n"
                    "Thank you for your purchase!"
                )

                # Delete the QR code message
                try:
                   await qr_message.delete()
                except:
                  pass
                return
                
        except Exception as e:
            print(f"Payment check error: {e}")

    # Timeout reached
    await bot.send_message(user_id, "⌛ Payment window expired. Please regenerate QR if needed.")
    await qr_message.delete()

@bot.on(events.CallbackQuery(pattern=r'verify:(.*)'))
async def payment_verification_handler(event):
    qr_id = event.pattern_match.group(1).decode()
    
    try:
        status = await asyncio.to_thread(razor_client.qrcode.fetch, qr_id)
        if status["status"] == "closed":
            await event.answer("❌ QR expired. Generate new one.")
        elif status["payments_amount_received"] > 0:
            await event.answer("✅ Payment received! Processing...")
        else:
            await event.answer("⚠️ Payment not detected yet")
    except Exception as e:
        await event.answer("🔴 Verification failed. Contact support.")

@bot.on(events.CallbackQuery(data='paisa'))
async def paisa_handler(event):
    user_id = event.sender_id

    # Retrieve the user's premium points from the database
    user_data = collection.find_one({"user_id": user_id})
    premium_points = user_data.get("premium_points", 0) if user_data else 0

    if premium_points < 20:
        # Not enough points
        await event.answer("🚫 Insufficient points. You need at least 20 premium points to get premium features.")
        return

    # Start a conversation for confirmation with a timeout
    try:
        async with bot.conversation(event.chat_id, timeout=30) as don:
            conversations[event.chat_id] = don
            conv = conversations[event.chat_id]
            # Send a confirmation message
            confirmation_message = (
                "🛒 <b>Confirm Purchase:</b>\n\n"
                "Do you want to buy premium features for 20 premium points?\n\n"
                "✅ <b>Buy</b>\n"
                "❌ <b>Cancel</b>"
            )

            # Send confirmation message with buttons
            response = await event.edit(
                confirmation_message,
                buttons=[
                    [Button.inline("✅ Buy", data="buy")],
                    [Button.inline("❌ Cancel", data="cancel")]
                ],
                parse_mode="html"
            )

            # Handle the user's response
            response = await conv.wait_event(events.CallbackQuery)

            if response.data == b'buy':
                # Update the user's premium status
                timestamp = int(time.time()) + (20 * 24 * 60 * 60)
                storre_user(user_id, timestamp)
                collection.update_one(
                    {"user_id": user_id},
                    {"$inc": {"premium_points": -5}},
                    upsert=True
                )
                collection.update_one(
                {"user_id": user_id},
                {"$set": {"premium_by": "REFERRAL"}},
                upsert=True
            )
                # Send a successful purchase message
                await response.edit(
                    "🎉 <b>Purchase Successful!</b> 🎉\n\n"
                    "You have successfully purchased premium features. Enjoy the enhanced functionality! "
                    "Your premium access will last for 30 days.\n\n"
                    "If you have any questions or issues, feel free to contact us."
                )
            else:
                # Handle cancellation
                await event.edit("🚫 Purchase cancelled.")

    except asyncio.TimeoutError:
        # Handle timeout scenario
        await event.edit("⏳ <b>Timeout:</b> The purchase confirmation has timed out. Please try again.",parse_mode='html')


@bot.on(events.NewMessage(pattern='/profile'))
async def user_status(event):
    command_args = event.raw_text.split()
    if event.is_reply:
        replied_msg = await event.get_reply_message()
        if replied_msg.sender_id is not None:
            user_id = replied_msg.sender_id
        else:
            return await event.reply("Cannot get the replied user.")

    # Extract user_id from the command argument
    elif len(command_args) > 1:
        arg = command_args[1]
        if arg.isdigit():
            user_id = int(arg)
        else:
            try:
                # Resolve username to user_id
                user_id = (await client.get_entity(arg)).id
            except ValueError:
                return await event.reply("Cannot find user with the provided username.")
    else:
        user_id = event.sender_id
    current_time = int(time.time())
    user_data = collection.find_one({"user_id": user_id})

# Calculate the difference
    if user_data:
        stored_time = user_data.get("timestamp", 0)
        time_difference = stored_time - current_time
        if time_difference > 0:
            days = time_difference // (24 * 3600)
            hours = (time_difference % (24 * 3600)) // 3600
            minutes = (time_difference % 3600) // 60
            premium_by = user_data.get("premium_by", "TRIAL")
            status_message = f"""
┏━━━ 👑 <b>VIP STATUS</b> ━━━

🌟 <b>Premium Member Verified!</b>

⏳ <b>Time Remaining:</b>
• {days} days
• {hours} hours
• {minutes} minutes

💎 <b>Subscription Type:</b> {premium_by}

✨ <b>Enjoying all premium features!</b>
┗━━━━━━━━━━━━━━━━━━
"""
        else:
           status_message = f"""
┏━━━ 👤 <b>USER STATUS</b>

🔵 <b>Current Status:</b> Regular User

🎯 <b>Available Plans:</b>

┏━━━━━━━━━━━━━━━━━
┣ 📍 Standard Plan
┣ • Duration: 20 Days
┣ • Price: ₹49 ($0.61)
┣ • Cost per day: ₹2.45
┗━━━━━━━━━━━━━━━━━

┏━━━━━━━━━━━━━━━━━
┣ 📍 Premium Plan
┣ • Duration: 30 Days
┣ • Price: ₹69 ($0.86)
┣ • Cost per day: ₹2.30
┣ • Save 5.9% vs Standard
┗━━━━━━━━━━━━━━━━━

┏━━━━━━━━━━━━━━━━━
┣ 📍 Pro Plan
┣ • Duration: 60 Days
┣ • Price: ₹129 ($1.65)
┣ • Cost per day: ₹2.15
┣ • Save 12.13% vs Standard
┗━━━━━━━━━━━━━━━━━

🚀 <b>What You'll Get:</b>
• Broadcast Feature
• Sudo Commands
• Advanced Management
• Priority Support
• Custom Commands
• Exclusive Updates

💫 <b>How to Get Premium:</b>
• Buy Directly
• Earn through Referrals
• 1 Point per Referral!

📌 Use /plans for more details
┗━━━━━━━━━━━━━━━━━━
"""
    else:
           status_message = f"""
┏━━━ 👋 <b>WELCOME</b> ━━━┓

🔵 <b>Current Status:</b> Regular User

🎯 <b>Choose Your Plan:</b>

┏━━━━━━━━━━━━━━━━━
┣ 📍 Standard Plan
┣ • Duration: 20 Days
┣ • Price: ₹49 ($0.61)
┣ • Cost per day: ₹2.45
┗━━━━━━━━━━━━━━━━━

┏━━━━━━━━━━━━━━━━━
┣ 📍 Premium Plan
┣ • Duration: 30 Days
┣ • Price: ₹69 ($0.86)
┣ • Cost per day: ₹2.30
┣ • Save 5.9% vs Standard
┗━━━━━━━━━━━━━━━━━

┏━━━━━━━━━━━━━━━━━
┣ 📍 Pro Plan
┣ • Duration: 60 Days
┣ • Price: ₹129 ($1.65)
┣ • Cost per day: ₹2.15
┣ • Save 12.13% vs Standard
┗━━━━━━━━━━━━━━━━━

✨ <b>Premium Features:</b>
• Broadcasting Power
• Sudo Commands
• Priority Support
• Advanced Tools
• Custom Commands
• Regular Updates

💎 <b>Get Started:</b>
• Purchase Directly
• Or Earn Free with Referrals

📌 Use /plans to upgrade now!
┗━━━━━━━━━━━━━━━━━━
"""

    await event.respond(status_message, parse_mode='html')


#@app.on_message(filters.command("stats"))
async def status_command_handler(client, message):
  user_id = message.from_user.id
  admin_file = f"{ggg}/admin.txt"
  if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if not message.from_user.id in admin_ids:
                 return await message.reply(f"**MF\n\nTHIS IS OWNER'S COMMAND...**")
  await status(client, message)


@bot.on(events.NewMessage(pattern='/give_auth'))
async def authorize_user(event):
    user_id = None
    days = 30  # Default days
    command_args = event.raw_text.split()

    # Verify admin status
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if event.sender_id not in admin_ids:
                return

    # Handle reply scenario
    if event.is_reply:
        replied_msg = await event.get_reply_message()
        if replied_msg.sender_id is not None:
            user_id = replied_msg.sender_id
            # Check if second argument exists and is a valid number for days
            if len(command_args) > 1 and command_args[1].isdigit():
                days = int(command_args[1])
        else:
            return await event.reply("Cannot authorize user: Unknown user ID.")
    
    # Handle non-reply scenario
    else:
        if len(command_args) < 2:
            return await event.reply("Please provide a user ID or username\nFormat: /give_auth <user_id/username> [days]")
        
        # Try to get user_id from second argument
        arg = command_args[1]
        if arg.isdigit():
            user_id = int(arg)
        else:
            try:
                user_id = (await client.get_entity(arg)).id
            except ValueError:
                return await event.reply("Cannot find user with the provided username.")
        
        # Check if third argument exists and is a valid number for days
        if len(command_args) > 2 and command_args[2].isdigit():
            days = int(command_args[2])

    if user_id is None:
        return await event.reply("Failed to determine user ID.")

    # Calculate timestamp
    timestamp = int(time.time()) + (days * 24 * 60 * 60)
    
    # Store user data
    storre_user(user_id, timestamp)
    collection.update_one(
                {"user_id": user_id},
                {"$set": {"premium_by": "PAID"}},
                upsert=True
            )

    await event.reply(f"Provided user with {days} days of bot's premium")


@bot.on(events.NewMessage(pattern='/rstplan'))
async def unauthorize_user(event):
    user_id = event.sender_id

    # Check if the user is an admin by comparing their user ID with the ones in admin.txt
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return
    if event.is_reply:
        replied_msg = await event.get_reply_message()
        if replied_msg.sender_id is not None:
            user_id = replied_msg.sender_id
        else:
            return await event.reply("Cannot authorize user: Unknown user ID.")
    command_args = event.raw_text.split()
    if len(command_args) > 1:
        arg = command_args[1]
        if arg.isdigit():
            user_id = int(arg)
        else:
            try:
                user_id = (await client.get_entity(arg)).id
            except ValueError:
                return await event.reply("Cannot find user with the provided username.")

    # Store the user with a timestamp 30 days from now
    timestamp = int(time.time()) - 12600
    storre_user(user_id, timestamp)
    user_data = collection.find_one({"user_id": user_id})
    await event.reply(f"User resetted successfully.\nUserdata:{user_data}")


# Run the main function

# Entry point for the asyncio program

    #
app.start()
print(app.me.username)
#bot.loop.run_until_complete(run_all_clients())
import time
from pyrogram import Client
from pyrogram.errors import FloodWait, RPCError


def start_bot():
    while True:
        try:
            print("Starting userbot...")
            app.run()
        except FloodWait as e:
            print(f"Rate limited! Sleeping for {e.value} seconds.")
            time.sleep(e.value)
        except OSError as e:
            print(f"Connection lost! Reconnecting in 5 seconds... Error: {e}")
            time.sleep(5)
        except RPCError as e:
            print(f"Pyrogram error: {e}. Restarting in 10 seconds...")
            time.sleep(10)
        except Exception as e:
            print(f"Unexpected error: {e}. Restarting in 10 seconds...")
            time.sleep(10)


bot.run_until_disconnected()
#if __name__ == "__main__":
#    start_bot()
