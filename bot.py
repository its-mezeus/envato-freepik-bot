#!/usr/bin/env python3
"""
Envato & Freepik Downloader Manager Bot
Manages link requests in groups with daily slot limits + force join.
"""

import os, re, json, asyncio, logging, threading
from datetime import datetime, timedelta
from flask import Flask, request as flask_request
from telegram import Update, BotCommand, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]
DAILY_LIMIT = int(os.environ.get("DAILY_LIMIT", "4"))
# Auto-detect Render URL or use manual override
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "")  # Render sets this automatically
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "") or RENDER_EXTERNAL_URL
PORT = int(os.environ.get("PORT", "10000"))
MODE = os.environ.get("MODE", "webhook")  # "webhook" for Render, "polling" for local
TZ_OFFSET = 5.5

FORCE_CHANNELS = [
    {"username": "chatgaragee", "name": "Chat Garage"},
    {"username": "freepikenvatopremiumfree", "name": "Freepik Envato Premium"},
    {"username": "canvaprofree4everyone", "name": "Canva Pro Free"},
    {"username": "animationgarage", "name": "Animation Garage"},
    {"username": "techiesgarageofficial", "name": "Techies Garage"},
    {"username": "garagecornerhub", "name": "Garage Corner Hub"},
]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")

def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {"users": {}, "verified": [], "settings": {"daily_limit": DAILY_LIMIT}}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_today():
    return (datetime.utcnow() + timedelta(hours=TZ_OFFSET)).strftime("%Y-%m-%d")

def get_user_slots(data, uid):
    key = str(uid)
    today = get_today()
    limit = data.get("settings", {}).get("daily_limit", DAILY_LIMIT)
    if key not in data["users"]:
        data["users"][key] = {"date": today, "count": 0, "muted": False}
    u = data["users"][key]
    if u["date"] != today:
        u["date"] = today
        u["count"] = 0
        u["muted"] = False
    return max(0, limit - u["count"])

def use_slot(data, uid):
    key = str(uid)
    today = get_today()
    limit = data.get("settings", {}).get("daily_limit", DAILY_LIMIT)
    if key not in data["users"]:
        data["users"][key] = {"date": today, "count": 0, "muted": False}
    u = data["users"][key]
    if u["date"] != today:
        u["date"] = today
        u["count"] = 0
        u["muted"] = False
    u["count"] += 1
    save_data(data)
    return max(0, limit - u["count"])

async def check_force_join(bot, uid):
    not_joined = []
    for ch in FORCE_CHANNELS:
        try:
            m = await bot.get_chat_member(f"@{ch['username']}", uid)
            if m.status in ["left", "kicked"]:
                not_joined.append(ch)
        except:
            not_joined.append(ch)
    return not_joined

def force_join_kb(not_joined):
    btns = []
    for ch in not_joined:
        btns.append([InlineKeyboardButton(f"📢 Join {ch['name']}", url=f"https://t.me/{ch['username']}")])
    btns.append([InlineKeyboardButton("✅ I've Joined All", callback_data="verify_join")])
    return InlineKeyboardMarkup(btns)

ENVATO_RE = re.compile(r'https?://(www\.)?(elements\.envato\.com|envato\.com|themeforest\.net|codecanyon\.net|videohive\.net|audiojungle\.net|graphicriver\.net|photodune\.net|3docean\.net)/\S+', re.I)
FREEPIK_RE = re.compile(r'https?://(www\.)?(freepik\.com|flaticon\.com)/\S+', re.I)

def detect_links(text):
    links = []
    for m in re.finditer(ENVATO_RE, text):
        links.append({"url": m.group(), "type": "Envato"})
    for m in re.finditer(FREEPIK_RE, text):
        links.append({"url": m.group(), "type": "Freepik"})
    return links

# ─── Handlers ─────────────────────────────────────────────────────────

