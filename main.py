import shutil
import pyrogram
import os
import random
import asyncio
import sys
import time
import certifi
import pymongo
from pyrogram import Client,filters
from pyromod import Message
from telethon import TelegramClient, events, Button, types, errors
from pyrogram.errors.exceptions.unauthorized_401 import SessionPasswordNeeded
from pyrogram.raw.functions.phone import CreateGroupCall
from pyrogram.errors.exceptions.bad_request_400 import PasswordHashInvalid
from pyrogram.errors.exceptions.bad_request_400 import PhoneCodeInvalid
from pyrogram.errors.exceptions import AuthKeyDuplicated
from pyrogram.errors.exceptions import AuthKeyUnregistered
from pyrogram.errors.exceptions import SessionRevoked,ChatForwardsRestricted
from pyrogram.errors.exceptions import PeerFlood,UserRestricted,FileReferenceExpired
from pyrogram.errors.exceptions import UserDeactivatedBan
from pyrogram.errors.exceptions import PeerIdInvalid
from pyrogram.errors.exceptions import UserDeactivated
from pytgcalls import idle, PyTgCalls
from pytgcalls.types import MediaStream
mongo_client = pymongo.MongoClient('mongodb+srv://brock:brock123@cluster0.clzne.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0',tlsCAFile=certifi.where())
db = mongo_client['voice']  #Replace 'your_database_name' with your actual database name
user_sessions = db['user_sessions']
from datetime import datetime
clients = {}  # Dictionary to store client objects
import os
StartTime = time.time()
from config import *
bot = TelegramClient(None, API_ID, API_HASH)
bot.start(bot_token=BOT_TOKEN)
from pyromod import Client as pccc
app = pccc(":hehe",api_id=API_ID,api_hash=API_HASH,bot_token=BOT_TOKEN, in_memory=True)
import pytgcalls
songs_client = {}
ggg=os.getcwd()
conversations = {}



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


# Command handler for /ping
@bot.on(events.NewMessage(pattern='/ping'))
async def ping_command(event):
    # Calculate uptime
    uptime = await get_readable_time((time.time() - StartTime))
    start = datetime.now()

    # Simulate progress bar
    xx = await event.reply("**0% ▒▒▒▒▒▒▒▒▒▒**")
    await xx.edit("**20% ██▒▒▒▒▒▒▒▒**")
    await xx.edit("**40% ████▒▒▒▒▒▒**")
    await xx.edit("**60% ██████▒▒▒▒**")
    await xx.edit("**80% ████████▒▒**")
    await xx.edit("**100% ██████████**")

    # Calculate the duration
    end = datetime.now()
    duration = (end - start).microseconds / 1000

    # Send the final message with ping and uptime information
    await xx.edit(
        f"❏ **PONG!! 🏓**\n"
        f"├• **Pinger** - `{duration:.2f}ms`\n"
        f"├• **Uptime -** `{uptime}`\n"
        f"└• **Owner :** [{(await bot.get_me()).first_name}](tg://user?id={(await bot.get_me()).id})"
    )

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
                    clients[sender] = Client(f"user_{sender}", api_id=API_ID, api_hash=API_HASH, in_memory=True, no_updates=True)
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

@bot.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    user_id = event.sender_id
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
        "13. **/join <num_clients> <group_or_channel_invite_link_or_username>** - Join a voice chat.\n"
        "4. **/left <num_of_clients> <group_or_channel_invite_link_or_username_or_user_id>** - left the group/channel.\n"
        "15. **/reboot** - Restart the bot.\n"
        "16. **/cancel** - Cancel the current commenting process.\n"
    )
    await event.respond(response)


@bot.on(events.NewMessage(pattern='/leave (\d+) (.+)'))
async def leave_voice_chat(event):
    user_id = event.sender_id

    # Check if the user is an admin
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return

    # Extract the number of clients and group identifier (could be an invite link or a chat ID)
    num_clients_to_leave = int(event.pattern_match.group(1))
    group_identifier = event.pattern_match.group(2)

    left_users = 0

    for sender in list(songs_client.keys()):
        call_py = songs_client.get(sender)
        client = clients.get(sender)
        try:
            # Check if the group identifier is a number (chat ID)
            if group_identifier.isdigit():
                chat_id = int(group_identifier)
            else:
                # If not a number, assume it's an invite link or username and get chat details
                chat = await client.get_chat(group_identifier)
                chat_id = chat.id

            # Leave the voice chat
            await call_py.leave_call(chat_id)
            left_users += 1
            print(f"{client} left the voice chat.")
        except Exception as e:
            print(e)

        # Break if we've left the required number of clients
        if left_users >= num_clients_to_leave:
            break

    await event.reply(f"Left {left_users} clients from the voice chat.")



