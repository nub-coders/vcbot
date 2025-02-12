import json
import subprocess
import requests
import re
from io import BytesIO
from urllib.parse import parse_qs, urlparse

import asyncio
import math
import os
import shlex
from typing import Tuple

from PIL import Image
from pymediainfo import MediaInfo
from pyrogram.types import Message
import time

import os
from asyncio import sleep
import os
import sys
from re import sub
from fonts import *
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import time
import asyncio
from config import *

from pyrogram import Client, filters
import gc
import time

from pyrogram.errors import (
    FloodWait,
    RPCError,
)

# Replace with your actual API ID and API hash from my.telegram.org                     
async def handle_disconnect(client, retries=5, delay=5):
    """Handles disconnects by attempting to reconnect with retries."""
    for attempt in range(retries):
        try:
            print(f"Attempting to reconnect (attempt {attempt + 1}/{retries})...")
            await client.connect()
            if client.is_connected:
                print("Successfully reconnected.")
                break  # Exit the loop if reconnected successfully
        except FloodWait as e:
            print(f"Floodwait encountered, waiting {e.value} seconds")
            await asyncio.sleep(e.value)
        except RPCError as e:
             print(f"RPC Error, not retrying: {e}")
             break
        except Exception as e:
            print(f"Unexpected error: {e}")
            break
    else:
        print(f"Failed to reconnect after {retries} attempts.")

import asyncio


import psutil
import os
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
def get_arg(message):
    msg = message.text
    msg = msg.replace(" ", "", 1) if msg[1] == " " else msg
    split = msg[1:].replace("\n", " \n").split(" ")
    if " ".join(split[1:]).strip() == "":
      return ""
    return " ".join(split[1:])

async def remove_active_chat(user_client, chat_id):
    if chat_id in active[user_client.me.username]:
        active[user_client.me.username].remove(chat_id)



async def autoleave_vc(user_client, call_py, message, duration_str):
    """
    Automatically leave voice chat when only the bot remains in the call for 5 seconds
    """
    session_client = call_py._mtproto
    bot_id = user_client.me.id  # Get bot's own user ID
    
    while True:
        try:
            # Track if song duration changes
            if message.chat.id in playing and playing[message.chat.id]:
                current_song = playing[message.chat.id]
                if str(current_song['duration']) != str(duration_str):
                    break
        except Exception:
            pass

        try:
            # Get current call members
            members = []
            async for member in session_client.get_call_members(message.chat.id):
                members.append(member)

            # Check if only bot remains in call
            if len(members) == 1 and members[0].chat.id == session_client.me.id:
                # Confirm persistent presence check
                await asyncio.sleep(25)
                
                # Recheck after cooldown
                members = []
                async for member in session_client.get_call_members(message.chat.id):
                    members.append(member)

                # Final verification before leaving
                if len(members) == 1 and members[0].chat.id == session_client.me.id:
                    await call_py.leave_call(message.chat.id)
                    # Cleanup operations
                    try:
                        queues.get(f"dic_{bot_id}")[message.chat.id].clear()
                        playing[message.chat.id].clear()
                    except KeyError:
                        pass
                    
                    await remove_active_chat(user_client, message.chat.id)
                    await user_client.send_message(
                        message.chat.id,
                        "⚠️ Nᴏ ᴀᴄᴛɪᴠᴇ ʟɪsᴛᴇɴᴇʀs ᴅᴇᴛᴇᴄᴛᴇᴅ. Lᴇᴀᴠɪɴɢ ᴠᴏɪᴄᴇ ᴄʜᴀᴛ."
                    )
                    await remove_active_chat(user_client, message.chat.id)
                    break

        except Exception as e:
            print(f"Autoleave error: {e}")
            break

        # Reduced check interval
        await asyncio.sleep(8)