async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    user = update.effective_user
    # Admins skip force join
    if user.id in ADMIN_IDS:
        data = load_data()
        if user.id not in data.get("verified", []):
            data.setdefault("verified", []).append(user.id)
            save_data(data)
        limit = data.get("settings", {}).get("daily_limit", DAILY_LIMIT)
        vip_count = len(data.get("vip", []))
        verified_count = len(data.get("verified", []))
        await update.message.reply_text(
            f"🎨 <b>Envato & Freepik Downloader Manager</b>\n\n"
            f"Hey <b>{user.first_name}</b>! 👑 Admin access!\n\n"
            f"<b>📊 Stats:</b>\n"
            f"/stats - Bot statistics\n\n"
            f"<b>🎫 Slot Management:</b>\n"
            f"/setlimit N - Change daily limit (current: {limit})\n"
            f"/resetuser ID - Reset user slots & unmute\n\n"
            f"<b>👑 VIP Management:</b>\n"
            f"/addvip ID - Give unlimited access\n"
            f"/removevip ID - Remove VIP\n"
            f"/viplist - Show all VIPs ({vip_count})\n\n"
            f"<b>ℹ️ User Commands (group only):</b>\n"
            f"/info - User info & slots\n"
            f"/slots - Check remaining slots\n"
            f"/help - How to use\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Verified: {verified_count} | 👑 VIPs: {vip_count}\n"
            f"⚡ <i>You have unlimited access</i>", parse_mode="HTML"
        )
        return
    not_joined = await check_force_join(ctx.bot, user.id)
    if not_joined:
        await update.message.reply_text(
            f"🔒 <b>VERIFICATION REQUIRED!</b>\n\n"
            f"Hey <b>{user.first_name}</b>! 👋\n\n"
            f"To use this bot, you must join all our channels first:\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📢 <b>{len(not_joined)} channel(s)</b> remaining\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👇 Join all channels below, then click <b>'I've Joined All'</b>",
            reply_markup=force_join_kb(not_joined), parse_mode="HTML"
        )
        return
    data = load_data()
    if user.id not in data.get("verified", []):
        data.setdefault("verified", []).append(user.id)
        save_data(data)
    limit = data.get("settings", {}).get("daily_limit", DAILY_LIMIT)
    await update.message.reply_text(
        f"🎨 <b>Envato & Freepik Downloader Manager</b>\n\n"
        f"Hey <b>{user.first_name}</b>! ✅ You're verified!\n\n"
        f"<b>How it works:</b>\n"
        f"📩 Send Envato/Freepik links in the group\n"
        f"🎫 You get <b>{limit} slots per day</b>\n"
        f"⏰ Slots reset at <b>12:00 AM IST</b>\n"
        f"🔇 After using all slots, you'll be muted until next day\n\n"
        f"<b>Commands:</b>\n"
        f"/slots - Check remaining slots\n"
        f"/help - Show this message\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <i>You can now send links in the group!</i>", parse_mode="HTML"
    )

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text("ℹ️ Use bot commands in the group, not here.", parse_mode="HTML")
        return
    await update.message.reply_text(
        f"🎨 <b>How to use:</b>\n\n"
        f"📩 Send Envato/Freepik links in this group\n"
        f"🎫 You get <b>{DAILY_LIMIT} slots per day</b>\n"
        f"⏰ Slots reset at <b>12:00 AM IST</b>\n\n"
        f"/slots - Check remaining slots", parse_mode="HTML"
    )

async def verify_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    not_joined = await check_force_join(ctx.bot, user.id)
    if not_joined:
        await query.answer(f"❌ You haven't joined {len(not_joined)} channel(s) yet!", show_alert=True)
        try:
            await query.message.edit_text(
                f"🔒 <b>VERIFICATION REQUIRED!</b>\n\n"
                f"Hey <b>{user.first_name}</b>! 👋\n\n"
                f"You still need to join:\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📢 <b>{len(not_joined)} channel(s)</b> remaining\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👇 Join all channels below, then click <b>'I've Joined All'</b>",
                reply_markup=force_join_kb(not_joined), parse_mode="HTML"
            )
        except:
            pass
        return
    await query.answer("✅ Verified! You can now use the bot!", show_alert=True)
    data = load_data()
    if user.id not in data.get("verified", []):
        data.setdefault("verified", []).append(user.id)
        save_data(data)
    limit = data.get("settings", {}).get("daily_limit", DAILY_LIMIT)
    await query.message.edit_text(
        f"✅ <b>VERIFIED SUCCESSFULLY!</b>\n\n"
        f"Hey <b>{user.first_name}</b>! 🎉\n\n"
        f"You can now send Envato/Freepik links in the group.\n\n"
        f"🎫 Daily limit: <b>{limit} requests</b>\n"
        f"⏰ Resets at <b>12:00 AM IST</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <i>Go send your links!</i>", parse_mode="HTML"
    )
    for admin_id in ADMIN_IDS:
        try:
            await ctx.bot.send_message(admin_id,
                f"✅ <b>User Verified!</b>\n"
                f"👤 <a href='tg://user?id={user.id}'>{user.first_name}</a>\n"
                f"🆔 <code>{user.id}</code>\n"
                f"🔗 @{user.username if user.username else 'N/A'}",
                parse_mode="HTML")
        except:
            pass

