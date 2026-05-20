import os
import json
import asyncio
import logging
import base64
import requests as _requests
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ============ BOT CONFIGURATION ============
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8675598309:AAFGGbJh8HlR0TraxpbWkRy8PSVs4wmkaPQ")
OWNER_ID = int(os.getenv("OWNER_ID", "6162078955"))
# ===========================================

import main as fb

_executor = ThreadPoolExecutor(max_workers=32)

GITHUB_TOKEN  = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO   = "yuennix/FB-TGBOT"
GITHUB_BRANCH = "main"
GITHUB_API    = f"https://api.github.com/repos/{GITHUB_REPO}/contents/users.json"

USERS_FILE = "users.json"

def _gh_headers():
    return {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

def load_from_github():
    if not GITHUB_TOKEN:
        return
    try:
        r = _requests.get(GITHUB_API, headers=_gh_headers(), params={"ref": GITHUB_BRANCH}, timeout=10)
        if r.status_code == 200:
            content = base64.b64decode(r.json()["content"]).decode("utf-8")
            with open(USERS_FILE, "w") as f:
                f.write(content)
    except Exception:
        pass

def sync_to_github():
    if not GITHUB_TOKEN:
        return
    try:
        with open(USERS_FILE, "r") as f:
            content = f.read()
        encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        r = _requests.get(GITHUB_API, headers=_gh_headers(), params={"ref": GITHUB_BRANCH}, timeout=10)
        sha = r.json().get("sha") if r.status_code == 200 else None
        payload = {
            "message": "chore: sync users.json",
            "content": encoded,
            "branch": GITHUB_BRANCH,
        }
        if sha:
            payload["sha"] = sha
        _requests.put(GITHUB_API, headers=_gh_headers(), json=payload, timeout=10)
    except Exception:
        pass

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_data       = {}
seen_users      = set()
approved_users  = set()
pending_users   = {}
stop_flags      = {}
created_accounts= []
user_credits    = {}
owner_action    = {}
creating_msg    = {}

def load_users():
    global seen_users, approved_users, user_credits, pending_users, created_accounts
    try:
        with open(USERS_FILE, "r") as f:
            data = json.load(f)
        seen_users     = set(data.get("seen_users", []))
        approved_users = set(data.get("approved_users", []))
        user_credits   = {int(k): v for k, v in data.get("user_credits", {}).items()}
        for uid_str, info in data.get("pending_users", {}).items():
            uid = int(uid_str)
            if uid not in pending_users:
                pending_users[uid] = info
        created_accounts = data.get("created_accounts", [])
    except Exception:
        pass

def save_users():
    try:
        with open(USERS_FILE, "w") as f:
            json.dump({
                "seen_users":       list(seen_users),
                "approved_users":   list(approved_users),
                "user_credits":     {str(k): v for k, v in user_credits.items()},
                "pending_users":    {str(k): v for k, v in pending_users.items()},
                "created_accounts": created_accounts,
            }, f)
        sync_to_github()
    except Exception:
        pass

def make_start_kb(uid=0):
    is_owner = (uid == OWNER_ID)
    rows = [
        [InlineKeyboardButton(text="✨ START CREATION ✨", callback_data="menu:create")]
    ]
    if is_owner:
        rows.append([
            InlineKeyboardButton(text="👤 My Accounts", callback_data="menu:myaccs"),
            InlineKeyboardButton(text="🌍 Bot Accounts", callback_data="menu:botaccs"),
        ])
    else:
        rows.append([InlineKeyboardButton(text="👤 My Accounts", callback_data="menu:myaccs")])
        rows.append([InlineKeyboardButton(text="💎 My Credits", callback_data="menu:mycredits")])
    if is_owner:
        rows.append([InlineKeyboardButton(text="⚙️ OWNER PANEL ⚙️", callback_data="menu:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def make_name_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇵🇭 Filipino Names", callback_data="name:1")],
        [InlineKeyboardButton(text="🔥 RPW Names", callback_data="name:2")],
        [InlineKeyboardButton(text="◀️ BACK", callback_data="back:main")],
    ])

def make_gender_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Male", callback_data="gender:1")],
        [InlineKeyboardButton(text="👩 Female", callback_data="gender:2")],
        [InlineKeyboardButton(text="🌈 Mixed", callback_data="gender:3")],
        [InlineKeyboardButton(text="◀️ BACK", callback_data="back:name")],
    ])

def make_acc_pass_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Custom Password", callback_data="accpass:custom")],
        [InlineKeyboardButton(text="🎲 Random Password", callback_data="accpass:random")],
        [InlineKeyboardButton(text="◀️ BACK", callback_data="back:gender")],
    ])

def make_stop_kb(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⛔ STOP CREATION ⛔", callback_data=f"stop:{uid}")]
    ])

