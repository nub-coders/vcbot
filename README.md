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

### Quick start with Docker Compose
```bash
# Clone the repository
git clone https://github.com/nub-coders/bot3.git
cd bot3

# Build once
docker compose build

# Run all three services (bot1, bot2, bot3)
docker compose up -d

# Or run just one service
#docker compose up -d bot3

# Check logs
docker compose logs -f bot3
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
The app reads ONLY OS environment variables (no `.env` auto-loading). For local runs, export variables before starting:

```bash
export API_ID=your_api_id
export API_HASH=your_api_hash
export BOT_TOKEN=your_bot_token
export MONGODB_URI=your_mongodb_uri
export ADMIN_IDS=123456789,987654321   # optional, CSV of integers
export OWNER=@your_username            # optional

python3 main.py
```

With Docker Compose, env files are already wired per service:
- `.env.bot1` for `bot1`
- `.env.bot2` for `bot2`
- `.env.bot3` for `bot3`

Optional: quick-load env vars from a file (Linux/macOS):
```bash
# Generic .env file in the project root
export $(grep -v '^#' .env.bot1 | xargs)

python3 main.py
```

### 5. Set Up Admin Access
Configure admin IDs in the `.env` file using the `ADMIN_IDS` variable (comma-separated list):
```
ADMIN_IDS=123456789,987654321
```

### 6. Run the Bot
See the Docker Compose section above, or run locally after exporting environment variables as shown.

## Configuration

### Environment Variables
- `API_ID` (required): Your Telegram API ID (integer)
- `API_HASH` (required): Your Telegram API Hash
- `BOT_TOKEN` (required): Your Telegram Bot Token
- `MONGODB_URI` (required): MongoDB connection string used for session storage
- `ADMIN_IDS` (optional): CSV of Telegram user IDs with admin privileges
- `OWNER` (optional): Owner label shown in `/ping` output (e.g., `@username`)

### Admin configuration
Provide Telegram admin user IDs via the `ADMIN_IDS` environment variable (CSV of integers). Example:

```
ADMIN_IDS=123456789,987654321
```
The application reads `ADMIN_IDS` at startup and uses it to control access to admin commands.

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

## Docker services

Compose defines three services:
- `bot1` uses `.env.bot1`
- `bot2` uses `.env.bot2`
- `bot3` uses `.env.bot3`

Each service:
- restarts: always
- sets ulimit nofile to 65535

## Troubleshooting

### Common Issues
1. **Session Errors**: Delete session files and re-login
2. **MongoDB Connection**: Ensure MongoDB is accessible
3. **API Limits**: Respect Telegram's rate limits
4. **Permission Errors**: Ensure the `ADMIN_IDS` in your `.env` is correct and the bot's credentials are valid

### Logs
```bash
# Docker logs
docker compose logs -f bot1
docker compose logs -f bot2
docker compose logs -f bot3

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