async def slots_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text("ℹ️ Use this command in the group.", parse_mode="HTML")
        return
    user = update.effective_user
    data = load_data()
    remaining = get_user_slots(data, user.id)
    limit = data.get("settings", {}).get("daily_limit", DAILY_LIMIT)
    used = limit - remaining
    await update.message.reply_text(
        f"🎫 <b>Your Slots Today</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 User: {user.first_name}\n"
        f"📊 Used: {used}/{limit}\n"
        f"🎫 Remaining: <b>{remaining}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ Resets at 12:00 AM IST", parse_mode="HTML"
    )

async def info_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text("ℹ️ Use this command in the group.", parse_mode="HTML")
        return
    user = update.effective_user
    data = load_data()
    remaining = get_user_slots(data, user.id)
    limit = data.get("settings", {}).get("daily_limit", DAILY_LIMIT)
    used = limit - remaining
    is_vip = user.id in data.get("vip", [])
    is_verified = user.id in data.get("verified", [])
    text = (
        f"👤 <b>Your Info</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"📛 Name: {user.first_name}\n"
        f"✅ Verified: {'Yes' if is_verified else 'No'}\n"
        f"👑 VIP: {'Yes — Unlimited!' if is_vip else 'No'}\n"
    )
    if not is_vip:
        text += (
            f"📊 Slots Used: {used}/{limit}\n"
            f"🎫 Remaining: <b>{remaining}</b>\n"
        )
    text += (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ Resets at 12:00 AM IST"
    )
    await update.message.reply_text(text, parse_mode="HTML")

async def setlimit_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not ctx.args:
        await update.message.reply_text("❌ Usage: <code>/setlimit 5</code>", parse_mode="HTML")
        return
    try:
        n = int(ctx.args[0])
        assert n >= 1
    except:
        await update.message.reply_text("❌ Invalid number!", parse_mode="HTML")
        return
    data = load_data()
    data["settings"]["daily_limit"] = n
    save_data(data)
    await update.message.reply_text(f"✅ Daily limit set to <b>{n}</b>!", parse_mode="HTML")

async def resetuser_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not ctx.args:
        await update.message.reply_text("❌ Usage: <code>/resetuser user_id</code>", parse_mode="HTML")
        return
    try:
        tid = int(ctx.args[0])
    except:
        await update.message.reply_text("❌ Invalid user ID!", parse_mode="HTML")
        return
    data = load_data()
    key = str(tid)
    if key in data["users"]:
        data["users"][key]["count"] = 0
        data["users"][key]["muted"] = False
        save_data(data)
    try:
        if update.effective_chat.type in ["group", "supergroup"]:
            await ctx.bot.restrict_chat_member(update.effective_chat.id, tid,
                permissions=ChatPermissions(can_send_messages=True, can_send_media_messages=True,
                    can_send_other_messages=True, can_add_web_page_previews=True))
    except:
        pass
    await update.message.reply_text(f"✅ User <code>{tid}</code> reset & unmuted!", parse_mode="HTML")

async def addvip_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not ctx.args:
        await update.message.reply_text("❌ Usage: <code>/addvip user_id</code>", parse_mode="HTML")
        return
    try:
        tid = int(ctx.args[0])
    except:
        await update.message.reply_text("❌ Invalid user ID!", parse_mode="HTML")
        return
    data = load_data()
    vips = data.setdefault("vip", [])
    if tid in vips:
        await update.message.reply_text(f"⚠️ User <code>{tid}</code> is already VIP!", parse_mode="HTML")
        return
    # Ask admin about force join setting for this VIP
    try:
        chat = await ctx.bot.get_chat(tid)
        name = chat.first_name or "Unknown"
        uname = f"@{chat.username}" if chat.username else "N/A"
        user_info = f"<b>{name}</b> ({uname})"
    except:
        user_info = f"<code>{tid}</code>"
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Force Join ON", callback_data=f"vip_fj_on_{tid}")],
        [InlineKeyboardButton("❌ Force Join OFF", callback_data=f"vip_fj_off_{tid}")],
        [InlineKeyboardButton("🚫 Cancel", callback_data=f"vip_cancel_{tid}")]
    ])
    await update.message.reply_text(
        f"👑 <b>Adding VIP User</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 User: {user_info}\n"
        f"🆔 ID: <code>{tid}</code>\n\n"
        f"🔒 <b>Force Join for this VIP?</b>\n\n"
        f"✅ <b>ON</b> — Must join channels (like normal users)\n"
        f"❌ <b>OFF</b> — Skip force join completely",
        reply_markup=kb, parse_mode="HTML"
    )

