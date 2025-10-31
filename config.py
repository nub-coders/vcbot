from pathlib import Path
import os

# Load environment variables from .env (if present)
try:
	from dotenv import load_dotenv
except Exception:
	# dotenv may not be installed yet; environment variables may still be provided by the runtime
	load_dotenv = None

dotenv_path = Path(__file__).parent / '.env'
if load_dotenv:
	load_dotenv(dotenv_path=dotenv_path)

# Read required configuration from environment
_api_id = os.getenv('API_ID')
API_ID = int(_api_id) if _api_id is not None else None
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')

if not API_ID or not API_HASH or not BOT_TOKEN:
	raise RuntimeError(
		'Missing required environment variables. Please create a .env file with API_ID, API_HASH and BOT_TOKEN'
	)

# Optional: ADMIN_IDS can be provided as a comma-separated list of user IDs
_admin_ids = os.getenv('ADMIN_IDS', '')
if _admin_ids:
	try:
		ADMIN_IDS = [int(x.strip()) for x in _admin_ids.split(',') if x.strip()]
	except Exception:
		raise RuntimeError('ADMIN_IDS must be a comma-separated list of integers')
else:
	ADMIN_IDS = []

