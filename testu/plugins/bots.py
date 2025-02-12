import sys
import asyncio
import os
from tools import *
from fonts import *
from pyrogram import enums
from pyrogram import Client, filters
from pytgcalls.types import ChatUpdate
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message, ChatPrivileges
from pyrogram.enums import ChatType, ChatMemberStatus
from pyrogram.errors.exceptions import InviteHashExpired , ChannelPrivate ,GroupcallForbidden, UserBlocked, PeerIdInvalid, MessageDeleteForbidden
from pytgcalls.exceptions import NotInCallError
from config import *
import time
from pyrogram.types import InputMediaPhoto, InputMediaVideo, InputMediaAudio
from pyrogram.types import Message, CallbackQuery
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait
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
from telethon import TelegramClient, events
import yt_dlp
import time

from functools import wraps
from pyrogram.types import CallbackQuery, Message
from pyrogram.enums import ChatMemberStatus


def retry(max_retries=3, initial_delay=5, backoff=2, exceptions=(FloodWait, OSError)):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            retries = 0
            delay = initial_delay
            while retries < max_retries:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    retries += 1
                    wait = e.value if isinstance(e, FloodWait) else delay
                    print(f"Retry {retries}/{max_retries} for {func.__name__} after {wait}s")
                    await asyncio.sleep(wait)
                    delay *= backoff
                except Exception as e:
                    print(f"Unexpected error in {func.__name__}: {str(e)}")
                    raise
            return await func(*args, **kwargs)
        return wrapper
    return decorator


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


def premium_only():
    def decorator(func):
        @wraps(func)
        async def wrapper(user_client, update):
            try:
                owner_id = get_owner_id_by_client(user_client)
                
                if not is_premium(owner_id):
                    try:
                        owner = await user_client.get_users(owner_id)
                        owner_mention = f"@{owner.username}" if owner.username else f"[{owner.first_name}](tg://user?id={owner_id})"
                    except Exception:
                        owner_mention = f"[Owner](tg://user?id={owner_id})"
                    
                    await update.reply(f"⚠️ Trial period ended. Please contact {owner_mention} to restart the bot.")
                    
                    return await stop_user(owner_id)
                
                return await func(user_client, update)
            
            except Exception as e:
                return
        return wrapper
    return decorator

def admin_only():
    def decorator(func):
        @wraps(func)
        async def wrapper(user_client, update):
            try:
                chat_id = update.message.chat.id if isinstance(update, CallbackQuery) else update.chat.id
                user_id = update.from_user.id if update.from_user else None
                reply_id = update.message.id if isinstance(update, CallbackQuery) else update.id
                user_data = user_sessions.find_one({"user_id": get_owner_id_by_client(user_client)})
                sudoers = user_data.get("SUDOERS", [])

                is_admin = False
                admin_file = f"{ggg}/admin.txt"
                if os.path.exists(admin_file):
                  with open(admin_file, "r") as file:
                     admin_ids = [int(line.strip()) for line in file.readlines()]
                     is_admin = user_id in admin_ids

    # Check permissions
                is_auth_user = False
                auth_users = user_data.get('auth_users', {})
                if isinstance(auth_users, dict) and str(chat_id) in auth_users:
                    is_auth_user = user_id in auth_users[str(chat_id)]
                if not isinstance(update, CallbackQuery):
                  if update.command == 'del':
                      is_auth_user = False

                is_authorized = (
                is_admin or get_user_id_by_client(user_id, user_client) or user_id in sudoers or is_auth_user)
                if not user_id:
                    linked_chat = await user_client.get_chat(chat_id)
                    if linked_chat.linked_chat and update.sender_chat.id == linked_chat.linked_chat.id:
                        return await func(user_client, update)
                    await update.reply("⚠️ Cannot verify admin status from unknown user.", reply_to_message_id=reply_id)
                    return

                chat_member = await user_client.get_chat_member(chat_id, user_id)
                if chat_member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR) or is_authorized:
                    return await func(user_client, update)
                if isinstance(update, CallbackQuery):
                    await update.answer("⚠️ This action is restricted to admins only.", show_alert=True)
                else:
                    await update.reply("⚠️ This command is restricted to admins only.", reply_to_message_id=reply_id)
                return
                
            except Exception as e:
                error_msg = f"Error checking admin status: {str(e)}"
                return print(error_msg)
        return wrapper
    return decorator



def single_client_only():
    def decorator(func):
        @wraps(func)
        async def wrapper(client, update):
                user_client = clients.get(get_owner_id_by_client(client))
                if user_client:
                    if user_client.name == client.name:
                        return await func(client, update)
                    print("Stopping bot")
                return await client.stop()
        return wrapper
    return decorator
# Define the main bot client (app)
create_custom_filter = filters.create(lambda _, __, message: any(m.is_self for m in (message.new_chat_members if message.new_chat_members else [])))

# Auth handler

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



from functools import wraps
from typing import Tuple, Optional

# Example usage:
async def is_active_chat(user_client,chat_id):
    if chat_id not in active[user_client.me.username]:
        return False
    else:
        return True


async def add_active_chat(user_client,chat_id):
    if chat_id not in active[user_client.me.username]:
        active[user_client.me.username].append(chat_id)



@Client.on_message(filters.command("ac"))
@retry()
@single_client_only()
async def active_chats(client, message):
    admin_file = f"{ggg}/admin.txt"
    user_id = message.from_user.id
    users_data = user_sessions.find_one({"user_id": get_owner_id_by_client(client)})
    sudoers = users_data.get("SUDOERS", [])
    premium_by = collection.find_one({"user_id": get_owner_id_by_client(client)}, {"premium_by": 1}).get("premium_by", "TRIAL")

    is_admin = False
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            is_admin = user_id in admin_ids

    # Check permissions
    is_authorized = (
        is_admin or
        get_user_id_by_client(user_id, client) or
        (user_id in sudoers and premium_by == "PAID")
    )

    if not is_authorized:
        return await message.reply("**MF\n\nTHIS IS OWNER/SUDOER'S COMMAND...**")


    if active[client.me.username]:
        await message.reply_text(f"<b>Active voice chats:\n<blockquote>{len(active[client.me.username])}</blockquote>")
    else:
         await message.reply_text(f"<b>Active voice chats:\n<blockquote>0</blockquote>")


async def remove_active_chat(user_client, chat_id):
    if chat_id in active[user_client.me.username]:
        active[user_client.me.username].remove(chat_id)




@Client.on_message(filters.command("tagall") & filters.group)
@retry()
@single_client_only()
@admin_only()
async def mentionall(client, message):
    await message.delete()
    chat_id = message.chat.id
    direp = message.reply_to_message
    args = get_arg(message)
    if not direp and not args:
        return await message.reply("**Give a message or reply to any message!**")

    spam_chats.append(chat_id)
    usrnum = 0
    usrtxt = ""
    async for usr in client.get_chat_members(chat_id):
        if not chat_id in spam_chats:
            break
        usrnum += 1
        usrtxt += f"{usr.user.mention()}, "
        if usrnum == 5:
            if args:
                txt = f"<blockquote>{args}\n\n{usrtxt}</blockquote>"
                await client.send_message(chat_id, txt)
            elif direp:
                await direp.reply(f"<blockquote>{usrtxt}</blockquote>")
            await asyncio.sleep(5)
            usrnum = 0
            usrtxt = ""
    try:
        spam_chats.remove(chat_id)
    except:
        pass


@Client.on_message(filters.command(["seek", "seekback"]))
@retry()
@single_client_only()
@admin_only()
async def seek_handler_func(user_client, message):
    try:
        await message.delete()
    except:
        pass
    # Check if user is banned
    user_data = collection.find_one({"user_id": user_client.me.id})
    busers = user_data.get('busers', {})
    if message.from_user.id in busers:
        return

    try:
        # Get seek value from command
        command_parts = message.text.split()
        if len(command_parts) != 2:
            await user_client.send_message(
                message.chat.id,
                "❌ Please specify the seek time in seconds.\nUsage: /seek (seconds)"
            )
            return

        try:
            seek_value = int(command_parts[1])
            if seek_value < 0:
                await user_client.send_message(
                    message.chat.id,
                    f"{upper_mono('❌ Seek time cannot be negative!')}"
                )
                return
        except ValueError:
            await user_client.send_message(
                message.chat.id,
                f"{upper_mono('❌ Please provide a valid number of seconds!')}"
            )
            return

        # Check if there's a song playing
        if message.chat.id in playing and playing[message.chat.id]:
            current_song = playing[message.chat.id]
            duration_str = str(current_song['duration'])

            # Convert HH:MM:SS to total seconds
            duration_seconds = sum(
                int(x) * 60 ** i
                for i, x in enumerate(reversed(duration_str.split(":")))
            )

            # Get session client
            bot_username = user_client.me.username
            session_client_id = connector.get(bot_username)
            if session_client_id is None:
                await user_client.send_message(
                    message.chat.id,
                    f"{upper_mono('No session client connected. Please authorize first with /host.')}"
                )
                return await remove_active_chat(user_client, message.chat.id)

            # Get call client
            session_client = clients.get(f"{session_client_id}_session")
            call_py = songs_client.get(session_client.me.id)

            # Check if bot is actually streaming by fetching elapsed time
            if message.chat.id not in played:
                await user_client.send_message(
                    message.chat.id,
                    f"{upper_mono('Assistant is not streaming anything!')}"
                )
                return

            played_in_seconds = int(time.time() - played[message.chat.id])

            # Check seek boundaries based on command
            command = command_parts[0].lower()
            if command == "/seek":
                # Check if seeking forward would exceed remaining duration
                remaining_duration = duration_seconds - played_in_seconds
                if seek_value > remaining_duration:
                    await user_client.send_message(
                        message.chat.id,
                        f"{upper_mono('❌ Cannot seek beyond the remaining duration!')}"
                    )
                    return
                total_seek = seek_value + played_in_seconds
            else:  # seekback
                # Check if seeking back would exceed played duration
                if seek_value > played_in_seconds:
                    await user_client.send_message(
                        message.chat.id,
                        f"{upper_mono('❌ Cannot seek back more than the played duration!')}"
                    )
                    return
                total_seek = played_in_seconds - seek_value

            # Set audio flags based on mode
            mode = current_song['mode']
            audio_flags = MediaStream.Flags.IGNORE if mode == "audio" else None

            # Seek to specified position
            to_seek = format_duration(total_seek)
            await call_py.play(
                message.chat.id,
                MediaStream(
                    current_song['yt_link'],
                    AudioQuality.STUDIO,
                    VideoQuality.HD_720p,
                    video_flags=audio_flags,
                    ytdlp_parameters='--cookies cookies.txt',
                    ffmpeg_parameters=f"-ss {to_seek} -to {duration_str}"
                ),
            )

            # Update played time based on command
            if command == "/seek":
                played[message.chat.id] -= seek_value
            else:  # seekback
                played[message.chat.id] += seek_value

            await user_client.send_message(
                message.chat.id,
                f"{upper_mono(f'Seeked to {to_seek}!')}\n\nʙʏ: {message.from_user.mention()}"
            )
        else:
            await user_client.send_message(
                message.chat.id,
                f"{upper_mono('Assistant is not streaming anything!')}"
            )
    except Exception as e:
        await user_client.send_message(
            message.chat.id,
            f"{upper_mono('❌ An error occurred:')} {str(e)}"
        )


@Client.on_message(filters.command("cancel") & filters.group)
@retry()
@single_client_only()
@admin_only()
async def cancel_spam(client, message):
    if not message.chat.id in spam_chats:
        return await message.reply("**Looks like there is no tagall here.**")
    else:
        try:
            spam_chats.remove(message.chat.id)
        except:
            pass
        return await message.reply("**Dismissing Mention.**")

@Client.on_message(filters.command("del") & filters.group)
@retry()
@single_client_only()
@admin_only()
async def delete_message_handler(client, message):
    # Check if the message is a reply
    if message.reply_to_message:
        try:
            # Delete the replied message
            await message.reply_to_message.delete()
            # Optionally, delete the command message as well
            await message.delete()
        except MessageDeleteForbidden:
              pass
        except Exception as e:
            await message.reply(f"Error deleting message: {str(e)}")
    else:
        await message.reply("**Please reply to a message to delete it.**")