@bot.on(events.NewMessage(pattern='/report (\d+) (\d+)'))
async def leave_voice_chat(event):
    user_id = event.sender_id

    # Check if the user is an admin
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return

    # Extract the number of clients and group identifier (could be an invite link or a chat ID)
    num_clients_to_leave = int(event.pattern_match.group(1))
    group_identifier = event.pattern_match.group(2)

    left_users = 0

    for sender in list(songs_client.keys()):
        client = clients.get(sender)
        try:
            peer=(client.resolve_peer(group_identifier))
            message = "This user is violating Telegram's Terms of Service."
            # Leave the voice chat
            reason = types.InputReportReasonChildAbuse()
            result = client.invoke(functions.account.ReportPeer(peer=peer, reason=reason, message=message))
            left_users += 1
            print(f"{client} reported the {group_identifier}.")
        except Exception as e:
            print(e)

        # Break if we've left the required number of clients
        if left_users >= num_clients_to_leave:
            break

    await event.reply(f"{left_users} clients reported the {group_identifier}.")


@bot.on(events.NewMessage(pattern='/left (\d+) (.+)'))
async def leave_voice_chat(event):
    user_id = event.sender_id

    # Check if the user is an admin
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return

    # Extract the number of clients and group identifier (could be an invite link or a chat ID)
    num_clients_to_leave = int(event.pattern_match.group(1))
    group_identifier = event.pattern_match.group(2)

    left_users = 0

    for sender in list(songs_client.keys()):
        client = clients.get(sender)
        try:
            # Check if the group identifier is a number (chat ID)
            if group_identifier.isdigit():
                chat_id = int(group_identifier)
            else:
                # If not a number, assume it's an invite link or username and get chat details
                chat = await client.get_chat(group_identifier)
                chat_id = chat.id

            # Leave the voice chat
            await client.leave_chat(chat_id)
            left_users += 1
            print(f"{client} left the chat.")
        except Exception as e:
            print(e)

        # Break if we've left the required number of clients
        if left_users >= num_clients_to_leave:
            break

    await event.reply(f"Left {left_users} clients from the chat.")


@bot.on(events.NewMessage(pattern=r'/vote (\d) (\d+) (\d+) (.+) (\d+)'))
async def vote_on_poll(event):
    user_id = event.sender_id

    # Check if the user is an admin
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return
    poll_index = int(event.pattern_match.group(1))   # The poll option index
    num_clients_to_vote = int(event.pattern_match.group(2))  # Number of clients to vote
    message_id = int(event.pattern_match.group(3))       # The message URL containing the poll)
    join_url = event.pattern_match.group(4)          # The group/channel join URL
    sleep_time = int(event.pattern_match.group(5))
    if poll_index < 0 or poll_index > 9:
       return await event.reply("Invalid poll index. Please provide a number between 0 and 9.")
    voted_users = 0
    for sender in list(songs_client.keys()):
        client = clients.get(sender)
        try:
             chat = await client.join_chat(join_url)
        except Exception as e:
             chat = await client.get_chat(join_url)
        try:
                    await client.vote_poll(chat.id, message_id, poll_index)
                    try:
                        await client.invoke(pyrogram.raw.functions.messages.GetMessagesViews(peer=await client.resolve_peer(chat.id),id=[message_id],increment=True))
                    except Exception as e:
                         await event.reply(f"Client {sender} failed to increase the viewcount: {e}")
                    voted_users += 1
                    await event.reply(f"Client {sender} successfully voted for option {poll_index + 1}.")
                    await asyncio.sleep(sleep_time)
                    if voted_users >= num_clients_to_vote:
                        break
        except Exception as e:
                    await event.reply(f"Client {sender} failed to vote on the poll: {e}")
    if voted_users < num_clients_to_vote:
            await event.reply(f"Only {voted_users} out of {num_clients_to_vote} clients successfully voted.")
    else:
            await event.reply(f"All {num_clients_to_vote} clients successfully voted.")
    

from telethon import events


@bot.on(events.NewMessage(pattern='/get'))
async def get_telegram_chat(event):
    user_id = event.sender_id

    # Check if the user is an admin
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return
    parts=event.raw_text.split()
    if len(parts) ==2:
      client = clients.get(int(parts[1]))
      async for message in client.get_chat_history(777000,limit=5):
       if not message.from_user.is_self and message.text:
          await bot.send_message(user_id, message.text, parse_mode="html")