async def pautoleave_vc(user_client, call_py, message, duration_str):
    """
    Automatically leave voice chat when members count is <= 1 for 5 seconds
    
    :param user_client: User client to get call members and send messages
    :param call_py: PyTgCalls client for leaving call
    :param message: Message object containing chat information
    :param playing: Dictionary tracking currently playing songs
    :param duration_str: Current song duration
    """
    session_client = call_py._mtproto
    while True:
        try:
            # Check if current song duration changed
            if message.chat.id in playing and playing[message.chat.id]:
                current_song = playing[message.chat.id]
                if str(current_song['duration']) != str(duration_str):
                    break
        except Exception:
            pass

        # Get current call members
        members = []
        try:
          async for i in session_client.get_call_members(message.chat.id):
            members.append(i)
        except:
           break
        # Check if members count is <= 1
        if len(members) <= 1:
            # Wait 5 seconds to confirm
            await asyncio.sleep(5)
            
            # Recheck members count after 5 seconds
            members = []
            async for i in session_client.get_call_members(message.chat.id):
                members.append(i)
            
            # If still <= 1 member, leave the voice chat
            if len(members) <= 1:
                await call_py.leave_call(message.chat.id)
                # Send message about leaving
                try:
                    song_queue = queues.get(f"dic_{user_client.me.id}")
                    song_queue[message.chat.id].clear()
                except:
                   pass
                try:
                    playing[message.chat.id].clear()
                except:
                   pass
                await remove_active_chat(user_client, message.chat.id)
                await user_client.send_message(
                    message.chat.id, 
                    f"ɴᴏ ᴏɴᴇ ɪꜱ ʟɪꜱᴛᴇɴɪɴɢ ᴛᴏ ᴛʜᴇ ꜱᴛʀᴇᴀᴍ, ꜱᴏ ᴛʜᴇ ᴀꜱꜱɪꜱᴛᴀɴᴛ ʟᴇꜰᴛ ᴛʜᴇ ᴠᴏɪᴄᴇ ᴄʜᴀᴛ."
                )
                break
        
        # Wait before next check
        await asyncio.sleep(10)


async def update_progress_button(message, duration_str, call_py):
    try:
        total_seconds = sum(int(x) * 60 ** i for i, x in enumerate(reversed(duration_str.split(":"))))

        while True:
            try:
                # Fetch elapsed seconds
                elapsed_seconds = int(await call_py.played_time(message.chat.id))
            except Exception as e:
                # If an exception occurs, the song has ended
                await message.edit_caption(message.caption.replace("ϟ ɴᴏᴡ ᴘʟᴀʏɪɴɢ ϟ", "ϟ sᴛʀᴇᴀᴍ ᴇɴᴅᴇᴅ ϟ").strip())
                break
            try:
               if message.chat.id in playing and playing[message.chat.id]:
                   current_song = playing[message.chat.id]
                   if str(current_song['duration']) != str(duration_str):
                       await message.edit_caption(message.caption.replace("ϟ 𝗡𝗼𝘄 𝗣𝗹𝗮𝘆𝗶𝗻𝗴 ϟ", "ϟ 𝗦𝘁𝗿𝗲𝗮𝗺 𝗘𝗻𝗱𝗲𝗱 ϟ").strip())
                       break            # Format elapsed time
            except Exception as e:
                passs
            elapsed_str = time.strftime('%M:%S', time.gmtime(elapsed_seconds))

            # Calculate progress bar (6 `─` with spaces)
            progress_length = 8
            position = min(int((elapsed_seconds / total_seconds) * progress_length), progress_length)
            progress_bar = "─ " * position + "▷" + "─ " * (progress_length - position - 1)
            progress_bar = progress_bar.strip()  # Remove trailing spaces

            progress_text = f"{elapsed_str} {progress_bar} {duration_str}"

            # Insert progress bar between the first and last rows
            keyboard = message.reply_markup.inline_keyboard
            progress_row = [InlineKeyboardButton(text=progress_text, callback_data="ignore")]
            updated_keyboard = keyboard[:1] + [progress_row] + keyboard[1:]

            await message.edit_reply_markup(InlineKeyboardMarkup(updated_keyboard))
            await asyncio.sleep(9)
    except Exception as e:
        print(f"Progress update error: {e}")