def make_approval_kb(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ APPROVE", callback_data=f"access:ok:{user_id}"),
            InlineKeyboardButton(text="❌ DENY", callback_data=f"access:no:{user_id}"),
        ]
    ])

def make_credit_give_kb(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="5", callback_data=f"credits:give:{user_id}:5"),
         InlineKeyboardButton(text="10", callback_data=f"credits:give:{user_id}:10"),
         InlineKeyboardButton(text="20", callback_data=f"credits:give:{user_id}:20")],
        [InlineKeyboardButton(text="50", callback_data=f"credits:give:{user_id}:50"),
         InlineKeyboardButton(text="100", callback_data=f"credits:give:{user_id}:100"),
         InlineKeyboardButton(text="✏️ Custom", callback_data=f"credits:give:{user_id}:custom")],
    ])

def make_admin_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Approved Users", callback_data="menu:users")],
        [InlineKeyboardButton(text="📋 Created Accounts", callback_data="menu:accounts")],
        [InlineKeyboardButton(text="🔄 Reload Proxies", callback_data="menu:reload_proxies")],
        [InlineKeyboardButton(text="◀️ BACK", callback_data="menu:back")],
    ])

def make_users_kb():
    rows = []
    users = [u for u in approved_users if u != OWNER_ID]
    if not users:
        rows.append([InlineKeyboardButton(text="— No approved users —", callback_data="noop")])
    else:
        for u in users:
            info    = pending_users.get(u, {})
            label   = info.get("name", str(u))
            credits = user_credits.get(u, 0)
            rows.append([InlineKeyboardButton(
                text=f"👤 {label} ({u}) | 💳 {credits} credits",
                callback_data="noop"
            )])
            rows.append([
                InlineKeyboardButton(text="➕ Add Credits", callback_data=f"credits:add:{u}"),
                InlineKeyboardButton(text="🚫 Revoke", callback_data=f"revoke:{u}"),
            ])
    rows.append([InlineKeyboardButton(text="◀️ BACK", callback_data="menu:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def make_accounts_kb():
    rows = []
    if created_accounts:
        rows.append([InlineKeyboardButton(
            text=f"🗑 Clear All ({len(created_accounts)} accs)",
            callback_data="accounts:clear"
        )])
    else:
        rows.append([InlineKeyboardButton(text="— No accounts yet —", callback_data="noop")])
    rows.append([InlineKeyboardButton(text="◀️ BACK", callback_data="menu:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def is_allowed(uid):
    return uid == OWNER_ID or uid in approved_users

async def _del(chat_id, msg_id, delay=0):
    try:
        if delay:
            await asyncio.sleep(delay)
        await bot.delete_message(chat_id, msg_id)
    except Exception:
        pass

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    uid        = message.from_user.id
    first_name = message.from_user.first_name or "there"
    username   = f"@{message.from_user.username}" if message.from_user.username else "no username"

    user_data.pop(uid, None)
    owner_action.pop(uid, None)
    banner_id = creating_msg.pop(uid, None)
    if banner_id:
        asyncio.create_task(_del(uid, banner_id))

    if uid == OWNER_ID:
        approved_users.add(uid)

    if uid not in seen_users:
        seen_users.add(uid)
        save_users()
        await message.answer(
            f"✨ *Welcome, {first_name}!* ✨\n\n"
            f"🤖 *Facebook Auto Creator Bot*\n\n"
            f"┌─────────────────────────┐\n"
            f"│  🔥 Fast & Reliable     │\n"
            f"│  📧 Yandex Email Support│\n"
            f"│  🔐 Auto OTP Fetch      │\n"
            f"│  🖼️ Auto Profile Picture │\n"
            f"│  🌐 Proxy Support       │\n"
            f"└─────────────────────────┘\n\n"
            f"📌 *HOW TO USE:*\n"
            f"1️⃣ Tap *START CREATION*\n"
            f"2️⃣ Choose name style\n"
            f"3️⃣ Choose gender\n"
            f"4️⃣ Set account password\n"
            f"5️⃣ Type how many accounts\n"
            f"6️⃣ Get fully created accounts!\n\n"
            f"⚠️ *Note:* Access requires owner approval.",
            parse_mode="Markdown"
        )

    if is_allowed(uid):
        await message.answer(
            "🤖 *FACEBOOK AUTO CREATOR*\n\n👇 *Select an option below* 👇",
            parse_mode="Markdown",
            reply_markup=make_start_kb(uid)
        )
        return

    if uid in pending_users:
        await message.answer(
            "⏳ *Access Request Pending*\n\nYour request is waiting for owner approval. Please wait.",
            parse_mode="Markdown"
        )
        return

    pending_users[uid] = {"name": first_name, "username": username}
    save_users()
    req_msg = await message.answer(
        "🔒 *ACCESS REQUIRED*\n\nThis bot requires approval to use.\nYour request has been sent to the owner.\n\nPlease wait for approval ⏳",
        parse_mode="Markdown"
    )
    pending_users[uid]["req_msg_id"] = req_msg.message_id
    try:
        await bot.send_message(
            OWNER_ID,
            f"🔔 *NEW ACCESS REQUEST*\n\n👤 Name: *{first_name}*\n🆔 User ID: `{uid}`\n📛 Username: {username}\n\nApprove or deny below:",
            parse_mode="Markdown",
            reply_markup=make_approval_kb(uid)
        )
    except Exception:
        pass

@dp.message(Command("credits"))
async def cmd_credits(message: types.Message):
    uid = message.from_user.id
    banner_id = creating_msg.pop(uid, None)
    if banner_id:
        asyncio.create_task(_del(uid, banner_id))
    if uid == OWNER_ID:
        await message.answer("👑 *OWNER*\n\nYou have *unlimited credits*.", parse_mode="Markdown")
        return
    if not is_allowed(uid):
        return
    credits = user_credits.get(uid, 0)
    await message.answer(
        f"💎 *YOUR CREDITS*\n\nAvailable: *{credits}* credit(s)\n_(1 credit = 1 Facebook account)_",
        parse_mode="Markdown"
    )

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id != OWNER_ID:
        await message.answer("🔒 Owner only command.", parse_mode="Markdown")
        return
    total_seen      = len(seen_users)
    total_approved  = len([u for u in approved_users if u != OWNER_ID])
    total_pending   = len(pending_users)
    total_credits_remaining = sum(user_credits.values())
    total_accounts  = len(created_accounts)
    await message.answer(
        f"📊 *BOT STATISTICS*\n\n"
        f"┌─────────────────────┐\n"
        f"│ 👥 Users Seen: *{total_seen}*      │\n"
        f"│ ✅ Approved: *{total_approved}*     │\n"
        f"│ ⏳ Pending: *{total_pending}*      │\n"
        f"├─────────────────────┤\n"
        f"│ 💳 Credits Used: *{total_accounts}*│\n"
        f"│ 💰 Credits Left: *{total_credits_remaining}*│\n"
        f"├─────────────────────┤\n"
        f"│ 🤖 Accounts Created: *{total_accounts}*│\n"
        f"└─────────────────────┘",
        parse_mode="Markdown"
    )

@dp.message(Command("menu"))
async def cmd_menu(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    await message.answer(
        "⚙️ *OWNER MENU*\n\nChoose a section:",
        parse_mode="Markdown",
        reply_markup=make_admin_menu_kb()
    )

@dp.callback_query(lambda c: c.data == "menu:reload_proxies")
async def cb_reload_proxies(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Owner only.", show_alert=True)
        return
    
    # Reload proxies in main module
    try:
        fb.working_proxies = []
        fb.get_working_proxies()
        await callback.message.answer("✅ *Proxies reloaded successfully!*", parse_mode="Markdown")
    except Exception as e:
        await callback.message.answer(f"❌ *Failed to reload proxies:* `{e}`", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("access:"))
async def cb_approval(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("You are not the owner.", show_alert=True)
        return

    parts     = callback.data.split(":")
    action    = parts[1]
    target_id = int(parts[2])
    user_info = pending_users.get(target_id, {})
    name      = user_info.get("name", "User")

    if action == "ok":
        approved_users.add(target_id)
        pending_users.pop(target_id, None)
        await callback.message.edit_text(
            f"✅ *APPROVED!*\n\n👤 {name} (`{target_id}`)\n\n💳 *How many credits to give this user?*\n_(1 credit = 1 account)_",
            parse_mode="Markdown",
            reply_markup=make_credit_give_kb(target_id)
        )
    else:
        pending_users.pop(target_id, None)
        await callback.message.edit_text(
            f"❌ *DENIED*\n\n👤 {name} (`{target_id}`) has been rejected.",
            parse_mode="Markdown"
        )
        await bot.send_message(
            target_id,
            "❌ *Your access request was denied.*\n\nContact the owner if you think this is a mistake.",
            parse_mode="Markdown"
        )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("credits:give:"))
async def cb_give_credits(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Owner only.", show_alert=True)
        return

    parts     = callback.data.split(":")
    target_id = int(parts[2])
    amount    = parts[3]

    if amount == "custom":
        owner_action[OWNER_ID] = {
            "action":       "add_credits",
            "target":       target_id,
            "prompt_msg_id": callback.message.message_id,
        }
        await callback.message.edit_text(
            f"✏️ *Type the number of credits to give* 👤 `{target_id}`:\n\n_(Send a number, e.g. 30)_",
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    amount = int(amount)
    user_credits[target_id] = user_credits.get(target_id, 0) + amount
    total = user_credits[target_id]
    save_users()

    target_info = pending_users.get(target_id, {})
    name = target_info.get("name", str(target_id))

    await callback.message.edit_text(
        f"✅ *Credits Added!*\n\n👤 {name} (`{target_id}`)\n💳 New total: *{total}* credit(s).",
        parse_mode="Markdown"
    )
    try:
        req_msg_id = pending_users.get(target_id, {}).get("req_msg_id")
        if req_msg_id:
            asyncio.create_task(_del(target_id, req_msg_id))
        await bot.send_message(
            target_id,
            f"✅ *ACCESS APPROVED!*\n\n💳 You've been given *{amount}* credit(s).\n_(1 credit = 1 Facebook account)_\n\n📧 *Email:* Yandex alias will be used\n🖼️ *Profile Picture:* Auto uploaded\n🌐 *Proxies:* Enabled\n\n👇 *Tap below to start* 👇",
            parse_mode="Markdown",
            reply_markup=make_start_kb(target_id)
        )
    except Exception:
        pass
    await callback.answer(f"✅ Gave {amount} credits!", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith("credits:add:"))
async def cb_add_credits(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Owner only.", show_alert=True)
        return
    target_id = int(callback.data.split(":")[2])
    info  = pending_users.get(target_id, {})
    name  = info.get("name", str(target_id))
    total = user_credits.get(target_id, 0)
    await callback.message.edit_text(
        f"💳 *ADD CREDITS*\n\n👤 {name} (`{target_id}`)\n💰 Current: *{total}* credit(s)\n\nHow many to add?",
        parse_mode="Markdown",
        reply_markup=make_credit_give_kb(target_id)
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu:admin")
async def cb_admin_menu(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Owner only.", show_alert=True)
        return
    await callback.message.edit_text(
        "⚙️ *OWNER MENU*\n\nChoose a section:",
        parse_mode="Markdown",
        reply_markup=make_admin_menu_kb()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu:back")
async def cb_menu_back(callback: types.CallbackQuery):
    uid = callback.from_user.id
    await callback.message.edit_text(
        "🤖 *FACEBOOK AUTO CREATOR*\n\n👇 *Select an option below* 👇",
        parse_mode="Markdown",
        reply_markup=make_start_kb(uid)
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu:users")
async def cb_menu_users(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Owner only.", show_alert=True)
        return
    users  = [u for u in approved_users if u != OWNER_ID]
    header = f"👥 *APPROVED USERS* — {len(users)} user(s)\n\nManage credits & access:"
    await callback.message.edit_text(header, parse_mode="Markdown", reply_markup=make_users_kb())
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("revoke:"))
async def cb_revoke(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Owner only.", show_alert=True)
        return
    target = int(callback.data.split(":")[1])
    approved_users.discard(target)
    user_credits.pop(target, None)
    save_users()
    try:
        await bot.send_message(target, "🚫 Your access to this bot has been revoked.")
    except Exception:
        pass
    users  = [u for u in approved_users if u != OWNER_ID]
    header = f"👥 *APPROVED USERS* — {len(users)} user(s)\n\nManage credits & access:"
    await callback.message.edit_text(header, parse_mode="Markdown", reply_markup=make_users_kb())
    await callback.answer(f"🚫 Revoked access for {target}", show_alert=True)

@dp.callback_query(lambda c: c.data == "menu:accounts")
async def cb_menu_accounts(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Owner only.", show_alert=True)
        return
    if not created_accounts:
        text = "📋 *CREATED ACCOUNTS*\n\nNo accounts have been created yet."
    else:
        lines = []
        for i, acc in enumerate(created_accounts, 1):
            pfp_status = "✅ Profile Pic" if acc.get('profile_pic_uploaded') else "❌ No Profile Pic"
            lines.append(
                f"*{i}.* 👤 `{acc['name']}`\n    📧 `{acc['email']}`\n    🔑 `{acc['password']}`\n    🆔 `{acc['uid']}`\n    🖼️ {pfp_status}"
            )
            if acc.get('cookies'):
                lines.append(f"    🍪 *Cookies:* `{acc['cookies']}`")
        body = "\n\n".join(lines)
        text = f"📋 *CREATED ACCOUNTS* — {len(created_accounts)} total\n\n{body}"
        if len(text) > 4000:
            text = text[:3950] + "\n\n_...truncated_"
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=make_accounts_kb())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "accounts:clear")
async def cb_accounts_clear(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Owner only.", show_alert=True)
        return
    count = len(created_accounts)
    created_accounts.clear()
    save_users()
    await callback.message.edit_text(
        f"🗑 *CLEARED!* {count} account record(s) removed.\n\n📋 *CREATED ACCOUNTS*\n\nNo accounts yet.",
        parse_mode="Markdown",
        reply_markup=make_accounts_kb()
    )
    await callback.answer("✅ Cleared!", show_alert=True)

@dp.callback_query(lambda c: c.data == "menu:myaccs")
async def cb_my_accounts(callback: types.CallbackQuery):
    uid  = callback.from_user.id
    if not is_allowed(uid):
        await callback.answer("No access.", show_alert=True)
        return
    mine = [a for a in created_accounts if a.get("by") == uid]
    if not mine:
        text = "📋 *MY ACCOUNTS*\n\nYou haven't created any accounts yet."
    else:
        lines = []
        for i, acc in enumerate(mine, 1):
            pfp_status = "✅ Profile Pic" if acc.get('profile_pic_uploaded') else "❌ No Profile Pic"
            otp_line = f"\n    🔢 *OTP:* `{acc.get('otp_code', 'N/A')}`" if acc.get('otp_code') else ""
            lines.append(
                f"*{i}.* 👤 `{acc['name']}`\n    📧 `{acc['email']}`\n    🔑 `{acc['password']}`\n    🆔 `{acc['uid']}`\n    🖼️ {pfp_status}{otp_line}"
            )
            if acc.get('cookies'):
                lines.append(f"    🍪 *Cookies:* `{acc['cookies']}`")
        body = "\n\n".join(lines)
        text = f"📋 *MY ACCOUNTS* — {len(mine)} total\n\n{body}"
        if len(text) > 4000:
            text = text[:3950] + "\n\n_...truncated_"
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ BACK", callback_data="menu:back")]
    ])
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=back_kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu:botaccs")
async def cb_bot_accounts(callback: types.CallbackQuery):
    uid = callback.from_user.id
    if not is_allowed(uid):
        await callback.answer("No access.", show_alert=True)
        return
    is_owner = (uid == OWNER_ID)
    mine = created_accounts if is_owner else [a for a in created_accounts if a.get("by") == uid]
    label = "🌍 *BOT ACCOUNTS*" if is_owner else "📋 *MY ACCOUNTS*"
    if not mine:
        text = f"{label}\n\nNo accounts created yet."
    else:
        lines = []
        for i, acc in enumerate(mine, 1):
            pfp_status = "✅ Profile Pic" if acc.get('profile_pic_uploaded') else "❌ No Profile Pic"
            by_line = f"\n    👤 by `{acc.get('by', '?')}`" if is_owner else ""
            otp_line = f"\n    🔢 *OTP:* `{acc.get('otp_code', 'N/A')}`" if acc.get('otp_code') else ""
            lines.append(
                f"*{i}.* 👤 `{acc['name']}`\n    📧 `{acc['email']}`\n    🔑 `{acc['password']}`\n    🆔 `{acc['uid']}`\n    🖼️ {pfp_status}{by_line}{otp_line}"
            )
            if acc.get('cookies'):
                lines.append(f"    🍪 *Cookies:* `{acc['cookies']}`")
        body = "\n\n".join(lines)
        text = f"{label} — {len(mine)} account(s)\n\n{body}"
        if len(text) > 4000:
            text = text[:3950] + "\n\n_...truncated_"
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ BACK", callback_data="menu:back")]
    ])
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=back_kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu:mycredits")
async def cb_my_credits(callback: types.CallbackQuery):
    uid = callback.from_user.id
    if not is_allowed(uid):
        await callback.answer("No access.", show_alert=True)
        return
    credits = user_credits.get(uid, 0)
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ BACK", callback_data="menu:back")]
    ])
    await callback.message.edit_text(
        f"💎 *MY CREDITS*\n\nAvailable: *{credits}* credit(s)\n_(1 credit = 1 Facebook account)_",
        parse_mode="Markdown",
        reply_markup=back_kb
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "noop")
async def cb_noop(callback: types.CallbackQuery):
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu:create")
async def cb_name_style(callback: types.CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("⛔ You don't have access.", show_alert=True)
        return
    await callback.message.edit_text(
        "📛 *CHOOSE NAME STYLE*\n\nSelect one:",
        parse_mode="Markdown", reply_markup=make_name_kb()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("back:"))
async def cb_back(callback: types.CallbackQuery):
    uid  = callback.from_user.id
    step = callback.data.split(":")[1]
    if uid in user_data:
        user_data[uid].pop("awaiting", None)
        user_data[uid].pop("prompt_msg_id", None)
    if step == "main":
        user_data.pop(uid, None)
        await callback.message.edit_text(
            "🤖 *FACEBOOK AUTO CREATOR*\n\n👇 *Select an option below* 👇",
            parse_mode="Markdown",
            reply_markup=make_start_kb(uid)
        )
    elif step == "name":
        await callback.message.edit_text(
            "📛 *CHOOSE NAME STYLE*\n\nSelect one:",
            parse_mode="Markdown", reply_markup=make_name_kb()
        )
    elif step == "gender":
        await callback.message.edit_text(
            "⚤ *CHOOSE GENDER*\n\nSelect one:",
            parse_mode="Markdown", reply_markup=make_gender_kb()
        )
    elif step == "accpass":
        await callback.message.edit_text(
            "🔑 *SET ACCOUNT PASSWORD*\n\nChoose option:",
            parse_mode="Markdown",
            reply_markup=make_acc_pass_kb()
        )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("name:"))
async def cb_gender(callback: types.CallbackQuery):
    uid = callback.from_user.id
    user_data[uid] = {"name": callback.data.split(":")[1]}
    await callback.message.edit_text(
        "⚤ *CHOOSE GENDER*\n\nSelect one:",
        parse_mode="Markdown", reply_markup=make_gender_kb()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("gender:"))
async def cb_gender_select(callback: types.CallbackQuery):
    uid = callback.from_user.id
    if uid not in user_data:
        await callback.answer("Session expired. Use /start", show_alert=True)
        return
    user_data[uid]["gender"] = callback.data.split(":")[1]
    user_data[uid]["domain"] = "yandex"
    await callback.message.edit_text(
        "🔑 *SET ACCOUNT PASSWORD*\n\nChoose option:",
        parse_mode="Markdown",
        reply_markup=make_acc_pass_kb()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("accpass:"))
async def cb_acc_pass(callback: types.CallbackQuery):
    uid = callback.from_user.id
    if uid not in user_data:
        await callback.answer("Session expired. Use /start", show_alert=True)
        return
    choice = callback.data.split(":")[1]
    if choice == "random":
        user_data[uid]["password"]      = None
        user_data[uid]["awaiting"]      = "count"
        user_data[uid]["prompt_msg_id"] = callback.message.message_id
        await callback.message.edit_text(
            "🔢 *HOW MANY ACCOUNTS?*\n\n_(Type a number, e.g. 5)_\n\n"
            "📧 *Email:* Yandex alias will be used\n"
            "✅ *OTP will be automatically fetched from Yandex email!*\n"
            "🖼️ *Profile picture will be auto uploaded!*\n"
            "🌐 *Proxy support enabled!*\n"
            "🔄 *Will retry twice if OTP not found*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ BACK", callback_data="back:accpass")]
            ])
        )
    else:
        user_data[uid]["awaiting"]      = "custom_pass"
        user_data[uid]["prompt_msg_id"] = callback.message.message_id
        await callback.message.edit_text(
            "🔑 *TYPE YOUR CUSTOM PASSWORD*\n\n_(minimum 6 characters)_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ BACK", callback_data="back:accpass")]
            ])
        )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("stop:"))
async def cb_stop(callback: types.CallbackQuery):
    uid = int(callback.data.split(":")[1])
    if callback.from_user.id != uid and callback.from_user.id != OWNER_ID:
        await callback.answer("Not your session.", show_alert=True)
        return
    stop_flags[uid] = True
    creating_msg.pop(uid, None)
    await callback.answer("⛔ Stopped!", show_alert=False)
    try:
        await callback.message.delete()
    except Exception:
        pass
    await bot.send_message(
        uid,
        "⛔ *Creation stopped.*",
        parse_mode="Markdown"
    )
    await bot.send_message(
        uid,
        "🤖 *FACEBOOK AUTO CREATOR*\n\n👇 *Select an option below* 👇",
        parse_mode="Markdown",
        reply_markup=make_start_kb(uid)
    )

# ============ MAIN CREATION FUNCTION ============
async def _start_creation(uid, count, data, chat_id, is_continuation=False):
    stop_flags[uid] = False

    if not is_continuation:
        banner = await bot.send_message(
            chat_id,
            f"⚡ *CREATING {count} ACCOUNT(S)...*\n\n"
            f"┌─────────────────────────┐\n"
            f"│ 📧 Yandex alias will   │\n"
            f"│    be used             │\n"
            f"│ 🔐 OTP auto-fetched    │\n"
            f"│ 🖼️ Profile pic auto     │\n"
            f"│ 🌐 Proxy enabled       │\n"
            f"│ 🔄 Retry twice if fail │\n"
            f"│ ⏰ 3 min wait for OTP  │\n"
            f"└─────────────────────────┘",
            parse_mode="Markdown",
            reply_markup=make_stop_kb(uid)
        )
        creating_msg[uid] = banner.message_id

    name_val   = str(data.get("name", "1"))
    gender_val = str(data.get("gender", "1"))
    custom_pw  = data.get("password", None)

    N_WORKERS = 2
    session_executor = ThreadPoolExecutor(max_workers=N_WORKERS, thread_name_prefix=f"fb_{uid}")

    success = 0
    lock = asyncio.Lock()
    stopped = False

    async def _worker():
        nonlocal success, stopped
        while True:
            if stopped or stop_flags.get(uid):
                return
            if success >= count:
                return

            def _register():
                try:
                    result = fb.register_account_for_bot(
                        domain_choice="yandex",
                        name_option=name_val,
                        gender_option=gender_val,
                        custom_pass=custom_pw,
                    )
                    return result
                except Exception as e:
                    print(f"[ERROR] Registration error: {e}")
                    return {"error": str(e)}

            try:
                result = await asyncio.to_thread(_register)
            except Exception as e:
                result = {"error": str(e)}

            if stop_flags.get(uid):
                async with lock:
                    stopped = True
                return

            if result and isinstance(result, dict) and result.get("uid"):
                async with lock:
                    if stopped or success >= count:
                        return
                    success += 1
                    current = success
                    if uid != OWNER_ID:
                        user_credits[uid] = max(0, user_credits.get(uid, 0) - 1)
                    credits_left = "" if uid == OWNER_ID else f"\n💳 Credits left: *{user_credits.get(uid, 0)}*"
                    
                    otp_code_value = result.get("otp_code")
                    if otp_code_value and str(otp_code_value) not in ["None", "N/A", ""]:
                        otp_line = f"\n🔢 *OTP:* `{otp_code_value}`"
                    else:
                        otp_line = ""
                    
                    cookies_full = result.get("cookies", "")
                    
                    account_data = {
                        "name":     result.get("name", "Unknown"),
                        "email":    result.get("email", "N/A"),
                        "password": result.get("password", "N/A"),
                        "uid":      result.get("uid", "N/A"),
                        "cookies":  cookies_full,
                        "otp_code": otp_code_value,
                        "profile_pic_uploaded": True,  # main.py handles this now
                        "by":       uid,
                    }
                    created_accounts.append(account_data)
                    save_users()
                    
                    cookie_msg = f"\n🍪 *Cookies:* `{cookies_full}`" if cookies_full else ""
                    
                await bot.send_message(
                    chat_id,
                    f"✅ *ACCOUNT {current}/{count} FULLY CREATED!*\n\n"
                    f"┌─────────────────────────┐\n"
                    f"│ 👤 *Name:* `{result.get('name', 'Unknown')}`\n"
                    f"│ 📧 *Email:* `{result.get('email', 'N/A')}`\n"
                    f"│ 🔑 *Password:* `{result.get('password', 'N/A')}`\n"
                    f"│ 🆔 *UID:* `{result.get('uid', 'N/A')}`\n"
                    f"│ 🖼️ *Profile Picture:* ✅ Uploaded\n"
                    f"{otp_line}\n"
                    f"{cookie_msg}\n"
                    f"{credits_left}\n"
                    f"└─────────────────────────┘\n\n"
                    f"🔗 *Login:* https://facebook.com/{result.get('uid', '')}",
                    parse_mode="Markdown"
                )
                
                if current >= count:
                    return
            
            elif result and isinstance(result, dict) and result.get("error"):
                await asyncio.sleep(3)
            
            else:
                await asyncio.sleep(2)

    tasks = [asyncio.create_task(_worker()) for _ in range(N_WORKERS)]
    try:
        await asyncio.gather(*tasks)
    finally:
        session_executor.shutdown(wait=False)

    if not is_continuation:
        banner_id = creating_msg.pop(uid, None)
        if banner_id:
            asyncio.create_task(_del(chat_id, banner_id))

    stop_flags.pop(uid, None)
    credits_summary = (
        "" if uid == OWNER_ID
        else f"\n💳 Credits remaining: *{user_credits.get(uid, 0)}*"
    )

    if success == 0:
        await bot.send_message(
            chat_id,
            "❌ *NO ACCOUNTS CREATED.*\n\n"
            "Possible reasons:\n"
            "• Facebook may be blocking registrations from this IP\n"
            "• No working proxies in proxies.txt\n"
            "• Yandex email rate limit reached\n\n"
            "Try again later or contact the owner.\n\n"
            "💡 *Tip:* Make sure your Yandex email is working and check spam folder.",
            parse_mode="Markdown"
        )
        await bot.send_message(
            chat_id,
            "🤖 *FACEBOOK AUTO CREATOR*\n\n👇 *Select an option below* 👇",
            parse_mode="Markdown",
            reply_markup=make_start_kb(uid)
        )
    else:
        await bot.send_message(
            chat_id,
            f"🎉 *DONE!* {success}/{count} accounts created.{credits_summary}\n\n"
            f"✅ All accounts have profile pictures!\n"
            f"✅ All checkpoints completed!",
            parse_mode="Markdown"
        )
        await bot.send_message(
            chat_id,
            "🤖 *FACEBOOK AUTO CREATOR*\n\n👇 *Select an option below* 👇",
            parse_mode="Markdown",
            reply_markup=make_start_kb(uid)
        )

@dp.message()
async def handle_text(message: types.Message):
    uid      = message.from_user.id
    chat_id  = message.chat.id
    entered  = (message.text or "").strip()

    data     = user_data.get(uid)
    awaiting = data.get("awaiting") if data else None

    if not data or awaiting not in ("custom_pass", "count"):
        return

    prompt_msg_id = data.pop("prompt_msg_id", None)

    asyncio.create_task(_del(chat_id, message.message_id))

    if awaiting == "custom_pass":
        if prompt_msg_id:
            asyncio.create_task(_del(chat_id, prompt_msg_id))
        if len(entered) < 6:
            err = await message.answer(
                "⚠️ Password too short _(min 6 chars)_. Try again:", parse_mode="Markdown"
            )
            asyncio.create_task(_del(chat_id, err.message_id, delay=4))
            user_data[uid]["awaiting"]      = "custom_pass"
            user_data[uid]["prompt_msg_id"] = err.message_id
            return
        user_data[uid]["password"] = entered
        user_data[uid].pop("awaiting", None)
        prompt = await message.answer(
            "✅ *Custom password set!*\n\n🔢 *HOW MANY ACCOUNTS?*\n\n_(Type a number, e.g. 5)_\n\n"
            "📧 *Email:* Yandex alias will be used\n"
            "✅ *OTP will be automatically fetched from Yandex email!*\n"
            "🖼️ *Profile picture will be auto uploaded!*\n"
            "🌐 *Proxy support enabled!*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ BACK", callback_data="back:accpass")]
            ])
        )
        user_data[uid]["awaiting"]      = "count"
        user_data[uid]["prompt_msg_id"] = prompt.message_id
        return

    if awaiting == "count":
        if prompt_msg_id:
            asyncio.create_task(_del(chat_id, prompt_msg_id))
        if not entered.isdigit() or int(entered) <= 0:
            err = await message.answer(
                "⚠️ Please type a *valid number* (e.g. 5).", parse_mode="Markdown"
            )
            asyncio.create_task(_del(chat_id, err.message_id, delay=4))
            user_data[uid]["awaiting"]      = "count"
            user_data[uid]["prompt_msg_id"] = err.message_id
            return
        count = int(entered)
        if count > 50:
            count = 50
            await message.answer("⚠️ Max 50 accounts per batch. Creating 50.", parse_mode="Markdown")
        if uid != OWNER_ID:
            available = user_credits.get(uid, 0)
            if available <= 0:
                err = await message.answer(
                    "❌ *You have no credits left.*\nContact the owner to get more credits.",
                    parse_mode="Markdown"
                )
                asyncio.create_task(_del(chat_id, err.message_id, delay=6))
                user_data.pop(uid, None)
                return
            if count > available:
                count = available
                note = await message.answer(
                    f"⚠️ You only have *{available}* credit(s). Creating *{available}* account(s).",
                    parse_mode="Markdown"
                )
                asyncio.create_task(_del(chat_id, note.message_id, delay=5))

        data = user_data.pop(uid)
        await _start_creation(uid, count, data, message.chat.id)