@Client.on_message(filters.command("auth") & filters.group)
@retry()
@single_client_only()
@admin_only()
async def auth_user(client, message):
    admin_file = f"{ggg}/admin.txt"
    user_id = message.from_user.id
    user_data = user_sessions.find_one({"user_id": get_owner_id_by_client(client)})
    sudoers = user_data.get("SUDOERS", [])
    
    # Check if user is admin

    
    chat_id = message.chat.id
    auth_users = user_data.get('auth_users', {})
    
    # Convert auth_users to dict if it's not already (for backward compatibility)
    if not isinstance(auth_users, dict):
        auth_users = {}
    
    # Initialize empty list for chat_id if it doesn't exist
    if str(chat_id) not in auth_users:
        auth_users[str(chat_id)] = []
    
    if message.reply_to_message:
        replied_message = message.reply_to_message
        if replied_message.from_user:
            replied_user_id = replied_message.from_user.id
            
            # Check if replied user is admin
            if os.path.exists(admin_file):
                with open(admin_file, "r") as file:
                    admin_ids = [int(line.strip()) for line in file.readlines()]
                    if replied_user_id in admin_ids:
                        return await message.reply(f"**Owner is already authorized everywhere.**")
            
            # Check if user can be authorized
            if (replied_user_id != message.chat.id and 
                not replied_message.from_user.is_self and 
                not get_user_id_by_client(replied_user_id, client)):
                
                # Check if user is already authorized in this chat
                if replied_user_id not in auth_users[str(chat_id)]:
                    auth_users[str(chat_id)].append(replied_user_id)
                    user_sessions.update_one(
                        {"user_id": get_owner_id_by_client(client)},
                        {"$set": {'auth_users': auth_users}},
                        upsert=True
                    )
                    await message.reply(f"User {replied_user_id} has been authorized in this chat.")
                else:
                    await message.reply(f"User {replied_user_id} is already authorized in this chat.")
            else:
                await message.reply("You cannot authorize yourself or an anonymous user.")
        else:
            await message.reply("The replied message is not from a user.")
    else:
        # If not a reply, check if a user ID is provided in the command
        command_parts = message.text.split()
        if len(command_parts) > 1:
            try:
                user_id_to_auth = int(command_parts[1])
                # Check if user is already authorized in this chat
                if user_id_to_auth not in auth_users[str(chat_id)]:
                    auth_users[str(chat_id)].append(user_id_to_auth)
                    user_sessions.update_one(
                        {"user_id": get_owner_id_by_client(client)},
                        {"$set": {'auth_users': auth_users}},
                        upsert=True
                    )
                    await message.reply(f"User {user_id_to_auth} has been authorized in this chat.")
                else:
                    await message.reply(f"User {user_id_to_auth} is already authorized in this chat.")
            except ValueError:
                await message.reply("Please provide a valid user ID.")
        else:
            await message.reply("You need to reply to a message or provide a user ID.")

@Client.on_message(filters.command("unauth") & filters.group)
@retry()
@single_client_only()
@admin_only()
async def unauth_user(client, message):
    admin_file = f"{ggg}/admin.txt"
    user_id = message.from_user.id
    user_data = user_sessions.find_one({"user_id": get_owner_id_by_client(client)})

    chat_id = message.chat.id
    auth_users = user_data.get('auth_users', {})
    
    # Convert auth_users to dict if it's not already (for backward compatibility)
    if not isinstance(auth_users, dict):
        auth_users = {}
    
    # Initialize empty list for chat_id if it doesn't exist
    if str(chat_id) not in auth_users:
        auth_users[str(chat_id)] = []
    
    if message.reply_to_message:
        replied_message = message.reply_to_message
        if replied_message.from_user:
            replied_user_id = replied_message.from_user.id
            
            # Check if replied user is admin
            if os.path.exists(admin_file):
                with open(admin_file, "r") as file:
                    admin_ids = [int(line.strip()) for line in file.readlines()]
                    if replied_user_id in admin_ids:
                        return await message.reply(f"**You can't remove authorization from owner.**")
            
            # Check if user can be unauthorized
            if replied_user_id in auth_users[str(chat_id)]:
                auth_users[str(chat_id)].remove(replied_user_id)
                user_sessions.update_one(
                    {"user_id": get_owner_id_by_client(client)},
                    {"$set": {'auth_users': auth_users}},
                    upsert=True
                )
                await message.reply(f"User {replied_user_id} has been removed from authorized users in this chat.")
            else:
                await message.reply(f"User {replied_user_id} is not authorized in this chat.")
        else:
            await message.reply("The replied message is not from a user.")
    else:
        # If not a reply, check if a user ID is provided in the command
        command_parts = message.text.split()
        if len(command_parts) > 1:
            try:
                user_id_to_unauth = int(command_parts[1])
                # Check if user is authorized in this chat
                if user_id_to_unauth in auth_users[str(chat_id)]:
                    auth_users[str(chat_id)].remove(user_id_to_unauth)
                    user_sessions.update_one(
                        {"user_id": get_owner_id_by_client(client)},
                        {"$set": {'auth_users': auth_users}},
                        upsert=True
                    )
                    await message.reply(f"User {user_id_to_unauth} has been removed from authorized users in this chat.")
                else:
                    await message.reply(f"User {user_id_to_unauth} is not authorized in this chat.")
            except ValueError:
                await message.reply("Please provide a valid user ID.")
        else:
            await message.reply("You need to reply to a message or provide a user ID.")

@Client.on_message(filters.command("block"))
@retry()
@single_client_only()
async def block_user(client, message):
    admin_file = f"{ggg}/admin.txt"
    user_id = message.from_user.id
    users_data = user_sessions.find_one({"user_id": get_owner_id_by_client(client)})
    sudoers = users_data.get("SUDOERS", [])
    premium_by = collection.find_one({"user_id": get_owner_id_by_client(client)}, {"premium_by": 1}).get("premium_by", "TRIAL")

    is_admin = False
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            is_admin = user_id in admin_ids

    # Check permissions
    is_authorized = (
        is_admin or
        get_user_id_by_client(user_id, client) or
        (user_id in sudoers and premium_by == "PAID")
    )

    if not is_authorized:
        return await message.reply("**MF\n\nTHIS IS OWNER/SUDOER'S COMMAND...**")

    # Check if the message is a reply


    user_data = collection.find_one({"user_id": client.me.id})
    busers = user_data.get('busers', {}) if user_data else []
    if message.reply_to_message:
        replied_message = message.reply_to_message
        # If the replied message is from a user (and not from the bot itself)
        if replied_message.from_user:
            replied_user_id = replied_message.from_user.id
            admin_file = f"{ggg}/admin.txt"
            if os.path.exists(admin_file):
               with open(admin_file, "r") as file:
                 admin_ids = [int(line.strip()) for line in file.readlines()]
                 if replied_user_id in admin_ids:
                     return await message.reply(f"**MF\n\nYou can't block my owner.**")
            # Check if the replied user is the same as the current chat (group) id
            if replied_user_id != message.chat.id and not replied_message.from_user.is_self and not get_user_id_by_client(replied_user_id, client):
                if not replied_user_id in busers:
                    collection.update_one({"user_id": client.me.id},
                                        {"$push": {'busers': replied_user_id}},
                                        upsert=True)
                else:
                   return await message.reply(f"User {replied_user_id} already in the blocklist.")
                await message.reply(f"User {replied_user_id} has been added to blocklist.")
            else:
                await message.reply("You cannot block yourself or a anonymous user")
        else:
            await message.reply("The replied message is not from a user.")
    else:
        # If not a reply, check if a user ID is provided in the command
        command_parts = message.text.split()
        if len(command_parts) > 1:
            try:
                user_id = int(command_parts[1])
                # Block the user with the provided user ID
                if not user_id in busers:
                    collection.update_one({"user_id": client.me.id},
                                        {"$push": {'busers': user_id}},
                                        upsert=True
                                    )
                else:
                   return await message.reply(f"User {user_id} already in the blocklist.")
                await message.reply(f"User {user_id} has been added to blocklist.")
            except ValueError:
                await message.reply("Please provide a valid user ID.")
        else:
            await message.reply("You need to reply to a message or provide a user ID.")

# Start the bot

@Client.on_message(filters.command("unblock"))
@retry()
@single_client_only()
async def unblock_user(client, message):
    # Check if the message is a reply
    admin_file = f"{ggg}/admin.txt"
    user_id = message.from_user.id
    users_data = user_sessions.find_one({"user_id": get_owner_id_by_client(client)})
    sudoers = users_data.get("SUDOERS", [])
    premium_by = collection.find_one({"user_id": get_owner_id_by_client(client)}, {"premium_by": 1}).get("premium_by", "TRIAL")

    is_admin = False
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            is_admin = user_id in admin_ids

    # Check permissions
    is_authorized = (
        is_admin or
        get_user_id_by_client(user_id, client) or
        (user_id in sudoers and premium_by == "PAID")
    )

    if not is_authorized:
        return await message.reply("**MF\n\nTHIS IS OWNER/SUDOER'S COMMAND...**")

    user_data = collection.find_one({"user_id": client.me.id})
    busers = user_data.get('busers', {}) if user_data else []
    if message.reply_to_message:
        replied_message = message.reply_to_message
        # If the replied message is from a user (and not from the bot itself)
        replied_user_id = replied_message.from_user.id
            # Check if the replied user is the same as the current chat (group) id
        if replied_user_id in busers:
               collection.update_one({"user_id": client.me.id},
                                        {"$pull": {'busers': replied_user_id}},
                                        upsert=True
                                    )
               await message.reply(f"User {replied_user_id} has been removed from blocklist.")
        else:
              return await message.reply(f"User {replied_user_id} not in the blocklist.")

    else:
        # If not a reply, check if a user ID is provided in the command
        command_parts = message.text.split()
        if len(command_parts) > 1:
            try:
                user_id = int(command_parts[1])
                # Block the user with the provided user ID
                if user_id in busers:
                    collection.update_one({"user_id": client.me.id},
                                        {"$pull": {'busers': user_id}},
                                        upsert=True
                                    )
                else:
                   return await message.reply(f"User {user_id} not in the blocklist.")
                await message.reply(f"User {user_id} has been removed from blocklist.")
            except ValueError:
                await message.reply("Please provide a valid user ID.")
        else:
            await message.reply("You need to reply to a message or provide a user ID.")


@Client.on_message(filters.command("sudolist"))
@retry()
@single_client_only()
async def show_sudo_list(client, message):
    # Check admin permissions
    admin_file = f"{ggg}/admin.txt"
    user_id = message.from_user.id
    owner_id = get_owner_id_by_client(client)
    # Get premium status of the command sender
    premium_by = collection.find_one({"user_id": user_id}, {"premium_by": 1}).get("premium_by", "PAID")
    
    is_admin = False
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            is_admin = user_id in admin_ids

    # Check permissions - must be admin/verified AND have PAID status
    is_authorized = is_admin or (get_user_id_by_client(user_id, client) and premium_by == "PAID")

    if not is_authorized:
        return await message.reply("**MF\n\nTHIS IS PAID OWNER'S COMMAND...**")
    
    try:
        # Get all users who have SUDOERS field
        sudo_users = user_sessions.find_one({"user_id": owner_id}).get("SUDOERS", []) if user_sessions.find_one({"user_id": owner_id}) else []
        
        if not sudo_users:
            return await message.reply("No sudo users found in the database.")
        
        # Build the sudo list message
        sudo_list = ["**🔱 SUDO USERS LIST:**\n"]
        number = 1
        
        for user_id in sudo_users:
                try:
                    # Try to get user info from Telegram
                    user_info = await client.get_users(user_id)
                    user_mention = f"@{user_info.username}" if user_info.username else user_info.first_name
                    sudo_list.append(f"**{number}➤** {user_mention} [`{user_id}`]")
                except Exception:
                    # If can't get user info, just show the ID
                    sudo_list.append(f"**{number}➤** Unknown User [`{user_id}`]")
                number += 1
        
        # Add count at the bottom
        sudo_list.append(f"\n**Total SUDO Users:** `{number-1}`")
        
        # Send the message
        await message.reply("\n".join(sudo_list))
        
    except Exception as e:
        await message.reply(f"An error occurred while fetching sudo list: {str(e)}")