def get_readable_time(seconds: int) -> str:
    count = 0
    ping_time = ""
    time_list = []
    time_suffix_list = ["s", "ᴍ", "ʜ", "ᴅᴀʏs"]
    while count < 4:
        count += 1
        if count < 3:
            remainder, result = divmod(seconds, 60)
        else:
            remainder, result = divmod(seconds, 24)
        if seconds == 0 and remainder == 0:
            break
        time_list.append(int(result))
        seconds = int(remainder)
    for i in range(len(time_list)):
        time_list[i] = str(time_list[i]) + time_suffix_list[i]
    if len(time_list) == 4:
        ping_time += time_list.pop() + ", "
    time_list.reverse()
    ping_time += ":".join(time_list)
    return ping_time

queue_styles = {
    1: '''♫ 𝔸𝕕𝕕𝕖𝕕 𝕥𝕠 ℚ𝕦𝕖𝕦𝕖 ♫
➲ Mode: {}
➲ Title: {}
➲ Duration: {}
➲ Position: #{}''',

    2: '''✧ 𝓝𝓮𝔀 𝓣𝓻𝓪𝓬𝓴 ✧
𝓜𝓸𝓭𝓮: {}
𝓣𝓲𝓽𝓵𝓮: {}
𝓓𝓾𝓻𝓪𝓽𝓲𝓸𝓷: {}
𝓠𝓾𝓮𝓾𝓮: #{}''',

    3: '''⚡ 𝖖𝖚𝖊𝖚𝖊 𝖚𝖕𝖉𝖆𝖙𝖊 ⚡
𝖒𝖔𝖉𝖊: {}
𝖙𝖗𝖆𝖈𝖐: {}
𝖑𝖊𝖓𝖌𝖙𝖍: {}
𝖕𝖔𝖘: {}''',

    4: '''✧ ᑎᗴᗯ 丅ᖇᗩᑕK ✧
ᗰᗝᗪᗴ: {}
丅I丅ᒪᗴ: {}
丅Iᗰᗴ: {}
ᑭᗝᔕ: #{}''',

    5: '''♪ 𝚀𝚄𝙴𝚄𝙴 𝚄𝙿𝙳𝙰𝚃𝙴 ♪
𝙼𝙾𝙳𝙴: {}
𝚃𝚁𝙰𝙲𝙺: {}
𝚃𝙸𝙼𝙴: {}
𝙿𝙾𝚂: #{}''',

    6: '''✿ 𝔔𝔲𝔢𝔲𝔢 𝔖𝔱𝔞𝔱𝔲𝔰 ✿
𝔐𝔬𝔡𝔢: {}
𝔗𝔦𝔱𝔩𝔢: {}
𝔗𝔦𝔪𝔢: {}
𝔓𝔬𝔰: #{}''',

    7: '''☆ ᴛʀᴀᴄᴋ ᴀᴅᴅᴇᴅ ☆
ᴍᴏᴅᴇ: {}
ᴛɪᴛʟᴇ: {}
ᴛɪᴍᴇ: {}
ᴘᴏꜱ: #{}''',

    8: '''❀ 𝕋𝕣𝕒𝕔𝕜 𝔸𝕕𝕕𝕖𝕕 ❀
𝕄𝕠𝕕𝕖: {}
𝕋𝕚𝕥𝕝𝕖: {}
𝕋𝕚𝕞𝕖: {}
ℙ𝕠𝕤: #{}''',

    9: '''✦ ＱＵＥＵＥ ✦
ＭＯＤＥ: {}
ＴＩＴＬＥ: {}
ＴＩＭＥ: {}
ＰＯＳ: #{}''',

    10: '''⚛ Q̲u̲e̲u̲e̲ U̲p̲d̲a̲t̲e̲ ⚛
M̲o̲d̲e̲: {}
T̲i̲t̲l̲e̲: {}
T̲i̲m̲e̲: {}
P̲o̲s̲: #{}''',

    11: '''✤ 𝓠𝓾𝓮𝓾𝓮 𝓢𝓽𝓪𝓽𝓾𝓼 ✤
𝓜𝓸𝓭𝓮: {}
𝓣𝓲𝓽𝓵𝓮: {}
𝓣𝓲𝓶𝓮: {}
𝓟𝓸𝓼: #{}''',

    12: '''⌘ 𝔸𝕕𝕕𝕖𝕕 𝕥𝕠 ℚ𝕦𝕖𝕦𝕖 ⌘
𝕄𝕠𝕕𝕖: {}
𝕋𝕚𝕥𝕝𝕖: {}
𝕋𝕚𝕞𝕖: {}
ℙ𝕠𝕤: #{}''',

    13: '''✾ Ⓠⓤⓔⓤⓔ ✾
Ⓜⓞⓓⓔ: {}
Ⓣⓘⓣⓛⓔ: {}
Ⓣⓘⓜⓔ: {}
Ⓟⓞⓢ: #{}''',

    14: '''❋ 𝚃𝚛𝚊𝚌𝚔 𝙰𝚍𝚍𝚎𝚍 ❋
𝙼𝚘𝚍𝚎: {}
𝚃𝚒𝚝𝚕𝚎: {}
𝚃𝚒𝚖𝚎: {}
𝙿𝚘𝚜: #{}''',

    15: '''✺ 𝖰𝖴𝖤𝖴𝖤 𝖴𝖯𝖣𝖠𝖳𝖤 ✺
𝖬𝖮𝖣𝖤: {}
𝖳𝖨𝖳𝖫𝖤: {}
𝖳𝖨𝖬𝖤: {}
𝖯𝖮𝖲: #{}''',
    16:'''⇛ 𝐒𝐨𝐧𝐠 𝐚𝐝𝐝𝐞𝐝 𝐭𝐨 𝐭𝐡𝐞 𝐪𝐮𝐞𝐮𝐞 ⇛
➲ ᴍᴏᴅᴇ: {}
➲ ᴛɪᴛʟᴇ: {}
➲ ᴅᴜʀᴀᴛɪᴏɴ: {}
➲ Qᴜᴇᴜᴇ ᴘᴏꜱɪᴛɪᴏɴ: #{}
 ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ'''
}