async def main():
    print("=" * 60)
    print("🤖 FACEBOOK AUTO CREATOR BOT 🤖")
    print("=" * 60)
    print(f"📧 Email: Yandex")
    print(f"👑 Owner ID: {OWNER_ID}")
    print("🔐 OTP: Auto-fetched from Yandex (3 min wait)")
    print("🖼️ Profile Picture: Auto uploaded")
    print("🌐 Proxy Support: Enabled (proxies.txt)")
    print("=" * 60)
    logging.basicConfig(level=logging.INFO)
    
    # Load proxies at startup
    try:
        fb.get_working_proxies()
    except:
        print("⚠️ No proxies loaded, using direct connection")
    
    load_from_github()
    load_users()

    await bot.delete_webhook(drop_pending_updates=True)
    
    await bot.set_my_commands([
        types.BotCommand(command="start",    description="🚀 Start the bot"),
        types.BotCommand(command="credits",  description="💳 Check your credits"),
        types.BotCommand(command="myaccs",   description="📋 My created accounts"),
    ])

    await bot.set_my_commands(
        [
            types.BotCommand(command="start",       description="🚀 Start the bot"),
            types.BotCommand(command="myaccs",      description="📋 My created accounts"),
            types.BotCommand(command="botaccs",     description="🌍 All bot accounts"),
            types.BotCommand(command="credits",     description="💳 Credits info"),
            types.BotCommand(command="stats",       description="📊 Bot statistics"),
            types.BotCommand(command="menu",        description="⚙️ Owner menu"),
        ],
        scope=types.BotCommandScopeChat(chat_id=OWNER_ID)
    )

    print("✅ Bot is running! Press Ctrl+C to stop.")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
