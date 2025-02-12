from config import *
# Dictionary to store welcome messages for each user
welcome_messages = {}

@bot.on(events.NewMessage(
    incoming=True,
    outgoing=False,
    func=lambda x: x.is_private,
    pattern='/setwelkm'
))
async def set_handler(event):
    try:
        user_id = event.sender_id

        # Check if the command is a reply
        if not event.reply_to_msg_id:
            return await event.reply(
                "Please reply to a text message to set it as your welcome message.\n"
                "Available placeholders:\n"
                "{name} - User's first name\n"
                "{id} - Chat ID\n"
                "{botname} - Bot's first name\n\n"
                "Supported HTML tags:\n"
                "<b>: Bold text\n"
                "<i>: Italic text\n"
                "<u>: Underlined text\n"
                "<code>: Inline code\n"
                "<pre>: Code block\n"
                "<pre language=\"python\">: Python code block\n"
                "<blockquote>: Quoted text"
            )

        # Get the replied message
        replied_msg = await event.get_reply_message()

        # Ensure the replied message contains text
        if not replied_msg.text:
            return await event.reply("The replied message must contain text. Media files are not supported.")

        # Extract the welcome message
        welcome_text = replied_msg.text.strip()

        # Validate message length
        if len(welcome_text) > 4096:
            return await event.reply("The welcome message is too long. Maximum length is 4096 characters.")

        # Define allowed placeholders
        allowed_placeholders = ["{name}", "{id}", "{botname}"]
        placeholders = re.findall(r'\{([^}]+)\}', welcome_text)

        # Identify unauthorized placeholders
        unauthorized_placeholders = [
            f"{{{placeholder}}}" for placeholder in placeholders
            if f"{{{placeholder}}}" not in allowed_placeholders
        ]
        if unauthorized_placeholders:
            return await event.reply(
                f"⚠️ Found unauthorized placeholders: {', '.join(unauthorized_placeholders)}\n\n"
                "Only these placeholders are allowed:\n"
                "{name} - User's first name\n"
                "{id} - Chat ID\n"
                "{botname} - Bot's first name"
            )

        # Validate HTML formatting
        def validate_html_formatting(text):
            allowed_tags = {"b", "i", "u", "code", "pre", "blockquote"}
            opening_tags = re.findall(r'<(b|i|u|code|pre|blockquote)(?: language="python")?>', text)
            closing_tags = re.findall(r'</(b|i|u|code|pre|blockquote)>', text)
            if opening_tags != closing_tags:
                return f"Unmatched HTML tags detected: {set(opening_tags) ^ set(closing_tags)}"
            return None

        html_error = validate_html_formatting(welcome_text)
        if html_error:
            return await event.reply(f"❌ HTML validation error:\n{html_error}")

        # Save the welcome message in the global dictionary
        welcome_messages[user_id] = welcome_text

        # Construct preview message
        test_msg = welcome_text.format(
            name="Test User",
            id="123456789",
            botname="TestBot"
        )
        preview = (
            f"✅ Welcome message set successfully!\n\n"
            f"Preview with sample values:\n"
            f"{'─' * 30}\n"
            f"{test_msg}\n"
            f"{'─' * 30}\n\n"
            f"Used placeholders: {', '.join(placeholders) if placeholders else 'None'}"
        )

        await event.reply(preview, parse_mode='html')

    except KeyError as e:
        await event.reply(
            f"Error in formatting! Please check your placeholders.\n"
            f"Error details: Missing placeholder {str(e)}"
        )
    except Exception as e:
        logging.error(f"Error setting welcome message for user {user_id}: {e}")
        await event.reply(f"❌ Error in setting welcome message:\n`{str(e)}`")


@app.on_message(filters.command("testwelcome"))
async def test_welcome(client, message):
    """Test the welcome message using Pyrogram client"""
    try:
        user_id = message.from_user.id
        welcome_text = welcome_messages.get(user_id)

        if not welcome_text:
            return await message.reply_text(
                "No welcome message set. Reply to a message with /setwelkm to set one."
            )

        # Replace placeholders with dynamic values
        test_msg = welcome_text.format(
            name=message.from_user.first_name or "User",
            id=message.chat.id,
            botname=client.me.first_name
        )

        # Send the test message
        await message.reply_text(test_msg)

    except KeyError as e:
        error_msg = f"Error in formatting placeholders: Missing placeholder {str(e)}"
        logging.error(error_msg)
        await message.reply_text(error_msg)
    except Exception as e:
        error_msg = f"Error testing welcome message: {str(e)}"
        logging.error(error_msg)
        await message.reply_text(error_msg)
app.run()