@bot.on(events.NewMessage(pattern='/check'))
async def check_telegram_chat(event):
    user_id = event.sender_id

    # Check if the user is an admin
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return

    # Extract the number of clients and group invite link from the command

    joined_users = 0
    try:
     for sender in list(songs_client.keys()):
        client = clients.get(sender)
        async for message in client.get_chat_history(777000,limit=10):
            if not message.from_user.is_self and message.media:
               await bot.send_message(user_id,f"<blockquote>{client.me.first_name} {sender}</blockquote>having media",parse_mode="html")
    except Exception as e:
        await bot.send_message(user_id,e)

@bot.on(events.NewMessage(pattern='/join (\d+) (.+)'))
async def join_voice_chat(event):
    user_id = event.sender_id

    # Check if the user is an admin
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return

    # Extract the number of clients and group invite link from the command
    num_clients_to_join = int(event.pattern_match.group(1))
    group_invite_link = event.pattern_match.group(2)

    joined_users = 0

    for sender in list(songs_client.keys()):
        call_py = songs_client.get(sender)
        client = clients.get(sender)
        try:
            # Join the chat using the invite link
            try:
                chat = await client.join_chat(group_invite_link)
            except:
                chat = await client.get_chat(group_invite_link)

            # Join the voice chat
            audio_file = 'input.webm'
            joined_users += 1
            await call_py.play(
            chat.id)
            await call_py.mute_stream(chat.id)
            #except pytgcalls.exceptions.UnMuteNeeded:
            print(f"{client} joined the voice chat.")
        except Exception as e:
            await event.respond(f"Error joining with {sender}: {e}")

        # Break if we've joined the required number of clients
        if joined_users >= num_clients_to_join:
            break

    await event.reply(f"Joined {joined_users} clients to the voice chat.")
# Start the bot
@bot.on(events.NewMessage(pattern='^/reboot$'))
async def reboot_handler(event):
    user_id = event.sender_id

    # Check if the user is an admin by comparing their user ID with the ones in /home/u219967/Work/Work/Work/zipper//home/u219967/W$
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id in admin_ids:
                await event.respond("Admin command received. Stopping the bot...")
                sys.exit(0)  # Raise a system exit exception to stop the entire code
            else:
                await event.respond("You are not authorized to use this command.")
    else:
        await event.respond("Admin file not found. Please contact the bot admin.")

@bot.on(events.NewMessage(pattern='/activers'))
async def handler(event):
    user_id = event.sender_id

    # Check if the user is an admin
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return

    user_ids = list(songs_client.keys())

    # Count the active clients
    num_active_clients = len(user_ids)

    # Build the message with mentions
    message = f"Active client user IDs:\n"
    for client_id in user_ids:
        # Get the user's first and last name using get_input_entity
        try:
            user = await bot.get_entity(client_id)
            first_name = user.first_name
            last_name = user.last_name if user.last_name else ''
            full_name = f"{first_name} {last_name}".strip()
        except Exception as e:
            print(f"Error getting user details: {e}")
            full_name = "Unknown"  # Handle errors by setting name to "Unknown"

        message += f"[{full_name}](tg://user?id={client_id}) - {client_id}\n"

    message += f"\nNumber of active clients: {num_active_clients}"

    max_length = 4000
    for i in range(0, len(message), max_length):
        chunk = message[i:i + max_length]
        await event.reply(chunk)
    # Send the message
                    # Store user's phone number
# Define client outside of any function scope
async def run_client(sender):


    # Check if the sender's session exists
    user_data = user_sessions.find_one({"user_id": sender})
    if user_data:
        string_session = user_data.get("string_session")

        # Initialize the client with the retrieved data
        clients[sender] = Client(f"user_{sender}", api_id=API_ID, api_hash=API_HASH, sleep_threshold=32, session_string=string_session, in_memory=True, no_updates=True)
        client = clients.get(sender)
        songs_client[sender]=PyTgCalls(client)
        call_py= songs_client.get(sender)
        await call_py.start()
    else:
        print("User session not found.")

