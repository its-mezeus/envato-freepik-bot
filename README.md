# 🎨 Envato & Freepik Downloader Manager Bot

A Telegram bot that manages Envato & Freepik download requests in groups with daily slot limits, force join verification, and VIP system.

## Features

- 🔒 **Force Join** — Users must join all required channels before sending links
- 🎫 **Daily Slots** — Configurable daily limit (default: 4)
- 👑 **VIP System** — Unlimited access for selected users
- 🔇 **Auto Mute** — Users muted after using all slots, auto-unmute at midnight IST
- 📬 **Admin Alerts** — Admins get DM alerts for every download request
- ✅ **Continuous Verification** — Re-checks channel membership on every request

## Setup

1. Create a bot via [@BotFather](https://t.me/BotFather)
2. Set environment variables:

```bash
export BOT_TOKEN="your-bot-token"
export ADMIN_IDS="admin_id_1,admin_id_2"
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run:
```bash
python3 bot.py
```

5. Add bot to your group as **admin** (needs delete messages + restrict members)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | Yes | Telegram bot token |
| `ADMIN_IDS` | Yes | Comma-separated admin user IDs |
| `DAILY_LIMIT` | No | Max links per user per day (default: 4) |
| `MODE` | No | `webhook` (default) or `polling` |
| `WEBHOOK_URL` | For webhook | Your Render app URL (e.g. `https://envato-freepik-bot.onrender.com`) |
| `PORT` | No | Port for Flask server (default: 10000) |

## Deploy on Render (Free Tier — 24/7)

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → **New+** → **Web Service**
3. Connect your GitHub repo
4. Configure:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python3 bot.py`
5. Add environment variables:
   - `BOT_TOKEN` = your bot token
   - `ADMIN_IDS` = admin IDs (comma-separated)
   - `WEBHOOK_URL` = `https://your-app-name.onrender.com`
   - `MODE` = `webhook`
6. Deploy!

## Run Locally (Polling)

```bash
export BOT_TOKEN="your-token"
export ADMIN_IDS="id1,id2"
export MODE="polling"
python3 bot.py
```

## Commands

### User Commands (group only)
| Command | Description |
|---------|-------------|
| `/start` | Start & verify (DM only) |
| `/info` | Your info & VIP status |
| `/slots` | Check remaining slots |
| `/help` | How to use |

### Admin Commands
| Command | Description |
|---------|-------------|
| `/stats` | Bot statistics |
| `/setlimit N` | Change daily limit |
| `/resetuser ID` | Reset user slots & unmute |
| `/addvip ID` | Give unlimited access |
| `/removevip ID` | Remove VIP |
| `/viplist` | Show all VIP users |

## Force Join Channels

Edit the `FORCE_CHANNELS` list in `bot.py` to set your required channels.

## How It Works

1. User sends Envato/Freepik link in group
2. Bot checks if user joined all channels
3. If not verified → message deleted, user directed to bot DM
4. If verified → slot used, admin alerted with link details
5. After all slots used → user muted until midnight IST
6. Slots reset at 12:00 AM IST daily