@Client.on_message(filters.command("addsudo"))
@retry()
@single_client_only()
async def add_to_sudo(client, message):
    # Check admin permissions
    admin_file = f"{ggg}/admin.txt"
    user_id = message.from_user.id

    # Get premium status of the command sender
    owner_id = get_owner_id_by_client(client)
    premium_by = collection.find_one({"user_id": owner_id}, {"premium_by": 1}).get("premium_by", "TRIAL")

    is_admin = False
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            is_admin = user_id in admin_ids
    
    is_authorized = is_admin or (get_user_id_by_client(user_id, client) and premium_by == "PAID")

    if not is_authorized:
        return await message.reply("**MF\n\nTHIS IS PAID OWNER'S COMMAND...**")

    if message.reply_to_message:
        replied_message = message.reply_to_message
        if replied_message.from_user:
            replied_user_id = replied_message.from_user.id

            # Check if target user is already admin
            if os.path.exists(admin_file):
                with open(admin_file, "r") as file:
                    admin_ids = [int(line.strip()) for line in file.readlines()]
                    if replied_user_id in admin_ids:
                        return await message.reply(f"**This user is already an owner!**")

            # Check if trying to add self or bot
            if replied_user_id != message.chat.id and not replied_message.from_user.is_self:
                # Get current sudo users
                users_data = user_sessions.find_one({"user_id": owner_id})

                sudoers = users_data.get("SUDOERS", [])

                if replied_user_id not in sudoers:
                    # Add user to sudoers
                    user_sessions.update_one(
                        {"user_id": owner_id},
                        {"$push": {"SUDOERS": replied_user_id}},
                        upsert=True
                    )
                    await message.reply(f"User {replied_user_id} has been added to sudoers list.")
                else:
                    await message.reply(f"User {replied_user_id} is already in sudoers list.")
            else:
                await message.reply("You cannot add yourself or the bot to sudoers.")
        else:
            await message.reply("The replied message is not from a user.")
    else:
        # Handle command with user ID
        command_parts = message.text.split()
        if len(command_parts) > 1:
            try:
                target_user_id = int(command_parts[1])

                # Check if target user is already admin
                if os.path.exists(admin_file):
                    with open(admin_file, "r") as file:
                        admin_ids = [int(line.strip()) for line in file.readlines()]
                        if target_user_id in admin_ids:
                            return await message.reply(f"**This user is already an owner!**")

                # Get current sudo users
                users_data = user_sessions.find_one({"user_id": owner_id})

                sudoers = users_data.get("SUDOERS", [])

                if target_user_id not in sudoers:
                    # Add user to sudoers
                    user_sessions.update_one(
                        {"user_id": owner_id},
                        {"$push": {"SUDOERS": target_user_id}},
                        upsert=True
                    )
                    await message.reply(f"User {target_user_id} has been added to sudoers list.")
                else:
                    await message.reply(f"User {target_user_id} is already in sudoers list.")
            except ValueError:
                await message.reply("Please provide a valid user ID.")
        else:
            await message.reply("You need to reply to a message or provide a user ID.")

@Client.on_message(filters.command("rmsudo"))
@retry()
@single_client_only()
async def remove_from_sudo(client, message):
    # Check admin permissions
    admin_file = f"{ggg}/admin.txt"
    user_id = message.from_user.id

    is_admin = False
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            is_admin = user_id in admin_ids

    # Check permissions - only admin or verified users can remove from sudo
    owner_id = get_owner_id_by_client(client)
    is_authorized = is_admin or (user_id == owner_id)

    if not is_authorized:
        return await message.reply("**MF\n\nTHIS IS OWNER'S COMMAND...**")

    # Handle reply to message
    if message.reply_to_message:
        replied_message = message.reply_to_message
        if replied_message.from_user:
            replied_user_id = replied_message.from_user.id

            # Check if target user is an admin
            if os.path.exists(admin_file):
                with open(admin_file, "r") as file:
                    admin_ids = [int(line.strip()) for line in file.readlines()]
                    if replied_user_id in admin_ids:
                        return await message.reply(f"**Cannot remove an owner from sudo list!**")

            # Check if trying to remove self or bot
            if replied_user_id != message.chat.id and not replied_message.from_user.is_self:
                # Get current sudo users
                users_data = user_sessions.find_one({"user_id": owner_id})
                if not users_data:
                    return await message.reply(f"User {replied_user_id} is not in the database.")

                sudoers = users_data.get("SUDOERS", [])

                if replied_user_id in sudoers:
                    # Remove user from sudoers
                    user_sessions.update_one(
                        {"user_id": owner_id},
                        {"$pull": {"SUDOERS": replied_user_id}}
                    )
                    await message.reply(f"User {replied_user_id} has been removed from sudoers list.")
                else:
                    await message.reply(f"User {replied_user_id} is not in sudoers list.")
            else:
                await message.reply("You cannot remove yourself or the bot from sudoers.")
        else:
            await message.reply("The replied message is not from a user.")
    else:
        # Handle command with user ID
        command_parts = message.text.split()
        if len(command_parts) > 1:
            try:
                target_user_id = int(command_parts[1])

                # Check if target user is an admin
                if os.path.exists(admin_file):
                    with open(admin_file, "r") as file:
                        admin_ids = [int(line.strip()) for line in file.readlines()]
                        if target_user_id in admin_ids:
                            return await message.reply(f"**Cannot remove an owner from sudo list!**")

                # Get current sudo users
                users_data = user_sessions.find_one({"user_id": owner_id})
                if not users_data:
                    return await message.reply(f"User {target_user_id} is not in the database.")

                sudoers = users_data.get("SUDOERS", [])

                if target_user_id in sudoers:
                    # Remove user from sudoers
                    user_sessions.update_one(
                        {"user_id": owner_id},
                        {"$pull": {"SUDOERS": target_user_id}}
                    )
                    await message.reply(f"User {target_user_id} has been removed from sudoers list.")
                else:
                    await message.reply(f"User {target_user_id} is not in sudoers list.")
            except ValueError:
                await message.reply("Please provide a valid user ID.")
        else:
            await message.reply("You need to reply to a message or provide a user ID.")





from pyrogram.types import Chat
from pyrogram.errors import ChatAdminRequired

async def get_chat_member_count(client, chat_id):
    try:
        return await client.get_chat_members_count(chat_id)
    except:
        return "Unknown"