async def run_all_client():
    user_ids = user_sessions.distinct("user_id")
    for user_id in user_ids:
        user_data = user_sessions.find_one({"user_id": user_id})
        if user_data:
            string_session = user_data.get("string_session")

            # Initialize the client with the retrieved data
            clients[user_id]  = Client(f"user_{user_id}", api_id=API_ID, api_hash=API_HASH, sleep_threshold=32, workers=1, session_string=string_session, in_memory=True, no_updates=True)
            client = clients.get(user_id)
            songs_client[user_id]=PyTgCalls(client)
            call_py= songs_client.get(user_id)
            try:
                auth=await client.connect()
                if not auth:
                    print("Client is not authorized. Please authorize first.")
                    user_sessions.delete_one({"user_id": user_id})
                    continue
                await client.disconnect()
                await call_py.start()
                #await client.send_message('nub_userbot','/start')
                print("Handlers added successfully.")
                #try:
                   #await client.join_chat("nub_coder_s")
                   #await client.join_chat("nub_coders_updates")

                #except:
                   #pass
                # Add your additional logic here if needed
            except Exception as e:
                admin_file = f"{ggg}/admin.txt"
                if os.path.exists(admin_file):
                   with open(admin_file, "r") as file:
                      admin_ids = [int(line.strip()) for line in file.readlines()]
                      for admin_id  in admin_ids:
                          try:
                             await bot.send_message(admin_id,f"Error starting client for user {user_id}: {e}")
                          except:
                                pass
                user_sessions.delete_one({"user_id": user_id})
                songs_client.pop(user_id)



# Dictionary to store comments with admin_id as the key


# Dictionary to store comments with admin_id as the key
admin_comments = {}
# Dictionary to track admins who are in "adding mode"
adding_mode = {}
# Dictionary to track the cancellation state
cancel_process = {}

# Your Telethon bot instance

# Check if the user is an admin
def is_admin(user_id):
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            return user_id in admin_ids
    return False

# Handler to start adding comments
@bot.on(events.NewMessage(pattern='/add'))
async def start_adding_comments(event):
    user_id = event.sender_id

    # Ensure the user is an admin
    if not is_admin(user_id):
        await event.respond("You are not authorized to perform this action.")
        return

    # Initialize or reset the admin's comment list
    admin_comments[user_id] = []
    adding_mode[user_id] = True

    await event.respond("You are now in 'add mode'. Send messages to add them as comments. Type /done when finished.")

# Handler to stop adding comments
@bot.on(events.NewMessage(pattern='/done'))
async def stop_adding_comments(event):
    user_id = event.sender_id

    # Ensure the user is an admin
    if not is_admin(user_id):
        await event.respond("You are not authorized to perform this action.")
        return

    # Stop adding mode
    if user_id in adding_mode and adding_mode[user_id]:
        adding_mode[user_id] = False
        await event.respond(f"Added {len(admin_comments[user_id])} comments. You can now post them using /comment.")
    else:
        await event.respond("You are not in 'add mode'. Start with /add.")

# Handler to clear all comments for the admin
@bot.on(events.NewMessage(pattern='/clear'))
async def clear_comments(event):
    user_id = event.sender_id

    # Ensure the user is an admin
    if not is_admin(user_id):
        await event.respond("You are not authorized to perform this action.")
        return

    # Clear the comments for the admin
    admin_comments[user_id] = []
    user_path='downloads'
    if os.path.exists(user_path):
        shutil.rmtree(user_path,ignore_errors=True)
    await event.respond("All comments have been cleared.")

# Handler to add comments while in "add mode"
# Handler to add comments while in "add mode"
@app.on_message(~filters.command("comments") & ~filters.command("done") & ~filters.command("clear") & ~filters.command("comment") & ~filters.command("add"))
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
# Handler to send all comments back to the admin
@app.on_message(filters.command("comments"))
async def send_all_comments(client: Client, message: Message):
    print('hdhd')
    user_id = message.from_user.id

    # Ensure the user is an admin
    if not is_admin(user_id):
        await message.reply("You are not authorized to perform this action.")
        return

    # Check if there are any comments to show
    if user_id not in admin_comments or not admin_comments[user_id]:
        await message.reply("No comments have been added.")
        return

    # Send each comment back to the admin
    for comment in admin_comments[user_id]:
        if comment["type"] == "text":
            await message.reply(comment["content"])
        elif comment["type"] == "sticker":
            await message.reply_sticker(comment["content"])
        elif comment["type"] == "gif":
            await message.reply_animation(comment["content"])
# Handler to cancel the comment process
@bot.on(events.NewMessage(pattern='/cancel'))
async def cancel_comment_process(event):
    user_id = event.sender_id

    # Ensure the user is an admin
    if not is_admin(user_id):
        await event.respond("You are not authorized to perform this action.")
        return

    # Set the cancellation flag to True
    cancel_process[user_id] = True
    user_path='downloads'
    if os.path.exists(user_path):
        shutil.rmtree(user_path,ignore_errors=True)
    await event.respond("Commenting process has been canceled.")

