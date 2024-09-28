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
USER_ID = int(input("Give user_id please: ")) # Replace with the user ID to fetc>
import datetime
from pyrogram import enums
from pyrogram.errors import FloodWait
import asyncio
import random
import re
from pyromod import listen
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



# Function to find a random word based on the given criteria
def find_random_words(filename, start_letter, word_length, include_letter=None):
    try:
        with open(filename, 'r') as file:
            words = file.read().splitlines()  # Read words from the file
    except FileNotFoundError:
        print(f"Error: The file '{filename}' was not found.")
        return []

    # Filtering words based on criteria
    filtered_words = [
        word for word in words
        if word.startswith(start_letter) and
           (not include_letter or include_letter in word) and
           len(word) == word_length
    ]
    print(f"Debug: Filtered words: {filtered_words}")

    if not filtered_words:
        return None

    return filtered_words
used_words = {}
# Listen to messages from the specific user @on9wordchainbot in a group context
@app.on_message(filters.user("on9wordchainbot") & filters.group)
async def wordchain_listener(client, message: Message):
    print("Debug: Received message from @on9wordchainbot")
    text = message.text
    print(f"Debug: Message text: {text}")
    # Check if the message contains "Turn:" and a user mention immediately after
    if "Turn:" in text:
        try:
            # Extract mentions from the message using markdown format
            entities = message.entities or []
            print(f"Debug: Entities found: {entities}")
            first_mention = None
            for entity in entities:
                # Look for the first mention after "Turn:"
                if entity.type == enums.MessageEntityType.TEXT_MENTION:
                    print(f"Debug:  mention found")
                    if "Turn:" in text and message.text.index("Turn:") < entity.offset:
                        first_mention = entity.user
                        print(f"Debug: First mention found: {first_mention.id}")
                        break

            # Verify if the first mention matches the current user ID
            if first_mention and first_mention.id == client.me.id:
                # Extract the word game details from the message
                print("Debug: First mention matches the bot's ID")
                word_info_line = re.search(r"Your word must start with (.+)", text).group(1)
                print(f"Debug: Word info line: {word_info_line}")
                # Extract capital letters and word length from the word info line
                capital_letters = re.findall(r'[A-Z]', word_info_line)
                word_length = int(re.search(r'\d+', word_info_line).group())
                print(f"Debug: Capital letters: {capital_letters}, Word length: {word_length}")


                # Determine the starting letter and included letter
                if len(capital_letters) == 1:
                    start_letter = capital_letters[0]
                    include_letter = None
                elif len(capital_letters) == 2:
                    start_letter = capital_letters[0]
                    include_letter = capital_letters[1]
                else:
                    print("Debug: Unexpected number of capital letters found.")
                    return

                # Find a random word based on the criteria
                filtered_words = find_random_words("words.txt", start_letter, word_length, include_letter)
                if not filtered_words:
                    await message.reply(f"@{client.me.username} No suitable word found.")
                    print("Debug: No suitable word found.")
                    return

                # Initialize chat ID and used word list if not exists
                chat_id = message.chat.id
                if chat_id not in used_words:
                    used_words[chat_id] = []

                # Select a random word that has not been used in this chat
                for attempt in range(10):
                    random_word = None
                    for _ in range(10):  # Try up to 10 times to find an unused word
                      random_word = random.choice(filtered_words)
                      if random_word not in used_words[chat_id]:
                        break
                      random_word = None

                    if random_word:
                        await asyncio.sleep(2)
                        used_words[chat_id].append(random_word)
                        await message.reply(random_word)
                        print(f"Debug: Reply sent with word: {random_word}")
                    else:
                       used_words[chat_id].append(random_word)
                       print("Debug: No suitable word found.")
                       pass
                    try:
                        response = await client.listen(chat_id=message.chat.id, user_id=message.from_user.id, timeout=3)
                        if response.text:
                            return
                    except Exception as e:
                        print(e)
                        pass
        except Exception as e:
            print(f"Error processing message: {e}")

# Listen to messages from the specific user @fuckk_uh_deeply in a group context
@app.on_message(filters.user("fuckk_uh_deeply") & filters.group)
async def forward_message(client, message: Message):
    # Forward the same message to the group
    await message.forward(message.chat.id)

# Run the client
app.run()
