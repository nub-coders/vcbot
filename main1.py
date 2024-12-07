import os
import json
import random
import logging
from urllib.parse import urlparse, parse_qs
from telethon import TelegramClient
from telethon.tl.functions.messages import RequestWebViewRequest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fake_useragent import UserAgent
import time

# Configure logging for clean output
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress Telethon's low-level logs
logging.getLogger("telethon").setLevel(logging.WARNING)

# Telegram API credentials
API_ID = 286xxxxx
API_HASH = '3edc6827bxxxxxxx''

# Path to the session folder and links file
SESSION_FOLDER = "session"
LINKS_FILE = 'web_view_links.txt'

# Ensure the session folder exists
if not os.path.exists(SESSION_FOLDER):
    os.makedirs(SESSION_FOLDER)

# Ensure the links file exists by creating it if it doesn't exist
if not os.path.exists(LINKS_FILE):
    with open(LINKS_FILE, 'w') as f:
        pass

# Load device configurations from devices.json
with open('devices.json', 'r') as file:
    devices = json.load(file)

def get_random_device():
    """Select a random device model and its SDK version."""
    device_model = random.choice(list(devices.keys()))
    sdk_version = devices[device_model]
    return device_model, sdk_version

async def create_client(session_file):
    """Create a TelegramClient with random user agent and device parameters."""
    ua = UserAgent()  # Instantiate UserAgent to get random user agents
    user_agent = ua.random

    # Get random device information
    device_model, system_version = get_random_device()

    # Log the selected user agent and device information
    logging.info(f"Using User-Agent: {user_agent}")
    logging.info(f"Using device {device_model} with SDK {system_version} for session {session_file}")

    # Create and return the client
    client = TelegramClient(
        os.path.join(SESSION_FOLDER, session_file),
        API_ID,
        API_HASH,
        device_model=device_model,
        system_version=system_version,
        app_version='11.4.2',  # Adjust version as needed
        lang_code='en',  # Language code (optional)
        system_lang_code='en',  # System language code (optional)
    )

    # Attach the random user agent to the headers (if needed)
    client.session.user_agent = user_agent

    return client

def parse_referral_link():
    """
    Hardcoded referral link to extract the bot username and startapp parameter.
    """
    link = "https://t.me/PAWSOG_bot/PAWS?startapp=RPAlcSo4"
    parsed_url = urlparse(link)
    path_parts = parsed_url.path.split('/')
    bot_username = path_parts[1] if len(path_parts) > 1 else None
    query_params = parse_qs(parsed_url.query)
    startapp_param = query_params.get("startapp", [None])[0]
    
    return bot_username, startapp_param

def setup_android_webdriver():
    """Set up Selenium WebDriver for Android using ADB."""
    os.system("adb devices")  # Ensure the device is connected
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_experimental_option("androidPackage", "org.chromium.chrome.stable")
    driver = webdriver.Chrome(options=options)
    return driver

def move_session_file(session_file, result):
    if result:
        destination_folder = 'succeeded'
    else:
        destination_folder = 'failed'

    # Create the destination folder if it doesn't exist
    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)

    # Move the session file to the appropriate folder
    os.rename(os.path.join(SESSION_FOLDER, session_file), os.path.join(destination_folder, session_file))

async def start_session_and_open_mini_app(session_file, bot_username, startapp_param):
    """
    Start a Telegram client session and interact with the bot to open the mini app.
    """
    client = await create_client(session_file)
    await client.connect()

    # Check if the session is authorized
    if not await client.is_user_authorized():
        logger.warning(f"⚠️ Session '{session_file}' is not authorized. Skipping...")
        await client.disconnect()
        move_session_file(session_file, False)
        return False

    logger.info(f"✨ Processing session: {session_file}")
    
    try:
        # Get InputUser for the bot
        bot_entity = await client.get_input_entity(bot_username)
        
        # Use RequestWebViewRequest to get the web view link
        result = await client(RequestWebViewRequest(
            peer=bot_entity,
            bot=bot_entity,
            platform="android",
            from_bot_menu=False,
            url=f"https://t.me/{bot_username}/PAWS?startapp={startapp_param}"
        ))

        # Print and save the full web view link
        web_view_link = result.url
        logger.info(f"🔗 Web view link: {web_view_link}")

        # Save the link to a text file
        with open(LINKS_FILE, 'a') as f:
            f.write(web_view_link + '\n')

        # Open the link using Selenium with Android WebDriver
        driver = setup_android_webdriver()
        driver.get(web_view_link)

        time.sleep(5)

        # Wait for the button with class name 'btn-next' and click it using JavaScript to avoid interception issues
        btn_next = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "btn-next"))
        )
        driver.execute_script("arguments[0].click();", btn_next)

        time.sleep(3)

        # Close the browser after actions are completed (optional)
        driver.quit()

        await client.disconnect()
        
        move_session_file(session_file, True)
        
        logger.info(f"🔌 Disconnected session: {session_file}")
        
        return True
    
    except Exception as e:
        
        logger.error(f"❌ Failed to interact with @{bot_username} using session '{session_file}': {e}")
        
        await client.disconnect()
        
        move_session_file(session_file, False)
        
        logger.info(f"🔌 Disconnected session: {session_file}")
        
        return False

async def main():
    
   """
   Main function to handle all sessions and send commands.
   """
   
   # Use hardcoded referral link details
   
   bot_username, startapp_param = parse_referral_link()
   
   if not bot_username:
       
       logger.error("❌ Invalid referral link. Exiting...")
       
       return

   logger.info(f"\n🔗 Referral link parsed successfully: Bot Username: @{bot_username}, StartApp Param: {startapp_param}")

   # Get all session files in the folder
   
   session_files = [f for f in os.listdir(SESSION_FOLDER) if f.endswith('.session')]

   success_count = 0
   
   failure_count = 0

   # Process each session file
   
   for session_file in session_files:
       
       result = await start_session_and_open_mini_app(session_file, bot_username, startapp_param)
       
       # Update success or failure count and print progress after each session
      
       if result:
           
           success_count += 1
        
           logger.info(f"🎉 Success! Total so far: ✅ {success_count} | ❌ {failure_count}")
       
       else:
           
           failure_count += 1
        
           logger.info(f"⚠️ Failed! Total so far: ✅ {success_count} | ❌ {failure_count}")
       
       # Add a gap between each session log for better readability
      
       print("\n" + "-" * 50 + "\n")

   # Print final summary of results
   
   logger.info(f"🏁 Task completed!\n✅ Successful tasks: {success_count}\n❌ Failed tasks: {failure_count}")

# Run the script

if __name__ == "__main__":
    
   import asyncio
   
   asyncio.run(main())