# Function to post comments (from Pyrogram/Telethon handler)
@bot.on(events.NewMessage(pattern=r'/bvote (\d+) (\d+) (\d+) (.+) (\d+)'))
async def vote_on_button(event):
    user_id = event.sender_id

    # Check if the user is an admin
    admin_file = f"{ggg}/admin.txt"
    if os.path.exists(admin_file):
        with open(admin_file, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                return
    poll_index = int(event.pattern_match.group(1))   # The poll option index
    num_clients_to_vote = int(event.pattern_match.group(2))  # Number of clients to vote
    message_id = int(event.pattern_match.group(3))       # The message URL containing the poll)
    join_url = event.pattern_match.group(4)          # The group/channel join URL
    sleep_time = int(event.pattern_match.group(5))
    voted_users = 0
    for sender in list(songs_client.keys()):
        client = clients.get(sender)
        try:
             chat = await client.join_chat(join_url)
        except Exception as e:
             chat = await client.get_chat(join_url)
        try:
                    dessage = await client.get_messages(chat.id,message_id)
                    try:
                         await client.invoke(pyrogram.raw.functions.messages.GetMessagesViews(peer=await client.resolve_peer(chat.id),id=[message_id],increment=True))
                    except Exception as e:
                         await event.reply(f"Client {sender} failed to increase the viewcount: {e}")
                    await dessage.click(poll_index)
                    voted_users += 1
                    await event.reply(f"Client {sender} successfully clickd for option {poll_index +1}.")
                    await asyncio.sleep(sleep_time)
                    if voted_users >= num_clients_to_vote:
                        break
        except Exception as e:
                    await event.reply(f"Client {sender} failed to vote on the poll: {e}")
    if voted_users < num_clients_to_vote:
            await event.reply(f"Only {voted_users} out of {num_clients_to_vote} clients successfully voted.")
    else:
            await event.reply(f"All {num_clients_to_vote} clients successfully voted.")


@bot.on(events.NewMessage(pattern='/comment (.+) (\d+) (\d+)'))
async def comment_on_post(event):
    user_id = event.sender_id

    # Ensure the user is an admin
    if not is_admin(user_id):
        await event.respond("You are not authorized to perform this action.")
        return

    # Extract the channel link/username and event ID from the command
    channel_username_or_link = event.pattern_match.group(1)
    message_id = int(event.pattern_match.group(2))
    sleep_time = int(event.pattern_match.group(3))
    # Check if the admin has any comments
    if user_id not in admin_comments or not admin_comments[user_id]:
        await event.respond("No comments have been added. Use /add to add comments.")
        return

    commented_users = 0
    available_clients = list(songs_client.keys())

    # Ensure there are enough clients to handle all comments
    if len(available_clients) < len(admin_comments[user_id]):
        await event.respond("Not enough clients to comment. Exiting.")
        return

    # Reset cancel flag for the current process
    cancel_process[user_id] = False

    for comment in admin_comments[user_id]:
        # If cancel is triggered, break out of the loop
        if cancel_process.get(user_id, False):
            await event.respond("Commenting process was canceled.")
            break

        # Randomly select a client from available_clients and remove it from the list
        sender = random.choice(available_clients)
        client = clients.get(sender)
        available_clients.remove(sender)

        try:
            # Join or get the chat
            try:
                channel = await client.join_chat(channel_username_or_link)
            except:
                channel = await client.get_chat(channel_username_or_link)

            # Get the discussion event
            discussion_message = await client.get_discussion_message(channel.id, message_id)
            try:
                 await client.invoke(pyrogram.raw.functions.messages.GetMessagesViews(peer=await client.resolve_peer(channel.id),id=[message_id],increment=True))
            except Exception as e:
                 await event.reply(f"Client {sender} failed to increase the viewcount: {e}")

            # Comment by replying to the discussion message
            if comment['type'] == 'text':
                await discussion_message.reply(comment['content'])
            elif comment['type'] == 'sticker':
                await discussion_message.reply_sticker(comment['content'])
            elif comment['type'] == 'gif':
                await discussion_message.reply_animation(comment['content'])
                os.remove(comment['content'])
            commented_users += 1
            await asyncio.sleep(sleep_time)  # 30-second delay
            await event.respond(f"Successfully commented '{comment}' on {channel.title}")

        except Exception as e:
            await event.respond(f"Error commenting with {sender}: {e}")
            continue

    # Clean up the comments after posting
    admin_comments[user_id] = []

    if not cancel_process.get(user_id, False):
        await event.respond(f"Finished commenting with {commented_users} clients.")

# Start the Telethon bot

# Start the Pyrogram client

app.start()
bot.loop.run_until_complete(run_all_client())
bot.run_until_disconnected()