play_styles = {
    1: '''♫ 𝕃𝕚𝕧𝕖 𝕠𝕟 𝔻𝕖𝕔𝕜 ♫
➲ Mode: {}
➲ Title: {}
➲ Duration: {}
➲ DJ: {}''',

    2: '''✧ 𝓝𝓸𝔀 𝓟𝓵𝓪𝔂𝓲𝓷𝓰 ✧
𝓜𝓸𝓭𝓮: {}
𝓣𝓲𝓽𝓵𝓮: {}
𝓓𝓾𝓻𝓪𝓽𝓲𝓸𝓷: {}
𝓤𝓼𝓮𝓻: {}''',

    3: '''⚡ 𝖈𝖚𝖗𝖗𝖊𝖓𝖙 𝖙𝖗𝖆𝖈𝖐 ⚡
𝖒𝖔𝖉𝖊: {}
𝖙𝖗𝖆𝖈𝖐: {}
𝖑𝖊𝖓𝖌𝖙𝖍: {}
𝖚𝖘𝖊𝖗: {}''',

    4: '''✧ ᑎᗝᗯ ᑭᒪᗩYIᑎᘜ ✧
ᗰᗝᗪᗴ: {}
丅I丅ᒪᗴ: {}
丅Iᗰᗴ: {}
ᗪᒍ: {}''',

    5: '''♪ 𝙽𝙾𝚆 𝙿𝙻𝙰𝚈𝙸𝙽𝙶 ♪
𝙼𝙾𝙳𝙴: {}
𝚃𝚁𝙰𝙲𝙺: {}
𝚃𝙸𝙼𝙴: {}
𝚄𝚂𝙴𝚁: {}''',

    6: '''✿ 𝔏𝔦𝔳𝔢 𝔗𝔯𝔞𝔠𝔨 ✿
𝔐𝔬𝔡𝔢: {}
𝔗𝔦𝔱𝔩𝔢: {}
𝔗𝔦𝔪𝔢: {}
𝔇𝔍: {}''',

    7: '''☆ ᴘʟᴀʏɪɴɢ ɴᴏᴡ ☆
ᴍᴏᴅᴇ: {}
ᴛɪᴛʟᴇ: {}
ᴛɪᴍᴇ: {}
ᴜꜱᴇʀ: {}''',

    8: '''❀ ℙ𝕝𝕒𝕪𝕚𝕟𝕘 ℕ𝕠𝕨 ❀
𝕄𝕠𝕕𝕖: {}
𝕋𝕚𝕥𝕝𝕖: {}
𝕋𝕚𝕞𝕖: {}
𝕌𝕤𝕖𝕣: {}''',

    9: '''✦ ＮＯＷ ＰＬＡＹＩＮＧ ✦
ＭＯＤＥ: {}
ＴＩＴＬＥ: {}
ＴＩＭＥ: {}
ＵＳＥＲ: {}''',

    10: '''⚛ O̲n̲ A̲i̲r̲ ⚛
M̲o̲d̲e̲: {}
T̲i̲t̲l̲e̲: {}
T̲i̲m̲e̲: {}
D̲J̲: {}''',

    11: '''✤ 𝓝𝓸𝔀 𝓟𝓵𝓪𝔂𝓲𝓷𝓰 ✤
𝓜𝓸𝓭𝓮: {}
𝓣𝓲𝓽𝓵𝓮: {}
𝓣𝓲𝓶𝓮: {}
𝓓𝓙: {}''',

    12: '''⌘ 𝕃𝕚𝕧𝕖 𝕋𝕣𝕒𝕔𝕜 ⌘
𝕄𝕠𝕕𝕖: {}
𝕋𝕚𝕥𝕝𝕖: {}
𝕋𝕚𝕞𝕖: {}
𝕌𝕤𝕖𝕣: {}''',

    13: '''✾ Ⓟⓛⓐⓨⓘⓝⓖ ✾
Ⓜⓞⓓⓔ: {}
Ⓣⓘⓣⓛⓔ: {}
Ⓣⓘⓜⓔ: {}
Ⓓⓙ: {}''',

    14: '''❋ 𝙽𝚘𝚠 𝙿𝚕𝚊𝚢𝚒𝚗𝚐 ❋
𝙼𝚘𝚍𝚎: {}
𝚃𝚒𝚝𝚕𝚎: {}
𝚃𝚒𝚖𝚎: {}
𝚄𝚜𝚎𝚛: {}''',

    15: '''✺ 𝖫𝖨𝖵𝖤 𝖳𝖱𝖠𝖢𝖪 ✺
𝖬𝖮𝖣𝖤: {}
𝖳𝖨𝖳𝖫𝖤: {}
𝖳𝖨𝖬𝖤: {}
𝖴𝖲𝖤𝖱: {}''',
    16: '''ϟ ɴᴏᴡ ᴘʟᴀʏɪɴɢ ϟ
➲ ᴍᴏᴅᴇ: {}
➲ ᴛɪᴛʟᴇ: {}
➲ ᴅᴜʀᴀᴛɪᴏɴ: {}
➲ ʀᴇQᴜᴇꜱᴛᴇᴅ ʙʏ: {}'''}


