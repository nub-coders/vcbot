API_ID = 21869707
import asyncio
API_HASH = '31ec80a4adad7aaad9262e894e3654e6'
GROUP = "nub_coder_s"
CHANNEL = "nub_coders_updates"
import os
ggg=os.getcwd()
temporary ={}
active ={}
playing ={}
queues ={}
clients = {}
played= {}
linkage = {}
conversations = {}
connector = {}
songs_client = {}
owners = {}
spam_chats = []
broadcasts = {}
# Assuming `user_sessions` is a MongoDB collection.
broadcast_message = {}
import pymongo
import time
StartTime = time.time()
from telethon import TelegramClient, events, Button
from pyrogram import Client, filters
from thumbnails import *
mongo_client = pymongo.MongoClient('mongodb+srv://fuckyoudeeply:air8858@cluster0.wroq1fk.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')
db = mongo_client['voice']  #Replace 'your_database_name' with your actual database name
user_sessions = db['user_sessions']
collection = db["users"]

from fonts import *


styles = {
    'andalucia': andalucia,
    'arrows': arrows,
    'birds': birds,
    'bold_cool': bold_cool,
    'bold_gothic': bold_gothic,
    'bold_script': bold_script,
    'bubbles': bubbles,
    'circles': circles,
    'cloud': cloud,
    'comic': comic,
    'cool': cool,
    'dark_circle': dark_circle,
    'dark_square': dark_square,
    'frozen': frozen,
    'gothic': gothic,
    'happy': happy,
    'ladybug': ladybug,
    'manga': manga,
    'outline': outline,
    'rays': rays,
    'rvnes': rvnes,
    'sad': sad,
    'san': san,
    'script': script,
    'serief': serief,
    'sim': sim,
    'skyline': skyline,
    'slant': slant,
    'slant_san': slant_san,
    'slash': slash,
    'smallcap': smallcap,
    'special': special,
    'square': square,
    'stinky': stinky,
    'stop': stop,
    'strike': strike,
    'tiny': tiny,
    'typewriter': typewriter,
    'underline': underline
}
from network_keeper import NetworkKeepAlive

from network_keeper import NetworkKeepAlive
BOT_TOKEN = "7595158693:AAFf7OS5qtXtpPl9rKLi_ue7PAxwxEYLD7A"
#BOT_TOKEN = '7397709432:AAHLI7O0R0kAwLKg-87OwWMbbSRT9AAQ0XQ'
#BOT_TOKEN = '8170019611:AAG23HltqMvRwzmXMzZ7XdI1kotMRHQtdpQ'
async def main():
 app = Client("main_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN,in_memory=True,workers=1,
    sleep_threshold=30,  # Increased from default 10
)
 bot = TelegramClient(None, API_ID, API_HASH).start(bot_token=BOT_TOKEN)

 network_keeper = NetworkKeepAlive()
 keep_alive_task = asyncio.create_task(network_keeper.keep_connection_alive())

 app.idle()

if __name__ == "__main__":
    asyncio.run(main())

