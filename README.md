# Bot3 - Telegram Bot

A powerful Telegram bot with voice chat capabilities, voting features, and multi-client management.

## Repository
- **GitHub**: [github.com/nub-coders/bot3](https://github.com/nub-coders/bot3)

## Features
- Multi-client Telegram session management
- Voice chat joining/leaving capabilities
- Poll voting (regular and button polls)
- View count incrementing
- Group joining/leaving
- User reporting functionality
- Admin controls and monitoring
- MongoDB session storage

## Prerequisites
- Python 3.8+
- MongoDB database
- Telegram API credentials (API_ID, API_HASH, BOT_TOKEN)

## Docker Setup (Recommended)

### Build and Run with Docker
```bash
# Clone the repository
git clone https://github.com/nub-coders/bot3.git
cd bot3

# Build the Docker image
docker build -t bot3 .

# Run the container with specified resources
docker run -d  --name bot1   --cpus="50"   --memory="50g" --ulimit nofile=65535:65535  --restart=always  bot3
```

## Setup Without Docker

### 1. Clone the Repository
```bash
git clone https://github.com/nub-coders/bot3.git
cd bot3
```

### 2. Install System Dependencies
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3 python3-pip git curl wget ffmpeg

# CentOS/RHEL
sudo yum install -y python3 python3-pip git curl wget ffmpeg
```

### 3. Install Python Dependencies
```bash
pip3 install -r requirements.txt
```

### 4. Configure Environment
The bot reads credentials from environment variables or a local `.env` file (recommended for local development). Create a `.env` file in the project root with the following variables:

```
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
ADMIN_IDS=123456789,987654321
```

Do not commit your `.env` to the repository. Use `.env.example` (not containing real secrets) to document required variables if you want to publish example config.

### 5. Set Up Admin Access
Configure admin IDs in the `.env` file using the `ADMIN_IDS` variable (comma-separated list):
```
ADMIN_IDS=123456789,987654321
```

### 6. Run the Bot
```bash
python3 main.py
```

## Configuration

### Environment Variables
- `API_ID`: Your Telegram API ID
- `API_HASH`: Your Telegram API Hash
- `BOT_TOKEN`: Your Telegram Bot Token

### Admin configuration
Provide Telegram admin user IDs via the `ADMIN_IDS` environment variable in `.env` (CSV of integers). Example:

```
ADMIN_IDS=123456789,987654321
```
Your application reads `ADMIN_IDS` at startup and uses it to control access to admin commands.

## Available Commands

### User Commands
- `/start` - Show available commands
- `/login` - Log in to the bot
- `/logout` - Log out from the bot
- `/ping` - Check bot status and system stats

### Admin Commands
- `/activers` - Show active clients
- `/vote <index> <num_clients> <message_id> <join_url> <delay>` - Vote on polls
- `/bvote <index> <num_clients> <message_id> <join_url> <delay>` - Vote on button polls
- `/join <num_clients> <group_url>` - Join groups/channels
- `/left <num_clients> <group_url>` - Leave groups/channels
- `/vc <num_clients> <group_url>` - Join voice chats
- `/leave <num_clients> <group_url>` - Leave voice chats
- `/bview <num_clients> <group_url>` - Increment view counts
- `/react <num_clients> <channel> <message_id> <emoji>` - React to messages
- `/report <num_clients> <user_id>` - Report users
- `/reboot` - Restart the bot
- `/pull` - Update from git repository

## Docker Resource Limits

The Docker setup is configured with:
- **CPU**: 50 vCPUs
- **Memory**: 50GB RAM
- **Restart Policy**: Always
- **Container Name**: bot1

## Troubleshooting

### Common Issues
1. **Session Errors**: Delete session files and re-login
2. **MongoDB Connection**: Ensure MongoDB is accessible
3. **API Limits**: Respect Telegram's rate limits
4. **Permission Errors**: Ensure the `ADMIN_IDS` in your `.env` is correct and the bot's credentials are valid

### Logs
```bash
# Docker logs
docker logs bot1

# System logs (without Docker)
tail -f /var/log/syslog
```

## Security Notes
- Keep your API credentials secure
- Use environment variables for sensitive data
- Regularly update dependencies
- Monitor bot usage and logs

## License
This project is for educational purposes. Use responsibly and in accordance with Telegram's Terms of Service.

## Support
For issues and questions, please open an issue on the GitHub repository.