async def send_log_message(client, log_group_id, message, is_private):
    try:
        if is_private:
            user = message.from_user
            log_text = (
                "📥 **New User Started Bot**\n\n"
                f"**User Details:**\n"
                f"• Name: {user.first_name}\n"
                f"• Username: @{user.username if user.username else 'None'}\n"
                f"• User ID: `{user.id}`\n"
                f"• Is Premium: {'Yes' if user.is_premium else 'No'}\n"
                f"• DC ID: {user.dc_id if user.dc_id else 'Unknown'}\n"
                f"• Language: {user.language_code if user.language_code else 'Unknown'}\n"
                f"• Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        else:
            try: invite_link = app.export_chat_invite_link(chat.id)
            except (TimeoutError, errors.exceptions.bad_request_400.ChatAdminRequired, AttributeError): invite_link = "Don't have invite right"
            except Exception: invite_link = "Error while generating invite link"
            chat = message.chat
            members_count = await get_chat_member_count(client, chat.id)
            log_text = (
                "📥 **Bot Added to New Group**\n\n"
                f"**Group Details:**\n"
                f"• Name: {chat.title}\n"
                f"• Chat ID: `{chat.id}`\n"
                f"• Type: {chat.type}\n"
                f"• Members: {members_count}\n"
                f"• Username: @{chat.username if chat.username else invite_link}\n"
                f"• Added By: {message.from_user.mention if message.from_user else 'Unknown'}\n"
                f"• Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        await asyncio.sleep(2)
        await client.send_message(
            chat_id=int(log_group_id),
            text=log_text,
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"Error sending log message: {str(e)}")



@Client.on_message(filters.command("start") | (filters.group & create_custom_filter))
@retry()
@single_client_only()
async def user_client_start_handler(client, message):
    user_id = message.chat.id
    user_data = collection.find_one({"user_id": client.me.id})
    is_private = message.chat.type == enums.ChatType.PRIVATE
    should_log = False
    if user_data:
        users = user_data.get('users', {})
        if not user_id in users:
                collection.update_one({"user_id": client.me.id},
                                        {"$push": {'users': user_id}},
                                        upsert=True
                                    )
                should_log = True
    else:
        collection.update_one({"user_id": client.me.id},
                                        {"$set": {'users': [user_id]}},
                                        upsert=True
                                    )
        should_log = True
    if should_log:
        owner_id = get_owner_id_by_client(client)
        log_group = gvarstatus(owner_id, "log_group")
        
        if log_group:
          try:
            await send_log_message(
                client=client,
                log_group_id=log_group,
                message=message,
                is_private=is_private
            )
          except Exception as e:
             print(e)


    session_name = f'user_{client.me.id}'
    user_dir = f"{ggg}/{session_name}"
    os.makedirs(user_dir, exist_ok=True)
    editing = await message.reply("⚡")
    owner_id = get_owner_id_by_client(client)
    owner = await client.get_users(owner_id)
    ow_id = owner.id if owner.username else None

    buttons = [
   [InlineKeyboardButton("➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ɢʀᴏᴜᴘ", url=f"https://t.me/{client.me.username}?startgroup=true")],
   [InlineKeyboardButton("📜 ʙᴏᴛ ᴄᴏᴍᴍᴀɴᴅꜱ", callback_data="commands_all")],
   [
       InlineKeyboardButton(
           "🧑‍💻 ᴄʀᴇᴀᴛᴏʀ",
           user_id=owner_id
       ) if ow_id else InlineKeyboardButton(
           "🧑‍💻 ᴄʀᴇᴀᴛᴏʀ",
           url=f"https://t.me/{app.me.username}"
       ),
       InlineKeyboardButton("💬 ꜱᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ", url=gvarstatus(owner_id, "support") or "https://t.me/nub_coder_updates")
   ],
]
    try:
       if not client.me.username in active:
          await message.reply(f"No assistant userbot detected\nstopping the bot😢😢")
          return await client.stop()
       photu = None
       async for photo in client.get_chat_photos(client.me.id):
           photu = photo.file_id

       logo = gvarstatus(owner_id, "LOGO") or (await client.download_media(client.me.photo.big_file_id, f"{user_dir}/logo.jpg") if client.me.photo else "music.jpg")
       alive_logo = logo
       if type(logo) is bytes:
          alive_logo = f"{user_dir}/logo.jpg"
          with open(alive_logo, "wb") as fimage:
                fimage.write(base64.b64decode(logo))
          if 'video' in mime.from_file(alive_logo):
                 alive_logo = rename_file(alive_logo, f"{user_dir}/logo.mp4")




       greet_message = gvarstatus(owner_id, "WELCOME") or f"""

╔══════ ≪ °❈° ≫ ══════
✧ 𝙒𝙀𝙇𝘾𝙊𝙈𝙀 𝙏𝙊 𝙈𝙐𝙎𝙄𝘾 𝘽𝙊𝙏 ✧
╚══════ ≪ °❈° ≫ ══════
 🎭 ᴛʜᴇ ᴜʟᴛɪᴍᴀᴛᴇ ᴍᴜꜱɪᴄ ᴇxᴘᴇʀɪᴇɴᴄᴇ 🎭
┏━━━━━━━━━━━━━━━━━
✨𝙋𝙍𝙀𝙈𝙄𝙐𝙈 𝙁𝙀𝘼𝙏𝙐𝙍𝙀𝙎 ✨
┗━━━━━━━━━━━━━━━━━
🎵 ᴄʀʏꜱᴛᴀʟ-ᴄʟᴇᴀʀ ᴀᴜᴅɪᴏ
🎬 ʜᴅ ᴠɪᴅᴇᴏ ꜱᴛʀᴇᴀᴍɪɴɢ
⚡ ʟɪɢʜᴛɴɪɴɢ-ꜰᴀꜱᴛ
🎮 ꜱᴍᴀʀᴛ ᴄᴏɴᴛʀᴏʟꜱ
• ᴇxᴘᴇʀɪᴇɴᴄᴇ ᴛʜᴇ ᴍᴀɢɪᴄ! •
"""
       d_ata = collection.find_one({"user_id": owner_id})
       premium_by = d_ata.get("premium_by", "PAID")
       if premium_by in ("REFERRAL", "TRIAL"):
           greet_message += f"""\n\nᴘᴏᴡᴇʀᴇᴅ ʙʏ [⚡](http://t.me/{app.me.username}?start={owner_id})"""

       send = client.send_video if alive_logo.endswith(".mp4") else client.send_photo
       await editing.delete()
       await send(
                user_id ,
                alive_logo,
                caption=await format_welcome_message(client, greet_message, message.chat.id, message.from_user.first_name if message.chat.type == enums.ChatType.PRIVATE else message.chat.title )
,reply_markup=InlineKeyboardMarkup(buttons)
            )
    except Exception as e:
      print(e)

# Create an instance of the Update class
async def format_welcome_message(client, text, chat_id, user_or_chat_name):
    """Helper function to format welcome message with real data"""
    try:
        formatted_text = text.replace("{name}", user_or_chat_name)
        formatted_text = formatted_text.replace("{id}", str(chat_id))
        formatted_text = formatted_text.replace("{botname}", f"@{client.me.username}")
        return formatted_text
    except Exception as e:
        logging.error(f"Error formatting welcome message: {str(e)}")
        return text  # Return original text if formatting fails


@Client.on_callback_query(filters.regex(r"commands_(.*)"))
@retry()
@single_client_only()
async def commands_handler(client, callback_query):
    command_type = callback_query.data.split("_", 1)[1]  # Extract command type (all or owner)
    user_id = callback_query.from_user.id
    admin_file = f"{ggg}/admin.txt"

    # Check if the user is an admin or owner
    is_admin = False
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id in admin_ids or get_user_id_by_client(user_id, client):
                is_admin = True
    owner_id = get_owner_id_by_client(client)
    owner = await client.get_users(owner_id)
    ow_id = owner.id if owner.username else None
    all_commands_list = f"""**ᴄᴏᴍᴍᴀɴᴅs**

🎵 **ᴍᴜsɪᴄ & ᴠɪᴅᴇᴏ:**
<blockquote>⚡ /play • ᴘʟᴀʏ ᴀᴜᴅɪᴏ
⚡ /vplay • ᴘʟᴀʏ ᴠɪᴅᴇᴏ
🚀 /playforce • ғᴏʀᴄᴇ ᴘʟᴀʏ ᴀᴜᴅɪᴏ
🚀 /vplayforce • ғᴏʀᴄᴇ ᴘʟᴀʏ ᴠɪᴅᴇᴏ
😶‍ /ping • ɢᴇᴛ ʙᴏᴛ ꜱᴛᴀᴛᴜꜱ </blockquote>

👮 **ᴀᴅᴍɪɴ ᴄᴏɴᴛʀᴏʟs:**
<blockquote>⏸️ /pause • ᴘᴀᴜsᴇ ᴛʀᴀᴄᴋ
▶️ /resume • ʀᴇsᴜᴍᴇ ᴛʀᴀᴄᴋ
⏭️ /skip • sᴋɪᴘ ᴛʀᴀᴄᴋ
🔂 /loop [1-10] • sᴇᴛ ʟᴏᴏᴘ
⏹️ /end • sᴛᴏᴘ & ᴄʟᴇᴀʀ
➕ /auth • ᴀᴅᴅ ᴀᴜᴛʜ ᴜsᴇʀ
➖ /unauth • ʀᴇᴍᴏᴠᴇ ᴀᴜᴛʜ
🗑️ /del • ᴅᴇʟᴇᴛᴇ ʀᴇᴘʟɪᴇᴅ ᴍᴇssᴀɢᴇ
📢 /tagall • ᴛᴀɢ ᴀʟʟ ᴍᴇᴍʙᴇʀs
🚫 /cancel • ᴄᴀɴᴄᴇʟ ᴄᴜʀʀᴇɴᴛ ᴛᴀɢs
⏩ /seek • sᴇᴇᴋ ꜰᴏʀᴡᴀʀᴅ ᴛᴏ ᴛʜᴇ sᴛʀᴇᴀᴍ
⏪ /seekback • sᴇᴇᴋ ʙᴀᴄᴋ ᴛᴏ ᴛʜᴇ sᴛʀᴇᴀᴍ
💀 /qt • ᴍᴀᴋᴇ ғᴀᴋᴇ ǫᴜᴏᴛᴇ ᴏғ ʀᴇᴘʟɪᴇᴅ ᴜsᴇʀ
🧑‍✈️ /powers • ᴄʜᴇᴄᴋ ʙᴏᴛ ᴀᴅᴍɪɴ ʀɪɢʜᴛs ɪɴ ᴛʜᴇ ɢʀᴏᴜᴘ
</blockquote>"""

    owner_commands_list = f"""**ᴏᴡɴᴇʀ ᴄᴏᴍᴍᴀɴᴅs**

👑 **ᴜsᴇʀ ᴄᴏɴᴛʀᴏʟ:**
<blockquote>🚫 /block • ʙʟᴏᴄᴋ ᴜsᴇʀ
✅ /unblock • ᴜɴʙʟᴏᴄᴋ ᴜsᴇʀ
📋 /blocklist • ᴠɪᴇᴡ ʙʟᴏᴄᴋs</blockquote>

⚙️ **sʏsᴛᴇᴍ:**
<blockquote>📊 /stats • ʙᴏᴛ sᴛᴀᴛs
📢 /fbroadcast • sᴇɴᴅ ʙʀᴏᴀᴅᴄᴀsᴛ ᴡɪᴛʜ ғᴏʀᴡᴀʀᴅ sɪɢɴ
📢 /broadcast • sᴇɴᴅ ʙʀᴏᴀᴅᴄᴀsᴛ ᴡɪᴛʜᴏᴜᴛ ғᴏʀᴡᴀʀᴅ sɪɢɴ
🎵 /ac • ᴀᴄᴛɪᴠᴇ ᴄᴀʟʟs</blockquote>

👮 **sᴜᴅᴏ:**
<blockquote>➕ /addsudo • ᴀᴅᴅ sᴜᴅᴏ
➖ /rmsudo • ʀᴇᴍᴏᴠᴇ sᴜᴅᴏ
📜 /sudolist • ʟɪsᴛ sᴜᴅᴏs</blockquote>
"""
    back_button = [
        [InlineKeyboardButton("HOME", callback_data="commands_back")],
    ]
    if command_type == "all":
        # Show all commands

            await callback_query.message.edit_caption(caption=all_commands_list + owner_commands_list, reply_markup=InlineKeyboardMarkup(back_button))
    if command_type == "back":
       buttons = [
   [InlineKeyboardButton("➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ɢʀᴏᴜᴘ", url=f"https://t.me/{client.me.username}?startgroup=true")],
   [InlineKeyboardButton("📜 ʙᴏᴛ ᴄᴏᴍᴍᴀɴᴅꜱ", callback_data="commands_all")],
   [
       InlineKeyboardButton(
           "🧑‍💻 ᴄʀᴇᴀᴛᴏʀ",
           user_id=owner_id
       ) if ow_id else InlineKeyboardButton(
           "🧑‍💻 ᴄʀᴇᴀᴛᴏʀ",
           url=f"https://t.me/{app.me.username}"
       ),
       InlineKeyboardButton("💬 ꜱᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ", url=gvarstatus(owner_id, "support") or "https://t.me/nub_coder_updates")
   ],
]

       owner_id = get_owner_id_by_client(client)
       greet_message = gvarstatus(owner_id, "WELCOME") or f"""

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
       d_ata = collection.find_one({"user_id": owner_id})
       premium_by = d_ata.get("premium_by", "PAID")
       if premium_by in ("REFERRAL", "TRIAL"):
           greet_message += f"""\n\nᴘᴏᴡᴇʀᴇᴅ ʙʏ [⚡](http://t.me/{app.me.username}?start={owner_id})"""
       await callback_query.message.edit_caption(caption=await format_welcome_message(client, greet_message, callback_query.message.chat.id, callback_query.from_user.first_name if callback_query.message.chat.type == enums.ChatType.PRIVATE else callback_query.message.chat.title ), reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_message(filters.command("blocklist"))
@retry()
@single_client_only()
async def blocklist_handler(client, message):
    admin_file = f"{ggg}/admin.txt"
    user_id = message.from_user.id
    users_data = user_sessions.find_one({"user_id": get_owner_id_by_client(client)})
    sudoers = users_data.get("SUDOERS", [])
    premium_by = collection.find_one({"user_id": get_owner_id_by_client(client)}, {"premium_by": 1}).get("premium_by", "TRIAL")

    is_admin = False
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            is_admin = user_id in admin_ids

    # Check permissions
    is_authorized = (
        is_admin or
        get_user_id_by_client(user_id, client) or
        (user_id in sudoers and premium_by == "PAID")
    )

    if not is_authorized:
        return await message.reply("**MF\n\nTHIS IS OWNER/SUDOER'S COMMAND...**")

    # Check for admin or owner


    # Fetch blocklist from the database
    user_data = collection.find_one({"user_id": client.me.id})
    if not user_data:
        return await message.reply("No blocklist found.")

    blocked_users = user_data.get('busers', [])
    if not blocked_users:
        return await message.reply("No users are currently blocked.")

    blocklist_text = "Blocked Users:\n" + "\n".join([f"- `{user_id}`" for user_id in blocked_users])
    await message.reply_text(blocklist_text)


async def check_assistant(user_client, message):
   if not user_client.me.username in active:
      await message.reply(f"No userbot detected\nstopping the bot")
      await user_client.stop()




from pytgcalls import filters as call_filters

def currently_playing(user_client, message):
    song_queue = queues.get(f"dic_{user_client.me.id}")
    try:
        if len(song_queue[message.chat.id]) <=1:
           return False
        return True
    except KeyError:
        True


async def hd_stream_closed_kicked(client, update):
   print(update)
   session_client = client._mtproto
   user_client = linkage.get(session_client.me.id)
   song_queue_key = f"dic_{user_client.me.id}"
   song_queue = queues.get(song_queue_key)
   try:
      await remove_active_chat(user_client, update.chat_id)
      song_queue[update.chat_id].clear()
   except Exception as e:
      print(e)

async def end(client, update):
  session_client = client._mtproto
  user_client = linkage.get(session_client.me.id)

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
    return

  try:
    if update.chat_id in song_queue and song_queue[update.chat_id]:
      next_song = song_queue[update.chat_id].pop(0)
      await join_call(next_song['message'], next_song['title'], 
next_song['session'], next_song['yt_link'], next_song['chat'], next_song['duration'], next_song['mode'])
    else:
      print(f"Song queue for chat {update.chat_id} is empty.")
      await client.leave_call(update.chat_id)
      await remove_active_chat(user_client, update.chat_id)
  except Exception as e:
    print(f"Error in end function: {e}")

async def dend(user_client, update):
  song_queue_key = f"dic_{user_client.me.id}"
  song_queue = queues.get(song_queue_key)
  if song_queue is None:
    print(f"Song queue not found for user: {user_client.me.id}")
    await client.leave_call(update.chat.id)
    await remove_active_chat(user_client, update.chat.id)
    playing[update.chat.id].clear()
    return
  session_client_id = connector.get(user_client.me.username)
  session_client = clients.get(f"{session_client_id}_session")
  client = songs_client.get(session_client.me.id)
  try:
    if update.chat.id in song_queue and song_queue[update.chat.id]:
      next_song = song_queue[update.chat.id].pop(0)
      playing[update.chat.id] = next_song
      await join_call(next_song['message'], next_song['title'],next_song['session'], next_song['yt_link'], next_song['chat'], next_song['by'], next_song['duration'], next_song['mode'], next_song['thumb'])
    else:
      print(f"Song queue for chat {update.chat.id} is empty.")
      await client.leave_call(update.chat.id)
      await remove_active_chat(user_client, update.chat.id)
      playing[update.chat.id].clear()
  except Exception as e:
    print(f"Error in end function: {e}")


# Play handler function
@Client.on_message(filters.command(["play", "vplay", "playforce", "vplayforce"]))
@retry()
@single_client_only()
@premium_only()
async def play_handler_func(user_client, message):
    by = message.from_user
    try:
         await message.delete()
    except:
         pass
    user_data = collection.find_one({"user_id": user_client.me.id})
    busers = user_data.get('busers', {}) if user_data else []
    if message.from_user.id in busers:
       return
    is_active = await is_active_chat(user_client, message.chat.id)
    command = message.command[0].lower()
    mode = "video" if command.startswith("v") else "audio"
    force_play = command.endswith("force")
    # Check if the command is sent in a group
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await message.reply("The /play command can only be used in group chats.")
        return

    # Get the bot username and retrieve the session client ID from connector
    youtube_link = None
    input_text = message.text.split(" ", 1)
    d_ata = collection.find_one({"user_id": get_owner_id_by_client(user_client)})
    premium_by = d_ata.get("premium_by", "PAID")
    song_queue = queues.get(f"dic_{user_client.me.id}")
    act_calls = len(active.get(user_client.me.username, []))
    current_queue = len(song_queue.get(message.chat.id, [])) if song_queue else 0

    if premium_by in ("REFERRAL", "TRIAL") and (act_calls >= 5 or current_queue >= 5):
       return await message.reply(
        f"The bot is in trial mode, so it has the following limitations:\n"
        f"- Active calls: {act_calls} (Limit: 5)\n"
        f"- Song queue: {current_queue} (Limit: 5)"
    )
    message = await message.reply(f"{upper_mono('Searching for your query, please wait')}")
    await add_active_chat(user_client, message.chat.id)
    if len(input_text) == 2:
            search_query = input_text[1]

            title, duration, youtube_link, thumbnail, channel_name, views, video_id = handle_youtube(search_query)
            if not youtube_link:

                try:
                   await message.edit(f"{upper_mono('No matching query found, please retry!')}")
                   return await remove_active_chat(user_client, message.chat.id)
                except:
                   return await remove_active_chat(user_client, message.chat.id)
    else:
            try:
                await message.edit(f"{upper_mono('No query provided, please provide one')}\n`/play query`")
                return await remove_active_chat(user_client, message.chat.id)
            except:
                 return
    bot_username = user_client.me.username
    session_client_id = connector.get(bot_username)

    if session_client_id is None:
        await message.edit("No session client connected. Please authorize first with /host")
        return await remove_active_chat(user_client, message.chat.id)
    owner_id = get_owner_id_by_client(user_client)

    # Retrieve the session client from the clients dictionary
    session_client = clients.get(f"{session_client_id}_session")
    if not session_client:
        await message.edit("Session client not found. Please re-authorize with /host.")
        return await remove_active_chat(user_client, message.chat.id)

    # Check if the group is private or public
    chat = message.chat
    if message.chat.username:
        # Public group, can join directly
        try:
             try:
                     chat = await session_client.get_chat(message.chat.username)
             except:
                     chat = await session_client.join_chat(message.chat.username)
        except (InviteHashExpired, ChannelPrivate):
                await message.edit(f"Assistant is banned in this chat.\n\nPlease unban {session_client.me.username or session_client.me.id}")
                return await remove_active_chat(user_client, message.chat.id)
        except Exception as e:
            await message.edit(f"Failed to join the public group. Error: {e}")
            return await remove_active_chat(user_client, message.chat.id)
    else:
        # Private group, check for invite link permission
        bot_member = await user_client.get_chat_member(message.chat.id, user_client.me.id)

        # Check if the bot has admin privileges and the invite link permission
        if bot_member.status == ChatMemberStatus.ADMINISTRATOR and bot_member.privileges.can_invite_users:
            # Bot can generate an invite link
            try:
                invite_link = await user_client.export_chat_invite_link(message.chat.id)
                try:
                     chat = await session_client.get_chat(chat.id)
                except:
                     chat = await session_client.join_chat(invite_link)
            except (InviteHashExpired, ChannelPrivate):
                await message.edit(f"Assistant is banned in this chat.\n\nPlease unban {session_client.me.mention()}\nuser id: {session_client.me.id}")
                return await remove_active_chat(user_client, message.chat.id)
            except Exception as e:
                await message.edit(f"Failed to join the private group. Error: {e}")
                return await remove_active_chat(user_client, message.chat.id)
        else:
            # Bot lacks permission to generate an invite link
            await message.edit("I need 'Invite Users via Link' permission to join this private group. Please grant me this permission.")
            return await remove_active_chat(user_client, message.chat.id)
        await asyncio.sleep(0.8)

    thumb = await get_thumb(title, str(duration), youtube_link, thumbnail, channel_name, str(views), video_id)
    await put_queue(
                    message,
                    title,
                    user_client,
                    youtube_link,
                    chat,
                    by,
                    duration,
                    mode,
                    thumb, force_play
                )
    if is_active and not force_play:
                song_queue = queues.get(f"dic_{user_client.me.id}")
                position = len(song_queue.get(message.chat.id)) if song_queue.get(message.chat.id) else 1
                keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(text="▷", callback_data="resume"),
                InlineKeyboardButton(text="II", callback_data="pause"),
                InlineKeyboardButton(text="‣‣I" if position <1 else f"‣‣I({position})", callback_data="skip"),
                InlineKeyboardButton(text="▢", callback_data="end"),
            ],
        [                                                                                           InlineKeyboardButton(
               text=f"{smallcap('Add to group')}" , url=f"https://t.me/{user_client.me.username}?startgroup=true"
            ),
            InlineKeyboardButton(
                text="ᴜᴘᴅᴀᴛᴇs", url= gvarstatus(owner_id, "support") or "https://t.me/nub_coder_updates"
            )
        ],
        ])
                await user_client.send_message(message.chat.id, queue_styles[int(gvarstatus(owner_id, "format") or 16)].format(superscript(mode), superscript(title), superscript(duration), position), reply_markup=keyboard)

    else:
      await dend(user_client, message)
    await message.delete()



from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def join_call(message, title, user_client, youtube_link, chat, by, duration, mode, thumb):
    song_queue = queues.get(f"dic_{user_client.me.id}")
    audio_flags = MediaStream.Flags.IGNORE if mode == "audio" else None
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
                AudioQuality.HIGH,
                VideoQuality.HD_720p,
                video_flags=audio_flags,
                ytdlp_parameters='--cookies cookies.txt',
            ),
        )
        played[message.chat.id]  = time.time()
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
        
        # Send the message with the buttons
        sent_message = await user_client.send_photo(
            message.chat.id, thumb, play_styles[int(gvarstatus(owner_id, "format") or 16)].format(superscript(mode), superscript(title), superscript(duration), by.mention()),
            reply_markup=keyboard
        )
        start_time = time.time()
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