def convert_bytes(size: float) -> str:
    """humanize size"""
    if not size:
        return ""
    power = 1024
    t_n = 0
    power_dict = {0: " ", 1: "Ki", 2: "Mi", 3: "Gi", 4: "Ti"}
    while size > power:
        size /= power
        t_n += 1
    return "{:.2f} {}B".format(size, power_dict[t_n])


async def int_to_alpha(user_id: int) -> str:
    alphabet = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]
    text = ""
    user_id = str(user_id)
    for i in user_id:
        text += alphabet[int(i)]
    return text


async def alpha_to_int(user_id_alphabet: str) -> int:
    alphabet = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]
    user_id = ""
    for i in user_id_alphabet:
        index = alphabet.index(i)
        user_id += str(index)
    user_id = int(user_id)
    return user_id


def time_to_seconds(time):
    stringt = str(time)
    return sum(int(x) * 60**i for i, x in enumerate(reversed(stringt.split(":"))))


def seconds_to_min(seconds):
    if seconds is not None:
        seconds = int(seconds)
        d, h, m, s = (
            seconds // (3600 * 24),
            seconds // 3600 % 24,
            seconds % 3600 // 60,
            seconds % 3600 % 60,
        )
        if d > 0:
            return "{:02d}:{:02d}:{:02d}:{:02d}".format(d, h, m, s)
        elif h > 0:
            return "{:02d}:{:02d}:{:02d}".format(h, m, s)
        elif m > 0:
            return "{:02d}:{:02d}".format(m, s)
        elif s > 0:
            return "00:{:02d}".format(s)
    return "-"