async def vip_forcejoin_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("❌ Admin only!", show_alert=True)
        return
    
    data_parts = query.data.split("_")
    # vip_fj_on_123 or vip_fj_off_123 or vip_cancel_123
    action = data_parts[1]  # "fj" or "cancel"
    
    if action == "cancel":
        tid = int(data_parts[2])
        await query.message.edit_text(f"🚫 Cancelled adding VIP <code>{tid}</code>", parse_mode="HTML")
        await query.answer("Cancelled")
        return
    
    fj_setting = data_parts[2]  # "on" or "off"
    tid = int(data_parts[3])
    
    data = load_data()
    vips = data.setdefault("vip", [])
    if tid in vips:
        await query.answer("Already VIP!", show_alert=True)
        return
    
    vips.append(tid)
    # Store VIP force join settings
    vip_settings = data.setdefault("vip_settings", {})
    vip_settings[str(tid)] = {"force_join": fj_setting == "on"}
    save_data(data)
    
    fj_text = "✅ ON (must join channels)" if fj_setting == "on" else "❌ OFF (skip force join)"
    
    try:
        chat = await ctx.bot.get_chat(tid)
        name = chat.first_name or "Unknown"
        uname = f"@{chat.username}" if chat.username else "N/A"
        user_info = f"<b>{name}</b> ({uname})"
    except:
        user_info = f"<code>{tid}</code>"
    
    await query.message.edit_text(
        f"👑 <b>VIP Added!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 User: {user_info}\n"
        f"🆔 ID: <code>{tid}</code>\n"
        f"🔒 Force Join: {fj_text}\n"
        f"🎫 Slots: <b>Unlimited</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="HTML"
    )
    await query.answer("✅ VIP added!")

async def removevip_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not ctx.args:
        await update.message.reply_text("❌ Usage: <code>/removevip user_id</code>", parse_mode="HTML")
        return
    try:
        tid = int(ctx.args[0])
    except:
        await update.message.reply_text("❌ Invalid user ID!", parse_mode="HTML")
        return
    data = load_data()
    vips = data.get("vip", [])
    if tid not in vips:
        await update.message.reply_text(f"⚠️ User <code>{tid}</code> is not VIP!", parse_mode="HTML")
        return
    vips.remove(tid)
    save_data(data)
    await update.message.reply_text(f"✅ User <code>{tid}</code> removed from VIP.", parse_mode="HTML")

async def viplist_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    data = load_data()
    vips = data.get("vip", [])
    if not vips:
        await update.message.reply_text("📋 <b>No VIP users</b>", parse_mode="HTML")
        return
    vip_settings = data.get("vip_settings", {})
    text = f"👑 <b>VIP Users ({len(vips)})</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    for i, vid in enumerate(vips, 1):
        fj = vip_settings.get(str(vid), {}).get("force_join", True)
        fj_icon = "🔒" if fj else "🔓"
        try:
            chat = await ctx.bot.get_chat(vid)
            name = chat.first_name or "Unknown"
            uname = f"@{chat.username}" if chat.username else "N/A"
            text += f"{i}. <b>{name}</b> ({uname}) — <code>{vid}</code> {fj_icon}\n"
        except:
            text += f"{i}. <code>{vid}</code> (unknown) {fj_icon}\n"
    text += f"\n🔒 = Force Join ON | 🔓 = Force Join OFF"
    await update.message.reply_text(text, parse_mode="HTML")