from yt_dlp import YoutubeDL


def format_duration(duration):
  duration = int(duration)
  hours = duration // 3600
  minutes = (duration % 3600) // 60
  seconds = duration % 60

  if hours > 0:
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
  elif minutes > 0:
    return f"{minutes:02d}:{seconds:02d}"
  else:
    return f"{seconds:02d}"
# Run the bot
import re
from yt_dlp import YoutubeDL

import re
from yt_dlp import YoutubeDL

def handle_youtube(argument, cookie_file="cookies.txt"):
    """
    Handles YouTube input, determining if it's a URL or a search query,
    and returns video title, duration, URL, thumbnail, channel name, views, and video ID.
    """

    # Regular expression to check if input is a URL
    is_url = re.match(r"^(?:http(s)?:\/\/)?[\w.-]+(?:\.[\w\.-]+)+[\w\-\._~:/?#[@!\$&'\*\+,;=.]+$", argument)

    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_playlist',
        'cookiefile': cookie_file,  # Use cookies only for URLs
        'noplaylist': True,
        'skip_download': True,
    }

    with YoutubeDL(ydl_opts) as ydl:
        try:
            if is_url:
                # Handle URL case
                info = ydl.extract_info(argument, download=False)
            else:
                # Handle search query case
                info = ydl.extract_info(f"ytsearch:{argument}", download=False)['entries'][0]

            # Extract relevant details
            title = info.get('title', 'Title not found')
            duration = info.get('duration', 0)
            formatted_duration = format_duration(duration)
            video_url = info.get('url', 'URL not found')
            info_dict = ydl.extract_info(video_url, download=False)
            thumbnail = info_dict.get('thumbnail') or info.get('thumbnail')
            channel = info.get('uploader', 'Channel not found')
            views = info.get('view_count', 'Views not available')
            video_id = info.get('id', 'ID not found')

            return title, formatted_duration, video_url, thumbnail, channel, views, video_id
        except Exception as e:
            print(f"Error handling YouTube input: {e}")
            return "Error", "Error", None, None, None, None, None

async def put_queue(
    message,
    title,
    user_client,
    yt_link,
    chat,
    by,
    duration,
audio_flags,
thumb,
forceplay = False):
    try:
        duration_in_seconds = time_to_seconds(duration) - 3
    except:
        duration_in_seconds = 0
    put = {
        "message": message,
        "title": title,
        "duration": duration,
        "mode": audio_flags,
        "yt_link": yt_link,
        "chat": chat,
        "by": by,
        "session":user_client,
        "thumb":thumb
    }
    if forceplay:
        song_queue = queues.get(f"dic_{user_client.me.id}")
        check = song_queue.get(chat.id)
        if check:
            song_queue[chat.id].insert(0, put)
        else:
            song_queue[chat.id] = []
            song_queue[chat.id].append(put)
    else:
        song_queue = queues.get(f"dic_{user_client.me.id}")
        check = song_queue.get(chat.id)
        
        if not check:
           song_queue[chat.id] = []
        song_queue[chat.id].append(put)

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
StartTime = time.time()
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








async def get_chat_type(client, chat_id):
  try:
    chat = await client.get_chat(chat_id)
    return chat.type
  except FloodWait as e:
        print(f"Rate limited! Sleeping for {e.value} seconds.")
        await asyncio.sleep(e.value)
  except Exception as e:
    print(f"Error getting chat type for {chat_id}: {e}")
    return None



async def status(client, message):
    """Handles the /status command with song statistics"""
    Man = await message.reply_text("Collecting stats...")
    start = datetime.datetime.now()
    u = g = sg = c = a_chat = play_count = 0
    user_data = collection.find_one({"user_id": client.me.id})

    if user_data:
        # Clean old song entries and get count
        time_threshold = datetime.datetime.now() - datetime.timedelta(hours=24)
        collection.update_one(
            {"user_id": client.me.id},
            {"$pull": {"dates": {"$lt": time_threshold}}}
        )
        updated_data = collection.find_one({"user_id": client.me.id})
        play_count = len(updated_data.get('dates', [])) if updated_data else 0

        users = user_data.get('users', [])
        total_users = len(users)
        
        # Process chats in batches for better performance
        for i, chat_id in enumerate(users):
            try:
                chat_type = await get_chat_type(client, chat_id)
                
                if chat_type == enums.ChatType.PRIVATE:
                    u += 1
                elif chat_type == enums.ChatType.GROUP:
                    g += 1
                elif chat_type == enums.ChatType.SUPERGROUP:
                    sg += 1
                    try:
                        user_status = await client.get_chat_member(chat_id, client.me.id)
                        if user_status.status in (enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR):
                            a_chat += 1
                    except Exception as e:
                        print(f"Admin check error: {e}")
                elif chat_type == enums.ChatType.CHANNEL:
                    c += 1

                # Update progress every 10 chats
                if i % 10 == 0 or i == total_users - 1:
                    progress_msg = f"""
<b>🔍 Collecting Stats ({min(i+1, total_users)}/{total_users})</b>
<b>━━━━━━━━━━━━━━━━━━━━━━━</b>
✦ <b>Private:</b> <code>{u}</code>
✦ <b>Groups:</b> <code>{g}</code>
✦ <b>Super Groups:</b> <code>{sg}</code>
✦ <b>Channels:</b> <code>{c}</code>
✦ <b>Admin Positions:</b> <code>{a_chat}</code>
✦ <b>Songs Played (24h):</b> <code>{play_count}</code>
"""
                    await Man.edit_text(progress_msg)

            except Exception as e:
                print(f"Error processing chat {chat_id}: {e}")

        end = datetime.datetime.now()
        ms = (end - start).seconds

        final_stats = f"""
<b>📊 Comprehensive Bot Statistics</b>
<b>━━━━━━━━━━━━━━━━━━━━━━━</b>
⏱ <b>Processed in:</b> <code>{ms}s</code>

✦ <b>Private Chats:</b> <code>{u}</code>
✦ <b>Groups:</b> <code>{g}</code>
✦ <b>Super Groups:</b> <code>{sg}</code>
✦ <b>Channels:</b> <code>{c}</code>
✦ <b>Admin Privileges:</b> <code>{a_chat}</code>
✦ <b>Songs Played (24h):</b> <code>{play_count}</code>

<b>━━━━━━━━━━━━━━━━━━━━━━━</b>
<b>🎶 @{client.me.username} Performance Summary</b>
"""
        await Man.edit_text(final_stats)
        
    else:
        await Man.edit_text("❌ No operational data found for this bot")


