import os

# ==== Greenville Roleplay Bot Defaults ====
# Recommended: set BOT_TOKEN (or DISCORD_TOKEN) as an environment variable or in a .env file.
TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("DISCORD_TOKEN") or ""

# Optional: set a specific guild ID only for instant dev slash-command testing (0 = sync globally for all servers)
GUILD_ID = int(os.environ.get("GUILD_ID", "0") or 0)

# Default command prefix for servers that haven't customized theirs via /config prefix
PREFIX = os.environ.get("DEFAULT_PREFIX", "-")

# SQLite database path for per-server configuration and persistent session links
DATABASE_PATH = os.environ.get("DATABASE_PATH", "data/bot.db")

# Default emojis used by the /startup command
EMOJI_LIST = ["🔥", "❌", "👀", "🗿", "✅", "💀"]