# Greenville Roleplay Bot

A multi-server Discord bot for **Greenville Roleplay (GVRP)** communities. Every server can invite the bot and configure its own rules channel, announcement channel, staff/host roles, Early Access & Booster roles, pings, reaction goals, and command prefix directly inside Discord.

## Features

- **Multi-Server Ready**: Per-server configuration stored in SQLite (`data/bot.db`) — no hardcoded channel IDs, role IDs, or server IDs.
- **Interactive Setup Wizard (`/config wizard`)**: Configure channels, roles, pings, and prefix using Discord dropdowns and modals.
- **Hybrid Commands**: Every command works as both a **slash command** (`/startup`) and a **prefix command** (`-startup`, customizable per server).
- **Persistent Session Buttons**: Early Access and Session Release join buttons remain functional even if the bot restarts, and Early Access links are gated to each server's configured Early Access, Booster, and Staff roles.
- **Auto-Detected Boosters**: Automatically recognizes Discord's native Server Booster role on every server (or a custom Booster role if configured).

## Server Setup (For Server Owners & Admins)

1. **Invite the bot** using an OAuth2 URL with scopes **`bot`** and **`applications.commands`** (or run `/invite` in any server where the bot is already present).
2. Grant the bot these permissions:
   - `View Channels`
   - `Send Messages`
   - `Embed Links`
   - `Manage Messages` (for `/purge` and cleaning up prefix triggers)
   - `Read Message History`
   - `Add Reactions`
   - `Mention @everyone, @here, and All Roles`
3. Run **`/config wizard`** in your server to pick your:
   - Rules channel
   - Session announcement channel (optional — defaults to whichever channel the command is run in)
   - Staff / Host roles
   - Early Access & Booster roles
   - Ping preferences (`@everyone`, `@here`, a role, or none)
   - Custom command prefix & default reaction goal

> Even without running `/config`, the bot works out of the box for members with `Manage Messages` / `Administrator` (or standard `Staff Team` / `Early Access` / `Server Booster` roles).

## Commands

| Command | Description | Who Can Use |
| --- | --- | --- |
| `/startup [reactions]` | Announce a session startup with rules link and reaction emoji | Staff / Host |
| `/setup` | Announce that the host is setting up the session | Staff / Host |
| `/ea <link>` | Post an Early Access embed with a role-gated join button | Staff / Host |
| `/release <peacetime> <frp_speeds> <link>` | Release the session with Peacetime, FRP speeds, and join button | Staff / Host |
| `/over` | Announce that the session has ended | Staff / Host |
| `/purge <amount>` | Bulk delete 1–100 recent non-pinned messages (< 14 days old) | Staff / Host |
| `/config wizard` | Interactive server setup panel | Admin / Manage Server |
| `/config view` | View current server configuration | Admin / Manage Server |
| `/config rules`, `session_channel`, `prefix`, `reactions`, `add_staff_role`, `add_ea_role`, `booster_role`, `startup_ping`, `release_ping`, `reset` | Configure individual server settings | Admin / Manage Server |
| `/help` | Show command list | Everyone |
| `/invite` | Get the OAuth2 invite link for your own server | Everyone |
| `/ping` | Check bot latency and server count | Everyone |

## Self-Hosting

### 1. Discord Developer Portal Setup
1. Create an application in the [Discord Developer Portal](https://discord.com/developers/applications) and add a Bot.
2. Under **Bot -> Privileged Gateway Intents**, enable:
   - **Server Members Intent**
   - **Message Content Intent**
3. Under **OAuth2 -> URL Generator**, select `bot` and `applications.commands` scopes, choose the permissions listed above, and invite the bot to your server(s).

### 2. Run Locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set BOT_TOKEN=...
python bot.py
```

### 3. Deploy on Render
This repository includes `render.yaml` and `Procfile`. Connect your repo on Render, set the `BOT_TOKEN` environment variable, and deploy. (If deployed as a Web Service with a `PORT` environment variable, the bot also serves a `200 OK` HTTP healthcheck.)