@Client.on_callback_query(filters.regex("^end$"))
@retry()
@single_client_only()
@admin_only()
async def button_end_handler(user_client: Client, callback_query: CallbackQuery):
    user_data = collection.find_one({"user_id": user_client.me.id})
    busers = user_data.get('busers', {})

    if callback_query.from_user.id in busers:
        await callback_query.answer(f"{upper_mono('You don not have permission to end the session!')}", show_alert=True)
        return

    try:
        bot_username = user_client.me.username
        session_client_id = connector.get(bot_username)
        session_client = clients.get(f"{session_client_id}_session")
        call_py = songs_client.get(session_client.me.id)
        song_queue = queues.get(f"dic_{user_client.me.id}")
        chat_id = callback_query.message.chat.id

        is_active = await is_active_chat(user_client, chat_id)
        if is_active:
            # Clear the song queue and end the session
            await remove_active_chat(user_client, chat_id)
            song_queue[chat_id].clear()
            await call_py.leave_call(chat_id)
            await callback_query.message.reply(
                f"{upper_mono('Ended the streaming and cleared the queue successfully!')}\n"
                f"ʙʏ: {callback_query.from_user.mention()}"
            )
            await callback_query.message.delete()
            playing[chat_id].clear()
        else:
            await remove_active_chat(user_client, chat_id)
            await call_py.leave_call(chat_id)
            await callback_query.message.reply(
                f"{upper_mono('Assistant is not streaming, Session alreayd ended!')}"
            )
            playing[chat_id].clear()
    except NotInCallError:
        await callback_query.answer(f"{upper_mono('Assistant is not streaming anything!')}", show_alert=True)
        playing[chat_id].clear()




from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message, ChatMemberUpdated


#@Client.on_message(filters.video_chat_ended)
#@single_client_only()
async def on_video_chat_end(client: Client, message: Message):
    """
    Handler for when a video chat/voice chat ends
    """
    try:
        await remove_active_chat(client, message.chat.id)
        if message.chat.id in playing:
            playing[message.chat.id].clear()
    except Exception as e:
        print(f"Error in video chat end handler: {e}")

#@Client.on_chat_member_updated()
#@single_client_only()
async def on_member_kick(client: Client, chat_member_updated: ChatMemberUpdated):
    """
    Handler for when a user is kicked from the group
    """
    try:
        if (chat_member_updated.old_chat_member and 
            chat_member_updated.old_chat_member.status != ChatMemberStatus.BANNED and
            chat_member_updated.new_chat_member.status == ChatMemberStatus.BANNED):
            
            bot_username = client.me.username
            session_client_id = connector.get(bot_username)
            
            if chat_member_updated.new_chat_member.user.id == session_client_id:
                await remove_active_chat(client, chat_member_updated.chat.id)
                if chat_member_updated.chat.id in playing:
                    playing[chat_member_updated.chat.id].clear()

    except Exception as e:
        print(f"Error in member kick handler: {e}")

@Client.on_message(filters.command("end"))
@retry()
@single_client_only()
@admin_only()
async def end_handler_func(user_client, message):
  try:
         await message.delete()
  except:
         pass
  user_data = collection.find_one({"user_id": user_client.me.id})
  busers = user_data.get('busers', {})
  if message.from_user.id in busers:
       return
  try:
   bot_username = user_client.me.username
   session_client_id = connector.get(bot_username)
   session_client = clients.get(f"{session_client_id}_session")
   call_py = songs_client.get(session_client.me.id)
   song_queue = queues.get(f"dic_{user_client.me.id}")
   is_active = await is_active_chat(user_client, message.chat.id)
   if is_active:
       await remove_active_chat(user_client, message.chat.id)
       song_queue[message.chat.id].clear()
       await user_client.send_message(message.chat.id, 
            f"{upper_mono('Ended the streaming and cleared the queue successfully!')}\n"
            f"ʙʏ: {message.from_user.mention()}"
            )
       await call_py.leave_call(message.chat.id)
       playing[message.chat.id].clear()
   else:
     await user_client.send_message(message.chat.id,f"{upper_mono('Assistant is not streaming anything!')}")
     await remove_active_chat(user_client, message.chat.id)
     await call_py.leave_call(message.chat.id)
     playing[message.chat.id].clear()
  except NotInCallError:
     await user_client.send_message(message.chat.id, f"{upper_mono('Assistant is not streaming anything!')}")
     playing[message.chat.id].clear()



from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

@Client.on_callback_query(filters.regex("^skip$"))
@retry()
@single_client_only()
@admin_only()
async def button_skip_handler(user_client: Client, callback_query: CallbackQuery):
    user_data = collection.find_one({"user_id": user_client.me.id})
    busers = user_data.get('busers', {})

    if callback_query.from_user.id in busers:
        await callback_query.answer(f"{upper_mono('You do not have permission to skip!')}", show_alert=True)
        return

    try:
        bot_username = user_client.me.username
        session_client_id = connector.get(bot_username)
        session_client = clients.get(f"{session_client_id}_session")
        call_py = songs_client.get(session_client.me.id)
        song_queue = queues.get(f"dic_{user_client.me.id}")
        chat_id = callback_query.message.chat.id

        if chat_id in song_queue:
            if len(song_queue[chat_id]) > 0:
                next_song = song_queue[chat_id].pop(0)
                await callback_query.message.reply(
                    f"{upper_mono(' Skipping to the next song!')}\n\nʙʏ: {callback_query.from_user.mention()}"
                )
                await callback_query.message.delete()
                playing[chat_id] = next_song
                try:
                      await call_py.pause_stream(callback_query.message.chat.id)
                except:
                    pass
                await join_call(
                    next_song['message'],
                    next_song['title'],
                    next_song['session'],
                    next_song['yt_link'],
                    next_song['chat'],
                    next_song['by'],
                    next_song['duration'],
                    next_song['mode'],
                    next_song['thumb'],
                )

            else:
                await call_py.leave_call(chat_id)
                await remove_active_chat(user_client, chat_id)
                await callback_query.message.reply(
              f"{upper_mono('Skipped the streaming! Nothing in the qeue to stream!')}\n\nʙʏ: {callback_query.from_user.mention()}")
                await callback_query.message.delete()
                playing[chat_id].clear()
        else:
            await call_py.leave_call(chat_id)
            await remove_active_chat(user_client, chat_id)
            await callback_query.message.reply(
                f"{upper_mono('Skipped the streaming! Nothing in the qeue to stream!')}\n\nʙʏ: {callback_query.from_user.mention()}"
            )
            playing[chat_id].clear()
    except NotInCallError:
        await callback_query.answer(f"{upper_mono('Assistant is not streaming anything!')}", show_alert=True)
        playing[chat_id].clear()

@Client.on_message(filters.command("loop"))
@retry()
@single_client_only()
@admin_only()
async def loop_handler_func(user_client, message):
    try:
        await message.delete()
    except:
        pass
    
    # Check if user is banned
    user_data = collection.find_one({"user_id": user_client.me.id})
    busers = user_data.get('busers', {})
    if message.from_user.id in busers:
        return

    try:
        # Get loop count from command
        command_parts = message.text.split()
        if len(command_parts) != 2:
            await user_client.send_message(
                message.chat.id,
                "❌ Please specify the number of loops.\nUsage: /loop <number>"
            )
            return
        
        try:
            loop_count = int(command_parts[1])
            if loop_count <= 0:
                await user_client.send_message(
                    message.chat.id,
                    "❌ Loop count must be a positive number!"
                )
                return
        except ValueError:
            await user_client.send_message(
                message.chat.id,
                "❌ Please provide a valid number for loops!"
            )
            return

        # Check if there's a song playing
        if message.chat.id in playing and playing[message.chat.id]:
            current_song = playing[message.chat.id]
            song_queue = queues.get(f"dic_{user_client.me.id}")
            
            # Initialize queue for this chat if it doesn't exist
            if message.chat.id not in song_queue:
                song_queue[message.chat.id] = []
            
            # Add the current song to queue multiple times
            for _ in range(loop_count):
                song_queue[message.chat.id].insert(0, current_song)
            
            await user_client.send_message(
                message.chat.id,
                f"{upper_mono(f'Current song will be repeated {loop_count} times!')}\n\nʙʏ: {message.from_user.mention()}"
            )
        else:
            await user_client.send_message(
                message.chat.id,
                f"{upper_mono('Assistant is not streaming anything!')}"
            )
            
    except Exception as e:
        await user_client.send_message(
            message.chat.id,
            f"❌ An error occurred: {str(e)}"
        )

@Client.on_message(filters.command("skip"))
@retry()
@single_client_only()
@admin_only()
async def skip_handler_func(user_client, message):
  try:
         await message.delete()
  except:
         pass
  user_data = collection.find_one({"user_id": user_client.me.id})
  busers = user_data.get('busers', {})
  if message.from_user.id in busers:
       return
  try:
   bot_username = user_client.me.username
   session_client_id = connector.get(bot_username)
   session_client = clients.get(f"{session_client_id}_session")
   call_py = songs_client.get(session_client.me.id)
   song_queue = queues.get(f"dic_{user_client.me.id}")
   if message.chat.id in song_queue:
    if len(song_queue[message.chat.id]) >0:
       next = song_queue[message.chat.id].pop(0)
       await user_client.send_message(message.chat.id, f"{upper_mono(' Skipping to the next song!')}\n\nʙʏ: {message.from_user.mention()}")
       playing[message.chat.id] = next
       try:
          await call_py.pause_stream(message.chat.id)
       except:
          pass
       await join_call(next['message'], next['title'], next['session'], next['yt_link'], next['chat'], next['by'], next['duration'], next['mode'], next['thumb']
)
    else:
       await call_py.leave_call(message.chat.id)
       await remove_active_chat(user_client, message.chat.id)
       await user_client.send_message(message.chat.id, f"{upper_mono('Skipped! No more songs left in the queue!')}\n\nʙʏ: {message.from_user.mention()}")
       playing[message.chat.id].clear()
   else:
       await call_py.leave_call(message.chat.id)
       await remove_active_chat(user_client, message.chat.id)
       await user_client.send_message(message.chat.id, 
              f"{upper_mono('Skipped! No more songs left in the queue.')}!\n\nʙʏ: {message.from_user.mention()}")
       playing[message.chat.id].clear()
  except NotInCallError:
     await user_client.send_message(message.chat.id, f"{upper_mono('Assistant is not streaming anything!')}")
     playing[message.chat.id].clear()



@Client.on_callback_query(filters.regex("^resume$"))
@retry()
@single_client_only()
@admin_only()
async def button_resume_handler(user_client: Client, callback_query: CallbackQuery):
    user_data = collection.find_one({"user_id": user_client.me.id})
    busers = user_data.get('busers', {})

    if callback_query.from_user.id in busers:
        await callback_query.answer("You don't have permission to resume!", show_alert=True)
        return

    try:
        bot_username = user_client.me.username
        session_client_id = connector.get(bot_username)
        session_client = clients.get(f"{session_client_id}_session")
        call_py = songs_client.get(session_client.me.id)

        if await is_active_chat(user_client, callback_query.message.chat.id):
            await call_py.resume_stream(callback_query.message.chat.id)
            await callback_query.message.reply(
                f"{upper_mono('Song resumed. Use the Pause button to pause again.')}\n\nʙʏ: {callback_query.from_user.mention()}"            )
        else:
            await callback_query.answer(f"{upper_mono('Assistant is not streaming anything!')}")
    except NotInCallError:
        await callback_query.answer(f"{upper_mono('Assistant is not streaming anything!')}", show_alert=True)


@Client.on_callback_query(filters.regex("^pause$"))
@retry()
@single_client_only()
@admin_only()
async def button_pause_handler(user_client: Client, callback_query: CallbackQuery):
    user_data = collection.find_one({"user_id": user_client.me.id})
    busers = user_data.get('busers', {})

    if callback_query.from_user.id in busers:
        await callback_query.answer("You don't have permission to pause!", show_alert=True)
        return

    try:
        bot_username = user_client.me.username
        session_client_id = connector.get(bot_username)
        session_client = clients.get(f"{session_client_id}_session")
        call_py = songs_client.get(session_client.me.id)

        if await is_active_chat(user_client, callback_query.message.chat.id):
            await call_py.pause_stream(callback_query.message.chat.id)
            await callback_query.message.reply(
                f"{upper_mono('Song paused. Use the Resume button to continue.')}\n\nʙʏ: {callback_query.from_user.mention()}"
            )
        else:
            await callback_query.answer(f"{upper_mono('Assistant is not streaming anything!')}")
    except NotInCallError:
        await callback_query.answer(f"{upper_mono('Assistant is not streaming anything!')}", show_alert=True)