async def stats_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    data = load_data()
    today = get_today()
    limit = data.get("settings", {}).get("daily_limit", DAILY_LIMIT)
    total = len(data["users"])
    verified = len(data.get("verified", []))
    active = sum(1 for u in data["users"].values() if u.get("date") == today and u.get("count", 0) > 0)
    muted = sum(1 for u in data["users"].values() if u.get("date") == today and u.get("muted", False))
    reqs = sum(u.get("count", 0) for u in data["users"].values() if u.get("date") == today)
    await update.message.reply_text(
        f"📊 <b>Bot Statistics</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Total Users: {total}\n"
        f"✅ Verified: {verified}\n"
        f"📅 Active Today: {active}\n"
        f"📩 Requests Today: {reqs}\n"
        f"🔇 Muted Today: {muted}\n"
        f"🎫 Daily Limit: {limit}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📆 Date: {today}", parse_mode="HTML"
    )

async def handle_group_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ["group", "supergroup"]:
        return
    if update.effective_user.id in ADMIN_IDS:
        return
    msg = update.message
    if not msg or not msg.text:
        return

    links = detect_links(msg.text)
    if not links:
        return

    user = update.effective_user
    data = load_data()
    bot_me = await ctx.bot.get_me()

    # Check if VIP has force join disabled
    vip_settings = data.get("vip_settings", {})
    vip_fj = vip_settings.get(str(user.id), {}).get("force_join", True)
    skip_fj = user.id in data.get("vip", []) and not vip_fj
    
    # ALWAYS check force join (unless VIP with force join OFF)
    not_joined = [] if skip_fj else await check_force_join(ctx.bot, user.id)
    if not_joined:
        # Remove from verified list if they left channels
        if user.id in data.get("verified", []):
            data["verified"].remove(user.id)
            save_data(data)
        try:
            await msg.delete()
        except:
            pass
        channel_list = ", ".join([ch["name"] for ch in not_joined])
        notify = await update.effective_chat.send_message(
            f"🔒 <b>{user.first_name}</b>, you left some channels!\n\n"
            f"❌ <b>Not joined:</b> {channel_list}\n\n"
            f"👉 Go to @{bot_me.username} and click /start to re-verify.\n\n"
            f"⚠️ You can't send links until you rejoin all channels.\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━",
            parse_mode="HTML"
        )
        # Also alert the user in DM
        try:
            await ctx.bot.send_message(
                user.id,
                f"⚠️ <b>Channel Membership Alert!</b>\n\n"
                f"You left some required channels:\n"
                f"❌ <b>{channel_list}</b>\n\n"
                f"You can't send links in the group until you rejoin.\n"
                f"Click /start to re-verify.",
                parse_mode="HTML"
            )
        except:
            pass
        await asyncio.sleep(20)
        try:
            await notify.delete()
        except:
            pass
        return
    else:
        # Re-add to verified if not in list
        if user.id not in data.get("verified", []):
            data.setdefault("verified", []).append(user.id)
            save_data(data)

    # VIP users get unlimited
    if user.id in data.get("vip", []):
        link_info = "\n".join([f"🔗 <b>{l['type']}:</b> {l['url']}" for l in links])
        await msg.reply_text("✅ <b>Request sent to admin!</b>\n\n👑 <b>VIP — Unlimited slots</b>\n\n━━━━━━━━━━━━━━━━━━━━━━━━━", parse_mode="HTML")
        admin_alert = (f"📬 <b>NEW DOWNLOAD REQUEST!</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 <b>User:</b> <a href='tg://user?id={user.id}'>{user.first_name}</a> 👑 VIP\n"
            f"🆔 <b>ID:</b> <code>{user.id}</code>\n")
        if user.username:
            admin_alert += f"🔗 <b>Username:</b> @{user.username}\n"
        admin_alert += f"\n{link_info}\n\n💬 <b>Group:</b> {update.effective_chat.title}\n\n━━━━━━━━━━━━━━━━━━━━━━━━━\n⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        for admin_id in ADMIN_IDS:
            try:
                await ctx.bot.send_message(admin_id, admin_alert, parse_mode="HTML", disable_web_page_preview=True)
            except:
                pass
        return

    # Check slots
    remaining = get_user_slots(data, user.id)

    if remaining <= 0:
        try:
            await msg.delete()
        except:
            pass
        key = str(user.id)
        data["users"][key]["muted"] = True
        save_data(data)
        try:
            utc_now = datetime.utcnow()
            ist_now = utc_now + timedelta(hours=TZ_OFFSET)
            midnight = ist_now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            unmute_utc = midnight - timedelta(hours=TZ_OFFSET)
            await ctx.bot.restrict_chat_member(update.effective_chat.id, user.id,
                permissions=ChatPermissions(can_send_messages=False, can_send_media_messages=False,
                    can_send_other_messages=False, can_add_web_page_previews=False),
                until_date=unmute_utc)
        except Exception as e:
            logger.error(f"Mute failed: {e}")
        limit = data.get("settings", {}).get("daily_limit", DAILY_LIMIT)
        notify = await update.effective_chat.send_message(
            f"❌ <b>{user.first_name}</b>, daily limit reached!\n\n"
            f"🎫 You've used all <b>{limit}</b> slots today.\n"
            f"🔇 You'll be unmuted at <b>12:00 AM IST</b>.\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━", parse_mode="HTML"
        )
        await asyncio.sleep(30)
        try:
            await notify.delete()
        except:
            pass
        return

    # Use slot
    new_remaining = use_slot(data, user.id)
    limit = data.get("settings", {}).get("daily_limit", DAILY_LIMIT)
    used = limit - new_remaining
    link_info = "\n".join([f"🔗 <b>{l['type']}:</b> {l['url']}" for l in links])

    await msg.reply_text(
        f"✅ <b>Request sent to admin!</b>\n\n"
        f"🎫 Slots: {used}/{limit} used | <b>{new_remaining} remaining</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ Resets at 12:00 AM IST", parse_mode="HTML"
    )

    admin_alert = (
        f"📬 <b>NEW DOWNLOAD REQUEST!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>User:</b> <a href='tg://user?id={user.id}'>{user.first_name}</a>\n"
        f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
    )
    if user.username:
        admin_alert += f"🔗 <b>Username:</b> @{user.username}\n"
    admin_alert += (
        f"\n{link_info}\n\n"
        f"🎫 <b>Slots used:</b> {used}/{limit}\n"
        f"💬 <b>Group:</b> {update.effective_chat.title}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )
    for admin_id in ADMIN_IDS:
        try:
            await ctx.bot.send_message(admin_id, admin_alert, parse_mode="HTML", disable_web_page_preview=True)
        except:
            pass

async def post_init(app: Application):
    await app.bot.set_my_commands([
        BotCommand("start", "Start & verify"),
        BotCommand("help", "How to use"),
        BotCommand("slots", "Check remaining slots"),
        BotCommand("info", "Your info & VIP status"),
    ])

flask_app = Flask(__name__)
tg_app = None

@flask_app.route("/")
def index():
    return "🎨 Envato & Freepik Manager Bot is running!", 200

@flask_app.route(f"/webhook", methods=["POST"])
def webhook():
    if tg_app:
        update = Update.de_json(flask_request.get_json(force=True), tg_app.bot)
        asyncio.run_coroutine_threadsafe(tg_app.process_update(update), tg_app._loop)
    return "ok", 200

def build_app():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("slots", slots_cmd))
    app.add_handler(CommandHandler("info", info_cmd))
    app.add_handler(CommandHandler("setlimit", setlimit_cmd))
    app.add_handler(CommandHandler("resetuser", resetuser_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("addvip", addvip_cmd))
    app.add_handler(CommandHandler("removevip", removevip_cmd))
    app.add_handler(CommandHandler("viplist", viplist_cmd))
    app.add_handler(CallbackQueryHandler(verify_callback, pattern="^verify_join$"))
    app.add_handler(CallbackQueryHandler(vip_forcejoin_callback, pattern="^vip_(fj|cancel)_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_group_message))
    return app

async def run_webhook():
    global tg_app
    tg_app = build_app()
    await tg_app.initialize()
    await tg_app.start()
    tg_app._loop = asyncio.get_event_loop()
    webhook_path = f"{WEBHOOK_URL}/webhook"
    await tg_app.bot.set_webhook(webhook_path)
    print(f"🎨 Envato & Freepik Manager Bot is running! (webhook: {webhook_path})")

def main():
    if not BOT_TOKEN:
        print("Set BOT_TOKEN!")
        return

    if MODE == "webhook" and WEBHOOK_URL:
        # Webhook mode for Render / production
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_webhook())
        threading.Thread(target=loop.run_forever, daemon=True).start()
        flask_app.run(host="0.0.0.0", port=PORT)
    else:
        # Polling mode for local development
        app = build_app()
        print("🎨 Envato & Freepik Manager Bot is running! (polling)")
        app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