def speed_converter(seconds, speed):
    if str(speed) == str("0.5"):
        seconds = seconds * 2
    if str(speed) == str("0.75"):
        seconds = seconds + ((50 * seconds) // 100)
    if str(speed) == str("1.5"):
        seconds = seconds - ((25 * seconds) // 100)
    if str(speed) == str("2.0"):
        seconds = seconds - ((50 * seconds) // 100)
    collect = seconds
    if seconds is not None:
        seconds = int(seconds)
        d, h, m, s = (
            seconds // (3600 * 24),
            seconds // 3600 % 24,
            seconds % 3600 // 60,
            seconds % 3600 % 60,
        )
        if d > 0:
            convert = "{:02d}:{:02d}:{:02d}:{:02d}".format(d, h, m, s)
            return convert, collect
        elif h > 0:
            convert = "{:02d}:{:02d}:{:02d}".format(h, m, s)
            return convert, collect
        elif m > 0:
            convert = "{:02d}:{:02d}".format(m, s)
            return convert, collect
        elif s > 0:
            convert = "00:{:02d}".format(s)
            return convert, collect
    return "-"


def check_duration(file_path):
    command = [
        "ffprobe",
        "-loglevel",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        file_path,
    ]

    pipe = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, err = pipe.communicate()
    _json = json.loads(out)

    if "format" in _json:
        if "duration" in _json["format"]:
            return float(_json["format"]["duration"])

    if "streams" in _json:
        for s in _json["streams"]:
            if "duration" in s:
                return float(s["duration"])

    return "Unknown"


formats = [
    "webm",
    "mkv",
    "flv",
    "vob",
    "ogv",
    "ogg",
    "rrc",
    "gifv",
    "mng",
    "mov",
    "avi",
    "qt",
    "wmv",
    "yuv",
    "rm",
    "asf",
    "amv",
    "mp4",
    "m4p",
    "m4v",
    "mpg",
    "mp2",
    "mpeg",
    "mpe",
    "mpv",
    "m4v",
    "svi",
    "3gp",
    "3g2",
    "mxf",
    "roq",
    "nsv",
    "flv",
    "f4v",
    "f4p",
    "f4a",
    "f4b",
]

async def convert_to_image(message, client) -> [None, str]:
    """Convert Most Media Formats To Raw Image"""
    if not message:
        return None
    if not message.reply_to_message:
        return None
    final_path = None
    if not (
        message.reply_to_message.video
        or message.reply_to_message.photo
        or message.reply_to_message.sticker
        or message.reply_to_message.media
        or message.reply_to_message.animation
        or message.reply_to_message.audio
    ):
        return None
    if message.reply_to_message.photo:
        final_path = await message.reply_to_message.download()
    elif message.reply_to_message.sticker:
        if message.reply_to_message.sticker.mime_type == "image/webp":
            final_path = "webp_to_png_s_proton.png"
            path_s = await message.reply_to_message.download()
            im = Image.open(path_s)
            im.save(final_path, "PNG")
        else:
            path_s = await client.download_media(message.reply_to_message)
            final_path = "lottie_proton.png"
            cmd = (
                f"lottie_convert.py --frame 0 -if lottie -of png {path_s} {final_path}"
            )
            await run_cmd(cmd)
    elif message.reply_to_message.audio:
        thumb = message.reply_to_message.audio.thumbs[0].file_id
        final_path = await client.download_media(thumb)
    elif message.reply_to_message.video or message.reply_to_message.animation:
        final_path = "fetched_thumb.png"
        vid_path = await client.download_media(message.reply_to_message)
        await run_cmd(f"ffmpeg -i {vid_path} -filter:v scale=500:500 -an {final_path}")
    return final_path                                                                                     