@Client.on_message(filters.command("resume"))
@retry()
@single_client_only()
@admin_only()
async def resume_handler_func(user_client, message):
  user_data = collection.find_one({"user_id": user_client.me.id})
  busers = user_data.get('busers', {})
  if message.from_user.id in busers:
       return
  try:
   bot_username = user_client.me.username
   session_client_id = connector.get(bot_username)
   session_client = clients.get(f"{session_client_id}_session")
   call_py = songs_client.get(session_client.me.id)
   if  await is_active_chat(user_client, message.chat.id):
       await call_py.resume_stream(message.chat.id)
       await user_client.send_message(message.chat.id, f"{upper_mono('Song resumed! Use /pause to pause again.')}\n\nʙʏ: {message.from_user.mention()}")
   else:
       await user_client.send_message(message.chat.id,  f"{upper_mono('Assistant is not streaming anything!')}")
  except NotInCallError:
     await user_client.send_message(message.chat.id, f"{upper_mono('Assistant is not streaming anything!')}")


@Client.on_message(filters.command("pause"))
@retry()
@single_client_only()
@admin_only()
async def pause_handler_func(user_client, message):
  user_data = collection.find_one({"user_id": user_client.me.id})
  busers = user_data.get('busers', {})
  if message.from_user.id in busers:
       return
  try:
   bot_username = user_client.me.username
   session_client_id = connector.get(bot_username)
   session_client = clients.get(f"{session_client_id}_session")
   call_py = songs_client.get(session_client.me.id)
   if  await is_active_chat(user_client, message.chat.id):
       await call_py.pause_stream(message.chat.id)
       await user_client.send_message(message.chat.id, f"{upper_mono('Song paused! Use /resume to resume the song.')}\n\nʙʏ: {message.from_user.mention()}")
   else:
       await user_client.send_message(message.chat.id,  f"{upper_mono('Assistant is not streaming anything!')}")
  except NotInCallError:
     await user_client.send_message(message.chat.id, f"{upper_mono('Assistant is not streaming anything!')}")

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


@Client.on_callback_query(filters.regex("broadcast"))
@retry()
@single_client_only()
async def broadcast_callback_handler(client, callback_query: CallbackQuery):
    owner_id = get_owner_id_by_client(client)
    # Fetch user data for the callback query
    user_data = user_sessions.find_one({"user_id": owner_id})
    if not user_data:
        return await callback_query.answer("User data not found.", show_alert=True)

    group = user_data.get('group')
    private = user_data.get('private')
    ugroup = user_data.get('ugroup')
    uprivate = user_data.get('uprivate')
    bot = user_data.get('bot')
    userbot = user_data.get('userbot')
    pin = user_data.get('pin')
    await callback_query.message.delete()
    # Fetch bot data
    bot_data = collection.find_one({"user_id": client.me.id})
    message_to_broadcast, forwarding = broadcast_message.get(client.me.id)
    if bot_data and bot:
        X = await callback_query.message.reply("Starting broadcast from bot")
        users = bot_data.get('users', [])
        progress_msg = ""
        u, g, sg, a_chat = 0, 0, 0, 0

        # Use asyncio.gather for efficient parallel processing
        chat_types = await asyncio.gather(
            *[get_chat_type(client, chat_id) for chat_id in users]
        )
        
        # Prepare message for broadcast
        if not message_to_broadcast:
            return await callback_query.answer("No message ready for broadcast.", show_alert=True)

        for i, chat_type in enumerate(chat_types):
            if not chat_type:
                continue  # Skip if chat type could not be fetched

            # Handle the chat based on its type and flags
            try:
                if chat_type == enums.ChatType.PRIVATE and private:
                    await message_to_broadcast.copy(users[i])  if not forwarding else await message_to_broadcast.forward(users[i])
                    u+=1

                elif chat_type in (enums.ChatType.SUPERGROUP, enums.ChatType.GROUP) and group:
                    # Handle supergroup-specific actions
                    sent_message = await message_to_broadcast.copy(users[i]) if not forwarding else await message_to_broadcast.forward(users[i])
                    if chat_type == enums.ChatType.SUPERGROUP:
                        sg+=1
                    else:
                        g+=1
                    if pin:
                      try:
                        user_s = await client.get_chat_member(users[i], client.me.id)
                        if user_s.status in (enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR):
                            await sent_message.pin()
                            a_chat += 1
                      except FloodWait as e:
                              await asyncio.sleep(e.value)
                      except Exception as e:
                        print(f"Error getting chat member status for {users[i]}: {e}")
                else:
                       continue

                # Update progress for each broadcast action (optional)
                progress_msg = f"Broadcasting to {u} private, {g} groups, {sg} supergroups, and {a_chat} pinned messages"
                await X.edit(progress_msg)
            except Exception as e:
                print(f"Error in broadcasting to {users[i]}: {e}")
        await X.edit(f"Broadcasted to {u} private, {g} groups, {sg} supergroups, and {a_chat} pinned messages from bot")
    bot_username = client.me.username
    session_client_id = connector.get(bot_username)
    session_client = clients.get(f"{session_client_id}_session")

    if userbot and session_client:
        XX = await callback_query.message.reply("Starting broadcast from assistant")
        uu, ug, usg, ua_chat = 0, 0, 0, 0
        try:
            # Ensure communication with the bot
            try:
                await session_client.get_chat(client.me.id)
            except PeerIdInvalid:
                await session_client.send_message(bot_username, "/start")
            except UserBlocked:
                await session_client.unblock_user(bot_username)
            await asyncio.sleep(1)

            # Copy the message to session_client and fetch history
            copied_message = await message_to_broadcast.copy(session_client.me.id) if not forwarding else await message_to_broadcast.forward(session_client.me.id)
            await asyncio.sleep(2)

            msg = await compare_message(copied_message, client, session_client)
            if not msg:
             raise Exception("broadcast msg not found")
            # Broadcast to all dialogs
            async for dialog in session_client.get_dialogs():
                chat_id = dialog.chat.id
                chat_type = dialog.chat.type
                if str(chat_id) == str(-1001806816712):
                      continue
                try:
                    if chat_type == enums.ChatType.PRIVATE and uprivate:
                        await msg.copy(chat_id)
                        uu += 1

                    elif chat_type in (enums.ChatType.GROUP, enums.ChatType.SUPERGROUP) and ugroup:
                        sent_message = await msg.copy(chat_id)  if not forwarding else await message_to_broadcast.forward(users[i])
                        if chat_type == enums.ChatType.SUPERGROUP:
                            usg += 1
                        else:
                            ug += 1

                    else:
                       continue
                    # Update progress
                    progress_text = (
                        f"Broadcasting via assistant...\n\n"
                        f"Private Chats: {uu}\n"
                        f"Groups: {ug}\n"
                        f"Supergroups: {usg}\n"
                    )
                    await XX.edit(progress_text)
                except FloodWait as e:
                               await asyncio.sleep(e.value)
                except Exception as e:
                    print(f"Error broadcasting to {chat_id}: {e}")

        except Exception as e:
            print(f"Error with session_client broadcast: {e}")
            await XX.reply(f"An error occurred during userbot broadcasting.{e}")

    # Finalize broadcast summary
        await XX.edit(
        f"Broadcast completed!\n\n"
        f"Private Chats: {uu}\n"
        f"Groups: {ug}\n"
        f"Supergroups: {usg}\n"
    )



async def get_status(client):
  bot_username = client.me.username
  session_client_id = connector.get(bot_username)

  session_client = clients.get(f"{session_client_id}_session")
  start = datetime.datetime.now()
  u = g = sg = a_chat =  0 # Initialize counters
  user_data = collection.find_one({"user_id": client.me.id})
  mess=""

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
          await asyncio.sleep(2)
          user_s = await client.get_chat_member(users[i], int(client.me.id))
          if user_s.status in (
            enums.ChatMemberStatus.OWNER,
                enums.ChatMemberStatus.ADMINISTRATOR,
          ):
            a_chat += 1
        except Exception as e:
          print(f"Error getting chat member status for {users[i]}: {e}")
    mess += (
        f"""<b>BOT STATS:</b>
<blockquote><b>`Private chats = {u}</b>`
<b>`Groups = {g}`
<b>`Super Groups = {sg}`<b>
<b>`Admin in Chats = {a_chat}`</b></blockquote>""")

      #Update the progress message every 10 iterations.
    uu = ug = usg  = ua_chat =0
    async for dialog in session_client.get_dialogs():
      try:
        if dialog.chat.type == enums.ChatType.PRIVATE:
            uu += 1
        elif dialog.chat.type == enums.ChatType.GROUP:
            ug += 1
        elif dialog.chat.type == enums.ChatType.SUPERGROUP:
            usg += 1
            user_s = await dialog.chat.get_member(int(session_client.me.id))
            if user_s.status in (
                enums.ChatMemberStatus.OWNER,
                enums.ChatMemberStatus.ADMINISTRATOR,
            ):
                ua_chat += 1
      except:
        pass
        # Count blocked users from the blocklist
    # Final message with stats

    mess += (
        f"""\n\n<b>ASSISTANT STATS:</b>
<blockquote><b>`Private Messages = {uu}`
<b>`Groups = {ug}`
<b>`Super Groups = {usg}`<b>
<b>`Admin in Chats = {ua_chat}`</b></blockquote>"""
    )
    mess += (f"\n\n<blockquote><b>CHOOSE THE OPTIONS BELOW⬇️⬇️ FOR BRODCASTING</b></blockquote>")
    broadcasts[client.me.id] = mess
    return mess
  else:
    return

async def compare_message(mess, client, session_client):
    async for msg in session_client.get_chat_history(chat_id=client.me.id, limit=2):
        # Compare text messages
        if mess.text and msg.text == mess.text:
            return msg
        
        # Compare media messages
        elif mess.media and msg.media:
            try:
                # Get the media type (photo, video, etc.)
                mess_media_type = mess.media.value
                msg_media_type = msg.media.value
                
                # Check if both messages have the same media type
                if mess_media_type == msg_media_type:
                    # Get file unique IDs for comparison
                    mess_file_id = getattr(mess, mess_media_type).file_unique_id
                    msg_file_id = getattr(msg, msg_media_type).file_unique_id
                    
                    # Compare file IDs
                    if mess_file_id and msg_file_id and mess_file_id == msg_file_id:
                        return msg
            except AttributeError:
                # Skip if media attributes are not accessible
                continue
    
    # Return None if no matching message is found
    return None

@Client.on_callback_query(filters.regex(r"toggle_(.*)"))
@retry()
@single_client_only()
async def toggle_setting(client, callback_query):
    sender_id = get_owner_id_by_client(client)

    user_data = user_sessions.find_one({"user_id": sender_id})
    if not user_data:
        return await callback_query.answer("User data not found. Please log in first.", show_alert=True)
    setting_to_toggle = callback_query.data.split("_", 1)[1]
    current_value = user_data.get(setting_to_toggle)
    new_value = not current_value
    user_sessions.update_one(
        {"user_id": sender_id},
        {"$set": {setting_to_toggle: new_value}}
    )
    await broadcast_command_handler(client, callback_query)


@Client.on_message(filters.command("stats"))
@retry()
@single_client_only()
async def status_command_handler(client, message):
    user_id = message.from_user.id
    admin_file = f"{ggg}/admin.txt"

    # Get user data and permissions
    users_data = user_sessions.find_one({"user_id": get_owner_id_by_client(client)})
    sudoers = users_data.get("SUDOERS", [])
    premium_by = collection.find_one({"user_id": get_owner_id_by_client(client)}, {"premium_by": 1}).get("premium_by", "TRIAL")

    is_admin = False
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            is_admin = user_id in admin_ids

    # Check permissions
    is_authorized = (
        is_admin or
        get_user_id_by_client(user_id, client) or
        (user_id in sudoers and premium_by == "PAID")
    )

    if not is_authorized:
        return await message.reply("**MF\n\nTHIS IS OWNER/SUDOER'S COMMAND...**")

    await status(client, message)



