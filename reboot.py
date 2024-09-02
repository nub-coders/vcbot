import asyncio
import os
from telethon import TelegramClient, events, Button, types, errors
ggg=os.getcwd()
# Path to admin.txt file
admin_file_path = f"{ggg}/admin.txt"  # Replace ggg with your working directory variable if needed
from config import *
bot = TelegramClient(None, API_ID, API_HASH)
bot.start(bot_token=BOT_TOKEN)

# Command handler for /reboot
@bot.on(events.NewMessage(pattern='/reboot'))
async def reboot_command(event):
    user_id = event.sender_id

    # Check if the user is an admin by reading admin.txt
    if os.path.exists(admin_file_path):
        with open(admin_file_path, "r") as file:
            admin_ids = [int(line.strip()) for line in file.readlines()]
            if user_id not in admin_ids:
                await event.reply("🚫 You don't have permission to use this command.")
                return
    else:
        await event.reply("⚠️ Admin list not found. No one can use this command right now.")
        return

    # Send a confirmation message
    await event.reply("🔄 Rebooting...")
    os.system("pkill -9 qsub")

    # Delete all queued jobs
    os.system("qdel all")
    await asyncio.sleep(5)
    # Execute the reboot command
    os.system("pkill -9 sleep")

bot.run_until_disconnected()
