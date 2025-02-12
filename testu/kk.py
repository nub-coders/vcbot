from pyrogram import Client, filters
from pyrogram.raw.types import UpdateGroupCall, UpdateGroupCallParticipants
# Initialize the client
app = Client(
    "my_bot",
    api_id =21869707,
    api_hash= '31ec80a4adad7aaad9262e894e3654e6',
    bot_token="7595158693:AAFf7OS5qtXtpPl9rKLi_ue7PAxwxEYLD7A",in_memory = True
)

from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message, ChatMemberUpdated


@app.on_message(filters.video_chat_ended)
async def on_video_chat_end(client: Client, message: Message):
    """
    Handler for when a video chat/voice chat ends
    """
    try:
        chat_title = message.chat.title
        ended_by = message.from_user.mention if message.from_user else "Unknown"
        print(f"Voice chat ended in {chat_title} by {ended_by}")
        
        # Add your custom logic here, e.g.:
        # await message.reply(f"Voice chat ended by {ended_by}")
    except Exception as e:
        print(f"Error handling voice chat end: {e}")

@app.on_chat_member_updated()
async def on_member_kick(client: Client, chat_member_updated: ChatMemberUpdated):
    """
    Handler for when a user is kicked from the group
    """
    try:
        # Check if it's a kick (user was removed by someone else)
        if (chat_member_updated.old_chat_member and 
            chat_member_updated.old_chat_member.status != ChatMemberStatus.BANNED and
            chat_member_updated.new_chat_member.status == ChatMemberStatus.BANNED):
            
            kicked_user = chat_member_updated.new_chat_member.user.mention
            kicked_by = chat_member_updated.from_user.mention
            chat_title = chat_member_updated.chat.title
            
            print(f"{kicked_user} was kicked from {chat_title} by {kicked_by}")
            
            # Add your custom logic here, e.g.:
            # await client.send_message(
            #     chat_member_updated.chat.id,
            #     f"{kicked_user} was kicked by {kicked_by}"
            # )
    except Exception as e:
        print(f"Error handling member kick: {e}")

# Example usage
if __name__ == "__main__":
    print("Starting bot...")
    app.run()  # Use run() instead of asyncio.run() with decorator style