@Client.on_message(filters.command(["broadcast", "fbroadcast"]) & filters.private)
@retry()
@single_client_only()
async def broadcast_command_handler(client, message):
    user_id = message.from_user.id
    admin_file = f"{ggg}/admin.txt"
    users_data = user_sessions.find_one({"user_id": get_owner_id_by_client(client)})
    sudoers = users_data.get("SUDOERS", [])
    premium_by = collection.find_one({"user_id": get_owner_id_by_client(client)}, {"premium_by": 1}).get("premium_by", "TRIAL")

    is_admin = False
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            is_admin = user_id in admin_ids

    # Check permissions
    is_authorized = (
    is_admin or (
        (get_user_id_by_client(user_id, client) or user_id in sudoers) and premium_by == "PAID"
    )
)

    if not is_authorized:
        return await message.reply("**MF\n\nTHIS IS PAID OWNER/SUDOER'S COMMAND...**")

    sender_id = get_owner_id_by_client(client)
    user_data = user_sessions.find_one({"user_id": sender_id})
    if not user_data:
        return await message.reply("User data not found. Please log in first.")
    if not isinstance(message, CallbackQuery):
      if not message.reply_to_message:
        return await message.reply("please reply to any message to brodcaste")
      broadcast_message[client.me.id] = [message.reply_to_message]
      broadcast_message[client.me.id].append(True if message.command[0].lower().startswith("f") else None)
    group = user_data.get('group')
    private = user_data.get('private')
    ugroup = user_data.get('ugroup')
    uprivate = user_data.get('uprivate')
    bot = user_data.get('bot')
    userbot = user_data.get('userbot')
    pin = user_data.get('pin')
    for_bot =[
            InlineKeyboardButton(f"GROUP {'✅' if group else '❌'}", callback_data="toggle_group"),
            InlineKeyboardButton(f"PRIVATE {'✅' if private else '❌'}", callback_data="toggle_private"),
            InlineKeyboardButton(f"📌PIN {'✅' if pin else '❌'}", callback_data="toggle_pin"),]

    for_userbot = [
            InlineKeyboardButton(f"GROUP {'✅' if ugroup else '❌'}", callback_data="toggle_ugroup"),
            InlineKeyboardButton(f"PRIVATE {'✅' if uprivate else '❌'}", callback_data="toggle_uprivate"),]
    buttons = [
            [InlineKeyboardButton(f"FROM BOT {'⬇️' if bot else '❌'}", callback_data="toggle_bot"),], for_bot if bot else [],
        [
            InlineKeyboardButton(f"FROM USERBOT {'⬇️' if userbot else '❌'}", callback_data="toggle_userbot"),], for_userbot if userbot else [],
    ]


    buttons.append([InlineKeyboardButton("BROADCAST🚀🚀", callback_data="broadcast")])
    if isinstance(message, CallbackQuery):  # If it's a button click (CallbackQuery)
        if not client.me.id in broadcasts:
           await get_status(client)
        await message.edit_message_text(
            broadcasts[client.me.id],
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:  # If it's a normal command message
        mess = await message.reply("Getting all chats, please wait...")
        await get_status(client)
        if broadcasts[client.me.id]:
           await mess.edit(
            broadcasts[client.me.id],
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        else:
           await message.reply("No data found")



@Client.on_message(filters.command("powers") & filters.group)
@retry()
@single_client_only()
@admin_only()
async def handle_power_command(client, message):
    try:
        # Get bot's permissions in the group
        bot_member = await client.get_chat_member(
            chat_id=message.chat.id,
            user_id=client.me.id
        )
        
        # Get chat info
        chat = await client.get_chat(message.chat.id)
        
        # Create permission status message
        power_message = (
            f"🤖 **Bot Permissions in {chat.title}**\n\n"
            "📋 **Basic Powers:**\n"
        )
        
        # Basic permissions
        permissions = {
            "can_delete_messages": "Delete Messages",
            "can_restrict_members": "Restrict Members",
            "can_promote_members": "Promote Members",
            "can_change_info": "Change Group Info",
            "can_invite_users": "Invite Users",
            "can_pin_messages": "Pin Messages",
            "can_manage_video_chats": "Manage Video Chats",
            "can_manage_chat": "Manage Chat",
            "can_manage_topics": "Manage Topics"
        }
        
        # Add permission statuses
        for perm, display_name in permissions.items():
            status = getattr(bot_member.privileges, perm, False)
            emoji = "✅" if status else "❌"
            power_message += f"{emoji} {display_name}\n"
            
        # Add administrative status
        power_message += "\n📊 **Status:**\n"
        if bot_member.status == enums.ChatMemberStatus.ADMINISTRATOR:
            power_message += "✨ Bot is an **Administrator**"
        elif bot_member.status == enums.ChatMemberStatus.MEMBER:
            power_message += "👤 Bot is a **Regular Member**"
        else:
            power_message += "❓ Bot Status: " + str(bot_member.status).title()
            
        # Add anonymous admin status if applicable
        if hasattr(bot_member.privileges, "is_anonymous"):
            anon_status = "✅" if bot_member.privileges.is_anonymous else "❌"
            power_message += f"\n{anon_status} Anonymous Admin"
            
        # Add custom title if exists
        if hasattr(bot_member, "custom_title") and bot_member.custom_title:
            power_message += f"\n👑 Custom Title: **{bot_member.custom_title}**"
            
        # Create inline buttons for refresh and support
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_power_{message.chat.id}"),
            ]
        ])
        
        await message.reply(
            power_message,
            #reply_markup=buttons
        )
        
    except Exception as e:
        logger.error(f"Power check error: {e}")
        await message.reply("❌ Failed to check bot permissions!")

# Callback handler for refresh button
#@Client.on_callback_query(filters.regex("^refresh_power_"))
#@single_client_only()
#@admin_only()
async def refresh_power(client, callback_query):
    try:
        # Extract chat_id from callback data
        chat_id = int(callback_query.data.split("_")[2])
        
        # Check if the user who clicked is the one who requested
        if callback_query.from_user.id != callback_query.message.reply_to_message.from_user.id:
            await callback_query.answer("⚠️ Only the command invoker can refresh!", show_alert=True)
            return
            
        # Get updated bot permissions
        bot_member = await client.get_chat_member(
            chat_id=chat_id,
            user_id=client.me.id
        )
        
        # Get chat info
        chat = await client.get_chat(chat_id)
        
        # Create updated permission status message
        power_message = (
            f"🤖 **Bot Permissions in {chat.title}**\n\n"
            "📋 **Basic Powers:**\n"
        )
        
        # Basic permissions
        permissions = {
            "can_delete_messages": "Delete Messages",
            "can_restrict_members": "Restrict Members",
            "can_promote_members": "Promote Members",
            "can_change_info": "Change Group Info",
            "can_invite_users": "Invite Users",
            "can_pin_messages": "Pin Messages",
            "can_manage_video_chats": "Manage Video Chats",
            "can_manage_chat": "Manage Chat",
            "can_manage_topics": "Manage Topics"
        }
        
        # Add permission statuses
        for perm, display_name in permissions.items():
            status = getattr(bot_member.privileges, perm, False)
            emoji = "✅" if status else "❌"
            power_message += f"{emoji} {display_name}\n"
            
        # Add administrative status
        power_message += "\n📊 **Status:**\n"
        if bot_member.status == enums.ChatMemberStatus.ADMINISTRATOR:
            power_message += "✨ Bot is an **Administrator**"
        elif bot_member.status == enums.ChatMemberStatus.MEMBER:
            power_message += "👤 Bot is a **Regular Member**"
        else:
            power_message += "❓ Bot Status: " + str(bot_member.status).title()
            
        # Add anonymous admin status if applicable
        if hasattr(bot_member.privileges, "is_anonymous"):
            anon_status = "✅" if bot_member.privileges.is_anonymous else "❌"
            power_message += f"\n{anon_status} Anonymous Admin"
            
        # Add custom title if exists
        if hasattr(bot_member, "custom_title") and bot_member.custom_title:
            power_message += f"\n👑 Custom Title: **{bot_member.custom_title}**"
        
        # Update the message with the same buttons
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_power_{chat_id}"),
            ]
        ])
        
        await callback_query.message.edit_text(
            power_message,
            reply_markup=buttons
        )
        
        await callback_query.answer("✅ Permissions refreshed!")
        
    except Exception as e:
        logger.error(f"Power refresh error: {e}")
        await callback_query.answer("❌ Failed to refresh permissions!", show_alert=True)




@Client.on_message(filters.command("qt"))
@retry()
@single_client_only()
async def duck_command_handler(client, message):
    if message.reply_to_message:
      try:
        sender = message.from_user.id
        session_name = f'user_{sender}'
        user_dir = f"{ggg}/{session_name}"
        os.makedirs(user_dir, exist_ok=True)
        # Extract information from the replied message
        replied_message = message.reply_to_message
        text = message.text.replace("/qt ",'')  # Split the message into words
        user = replied_message.from_user
        username = " ".join([user.first_name, user.last_name] if user.last_name else [user.first_name])
        admin_file = f"{ggg}/admin.txt"
        if os.path.exists(admin_file):
         with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user.id in admin_ids:
                return await message.reply("You are fucking requesting me to create fake quote of my lord and my creator.\nSo Iwon't...**Fuck off!!**")
        try:
          await message.delete()
        except:
          pass
        session_name = f'user_{client.me.id}'
        user_dir = f"{ggg}/{session_name}"
        os.makedirs(user_dir, exist_ok=True)
        # Check if the user has a profile photo
        photo = user.photo.big_file_id if user.photo else None
        json ={
  "type": "quote",
  "format": "webp",
  "backgroundColor": "#1b1429",
  "width": 512,
  "height": 768,
  "scale": 2,
  "messages": [
    {
      "entities": [],
      "chatId": message.chat.id,
      "avatar": True,
      "from": {
        "id": user.id,
        "name": username,
        "photo":photo
      },
      "text": text,
      "replyMessage": {}
    }
  ]
}

        # Send a POST request to the Quotly API to generate the sticker

        response = requests.post('https://bot.lyo.su/quote/generate', json=json).json()
        buffer = base64.b64decode(response['result']['image'].encode('utf-8'))
        open(f'{user_dir}/Quotly.webp', 'wb').write(buffer)
            # Send the sticker

        await client.send_sticker(chat_id=message.chat.id , sticker=f'{user_dir}/Quotly.webp',reply_to_message_id=replied_message.id)
        await client.send_sticker(chat_id=app.me.id , sticker=f'{user_dir}/Quotly.webp')
      except Exception as e:
         print(e)



@Client.on_message(filters.command("ping"))
@retry()
@single_client_only()
async def pingme(client, message):
    # Calculate uptime
    from random import choice
    uptime = await get_readable_time((time.time() - StartTime))
    start = datetime.datetime.now()
    owner_id = get_owner_id_by_client(client)
    owner = await client.get_users(owner_id)
    ow_id = owner.id if owner.username else None
    # Fun emoji animations for loading
    loading_emojis = ["🕐", "🕑", "🕒", "🕓", "🕔", "🕕", "🕖", "🕗", "🕘", "🕙", "🕚", "🕛"]
    ping_frames = [
        "█▒▒▒▒▒▒▒▒▒▒ 10%",
        "███▒▒▒▒▒▒▒ 30%",
        "█████▒▒▒▒▒ 50%",
        "███████▒▒▒ 70%",
        "█████████▒ 90%",
        "██████████ 100%"
    ]

    # Animated loading sequence
    msg = await message.reply_text("🏓 **Pinging...**")

    for frame in ping_frames:
        await msg.edit(f"```\n{frame}\n```{choice(loading_emojis)}")
        await asyncio.sleep(0.3)  # Smooth animation delay

    end = datetime.datetime.now()
    ping_duration = (end - start).microseconds / 1000

    # Status indicators based on ping speed
    if ping_duration < 100:
        status = "EXCELLENT 🟢"
    elif ping_duration < 200:
        status = "GOOD 🟡"
    else:
        status = "MODERATE 🔴"

    # Fancy formatted response
    response = f"""
╭──────────────────
│   PONG! 🏓
├──────────────────
│ ⌚ Speed: {ping_duration:.2f}ms
│ 📊 Status: {status}
│ ⏱️ Uptime: {uptime}
│ 👑 Owner: {owner.mention() if ow_id else f'[MUSIC BOT HOSTER ⚡](http://t.me/nub_hoster_bot?start={owner_id})'}
╰──────────────────
"""

    # Add random motivational messages
    quotes = [
        "Blazing fast! ⚡",
        "Speed demon! 🔥",
        "Lightning quick! ⚡",
        "Sonic boom! 💨"
    ]

    await msg.edit(
        response + f"\n<b>{choice(quotes)}</b>"
    )
