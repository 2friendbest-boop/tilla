# -*- coding: utf-8 -*-
"""
🎮 GAME STORE BOT  —  PUBG • Free Fire • Roblox • Standoff 2 • Telegram Stars
Hisob (balans) tizimi • Admin panel • Referal • Promokod • VIP darajalar • Rangli tugmalar • Premium emoji
Render uchun moslangan: sozlamalar environment variable orqali, health-server, doimiy disk.
"""
import asyncio
import html
import logging
import os
import re
import time

import aiosqlite
from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import BaseFilter, Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiohttp import web

# ═══════════════════════ SOZLAMALAR (Render → Environment) ═══════════════════════
BOT_TOKEN = os.environ["BOT_TOKEN"]                                   # majburiy
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x]
_ch = os.getenv("REQUIRED_CHANNEL", "").strip()                       # "@kanalim" yoki https://t.me/kanalim; bo'sh = o'chiq
if _ch.startswith("https://t.me/"):
    _ch = "@" + _ch[len("https://t.me/"):]
elif _ch.startswith("t.me/"):
    _ch = "@" + _ch[len("t.me/"):]
elif _ch and not _ch.startswith("@") and not _ch.lstrip("-").isdigit():
    _ch = "@" + _ch
REQUIRED_CHANNEL = _ch
DB_FILE = os.getenv("DB_FILE", "store.db")                            # Render diskida: /data/store.db

# ── Premium emoji ──
# Render → Environment: USE_PREMIUM=1  (bot egasida Telegram Premium bo'lishi kerak)
# Har bir oddiy emoji yoniga o'zingizning premium emoji ID sini qo'ying.
# ID bo'sh ("") bo'lsa — oddiy emoji ko'rinadi. Tugma matni shu emoji bilan boshlansa,
# u avtomatik premium ikonkaga almashadi.
USE_PREMIUM = os.getenv("USE_PREMIUM", "0") == "1"
PREMIUM_EMOJI = {
    "🎮": "5264959791213586839",   # Xarid qilish
    "⭐": "5807791714093502248",   # Telegram Stars
    "💰": "5256186332669035163",   # Hisobim / Balans
    "➕": "5222040745665379997",   # Hisob to'ldirish / qo'shish
    "➖": "5417835132025328839",   # Hisob ayirish
    "📦": "5436261671301564151",   # Buyurtmalarim
    "👥": "5310008912907360202",   # Referal
    "🎁": "5841267724285646096",   # Promokod
    "🏆": "5415655814079723871",   # Top xaridorlar
    "📅": "5399817885952520170",   # Kunlik bonus
    "🆘": "5213285132709929474",   # Yordam
    "⚙️": "5341715473882955310",   # Admin panel / Sozlamalar
    "⬅️": "5352759161945867747",   # Orqaga / Menyu
    "❌": "",   # Bekor
    "✅": "",   # Tasdiqlash / Bajarildi
    "📢": "",   # Kanal / Xabar yuborish
    "📤": "",   # Ulashish
    "📊": "",   # Statistika
    "⏳": "",   # Kutilayotganlar
    "👤": "",   # Foydalanuvchi
    "🚫": "",   # Ban
    "🔓": "",   # Unban
    "💬": "",   # Yozish
    "🟢": "",   # Yoqish
    "🔴": "",   # O'chirish
    "✏️": "",   # Tahrirlash
    "💵": "5298877105000439431",   # Narx
    "🗑": "",   # Butunlay o'chirish
    "👨‍💻": "",  # Admin bilan bog'lanish
    "🔫": "5204252919565657978",   # PUBG
    "🔥": "6156638827709467651",   # Free Fire
    "🧱": "5235507619916950217",   # Roblox
    "🎯": "5294063533288334126",   # Standoff 2
    "👑": "",   # Menyu sarlavhasi
}

# VIP darajalar: (jami xarid summasi, nomi, chegirma %)
LEVELS = [
    (0,         "🥉 Bronza",  0),
    (300_000,   "🥈 Kumush",  2),
    (1_000_000, "🥇 Oltin",   4),
    (3_000_000, "💎 Platina", 6),
    (7_000_000, "👑 VIP",     8),
]
# ══════════════════════════════════════════════════════════

P, G, R = "primary", "success", "danger"   # ko'k, yashil, qizil tugma
bot: Bot = None
DB: aiosqlite.Connection = None
logging.basicConfig(level=logging.INFO)

DEFAULT_SETTINGS = {
    "card_number": "6262910201065257",
    "card_owner": "N.S",
    "min_topup": "5000",
    "ref_bonus": "1000",
    "daily_bonus": "500",
    "support_username": "@nrvsh17",
    "welcome": "Eng ishonchli va tezkor o'yin valyutalari do'koni 🚀",
}
SETTING_LABELS = {
    "card_number": "💳 Karta raqami",
    "card_owner": "👤 Karta egasi",
    "min_topup": "⬇️ Minimal to'ldirish",
    "ref_bonus": "🎁 Referal bonus (so'm)",
    "daily_bonus": "📅 Kunlik bonus (0 = o'chiq)",
    "support_username": "🆘 Support username (@siz)",
    "welcome": "👋 Salomlashish matni",
}
NUMERIC = {"min_topup", "ref_bonus", "daily_bonus"}

SEED = [
    ("pubg", "PUBG Mobile", "🔫", "PUBG Mobile <b>ID</b> raqamingizni yuboring:",
     [("60 UC", 12000), ("325 UC", 60000), ("660 UC", 120000), ("1800 UC", 300000)]),
    ("ff", "Free Fire", "🔥", "Free Fire <b>ID</b> raqamingizni yuboring:",
     [("100 💎", 11000), ("310 💎", 33000), ("520 💎", 55000), ("1060 💎", 110000)]),
    ("roblox", "Roblox", "🧱", "Roblox <b>username</b> (login) ingizni yuboring:",
     [("80 Robux", 14000), ("400 Robux", 70000), ("800 Robux", 135000)]),
    ("standoff", "Standoff 2", "🎯", "Standoff 2 <b>ID</b> raqamingizni yuboring:",
     [("100 G", 12000), ("500 G", 55000), ("1000 G", 105000)]),
]

# Stars paketlari: (miqdor, narx so'mda)
STARS_PACKAGES = [
    (50, 12000),
    (100, 23000),
    (150, 35000),
    (250, 57000),
    (500, 112000),
    (750, 168000),
    (1000, 222000),
    (1500, 333000),
    (2500, 550000),
    (5000, 1100000),
]

# Boshqa miqdor uchun
PRICE_PER_STAR = 240
MIN_CUSTOM = 50
MAX_CUSTOM = 10000


# ═══════════════════════ YORDAMCHILAR ═══════════════════════
def e(s):
    return html.escape(str(s or ""))


def fmt(n):
    return f"{int(n):,}".replace(",", " ") + " so'm"


def pe(emoji):
    """Matn ichida premium emoji (ID yo'q yoki o'chiq bo'lsa — oddiy emoji)."""
    eid = PREMIUM_EMOJI.get(emoji)
    if USE_PREMIUM and eid:
        return f'<tg-emoji emoji-id="{eid}">{emoji}</tg-emoji>'
    return emoji


def B(text, cb=None, style=None, url=None):
    kw = {}
    if USE_PREMIUM:
        for em, eid in PREMIUM_EMOJI.items():
            if eid and text.startswith(em):
                kw["icon_custom_emoji_id"] = eid      # tugma ikonkasi (premium)
                text = text[len(em):].lstrip() or "​"
                break
    kw["text"] = text
    if cb:
        kw["callback_data"] = cb
    if url:
        kw["url"] = url
    if style:
        kw["style"] = style
    return InlineKeyboardButton(**kw)


def kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)


def level(spent):
    idx = 0
    for i, (th, _, _) in enumerate(LEVELS):
        if spent >= th:
            idx = i
    return idx, LEVELS[idx][1], LEVELS[idx][2]


def disc(price, pct):
    return price * (100 - pct) // 100


async def ex(sql, args=()):
    cur = await DB.execute(sql, args)
    await DB.commit()
    return cur


async def one(sql, args=()):
    cur = await DB.execute(sql, args)
    return await cur.fetchone()


async def many(sql, args=()):
    cur = await DB.execute(sql, args)
    return await cur.fetchall()


async def gs(key):
    r_ = await one("SELECT value FROM settings WHERE key=?", (key,))
    return r_["value"] if r_ else DEFAULT_SETTINGS.get(key, "")


async def ss(key, value):
    await ex("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
             (key, value))


async def show(ev, text, markup=None):
    if isinstance(ev, CallbackQuery):
        try:
            await ev.message.edit_text(text, reply_markup=markup)
            return
        except Exception:
            await ev.message.answer(text, reply_markup=markup)
    else:
        await ev.answer(text, reply_markup=markup)


async def safe_send(uid, text, markup=None):
    try:
        await bot.send_message(uid, text, reply_markup=markup)
        return True
    except Exception as ex_:
        logging.warning("send fail %s: %s", uid, ex_)
        return False


async def notify_admins(text, markup=None, photo=None):
    for a in ADMIN_IDS:
        try:
            if photo:
                await bot.send_photo(a, photo, caption=text, reply_markup=markup)
            else:
                await bot.send_message(a, text, reply_markup=markup)
        except Exception as ex_:
            logging.warning("admin notify fail %s: %s", a, ex_)


async def append_status(c: CallbackQuery, line):
    try:
        await c.message.edit_text(c.message.html_text + "\n\n" + line, reply_markup=None)
    except Exception:
        try:
            await c.message.edit_caption(caption=(c.message.html_text or "") + "\n\n" + line, reply_markup=None)
        except Exception:
            pass


async def credit(uid, amount):
    """Balansga pul qo'shish + referal bonusini berish."""
    await ex("UPDATE users SET balance=balance+? WHERE id=?", (amount, uid))
    u = await one("SELECT ref_by, ref_paid FROM users WHERE id=?", (uid,))
    if u and u["ref_by"] and not u["ref_paid"]:
        await ex("UPDATE users SET ref_paid=1 WHERE id=?", (uid,))
        bonus = int(await gs("ref_bonus") or 0)
        if bonus > 0:
            await ex("UPDATE users SET balance=balance+?, ref_earn=ref_earn+? WHERE id=?",
                     (bonus, bonus, u["ref_by"]))
            await safe_send(u["ref_by"],
                            f"🎉 Taklif qilgan do'stingiz hisobini to'ldirdi!\nSizga <b>{fmt(bonus)}</b> bonus berildi 💰")


# ═══════════════════════ BAZA ═══════════════════════
async def init_db():
    global DB
    os.makedirs(os.path.dirname(DB_FILE) or ".", exist_ok=True)
    DB = await aiosqlite.connect(DB_FILE)
    DB.row_factory = aiosqlite.Row
    await DB.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY, name TEXT, username TEXT,
        balance INTEGER DEFAULT 0, spent INTEGER DEFAULT 0,
        ref_by INTEGER, ref_paid INTEGER DEFAULT 0, ref_earn INTEGER DEFAULT 0,
        banned INTEGER DEFAULT 0, joined INTEGER, last_bonus TEXT);
    CREATE TABLE IF NOT EXISTS games(
        id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT, title TEXT, emoji TEXT,
        prompt TEXT, active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT, game_id INTEGER, title TEXT,
        price INTEGER, active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, game TEXT, title TEXT,
        price INTEGER, player_id TEXT, status TEXT DEFAULT 'pending', created INTEGER);
    CREATE TABLE IF NOT EXISTS topups(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER,
        status TEXT DEFAULT 'pending', created INTEGER);
    CREATE TABLE IF NOT EXISTS promos(code TEXT PRIMARY KEY, amount INTEGER, uses_left INTEGER);
    CREATE TABLE IF NOT EXISTS promo_used(code TEXT, user_id INTEGER, PRIMARY KEY(code,user_id));
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
    """)
    for k, v in DEFAULT_SETTINGS.items():
        await DB.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))
    if not await one("SELECT 1 FROM games LIMIT 1"):
        for key, title, emoji, prompt, prods in SEED:
            cur = await DB.execute("INSERT INTO games(key,title,emoji,prompt) VALUES(?,?,?,?)",
                                   (key, title, emoji, prompt))
            for t, p in prods:
                await DB.execute("INSERT INTO products(game_id,title,price) VALUES(?,?,?)", (cur.lastrowid, t, p))
    await DB.commit()


# ═══════════════════════ HOLATLAR ═══════════════════════
class S(StatesGroup):
    player = State()
    top_amount = State()
    top_receipt = State()
    promo = State()
    support = State()
    admin = State()
    stars_custom = State()
    stars_user = State()


class IsAdmin(BaseFilter):
    async def __call__(self, ev) -> bool:
        return bool(ev.from_user and ev.from_user.id in ADMIN_IDS)


class Guard(BaseMiddleware):
    async def __call__(self, handler, event, data):
        u = event.from_user
        if u and u.id not in ADMIN_IDS:
            r_ = await one("SELECT banned FROM users WHERE id=?", (u.id,))
            if r_ and r_["banned"]:
                if isinstance(event, CallbackQuery):
                    await event.answer("🚫 Siz bloklangansiz", show_alert=True)
                return
            if REQUIRED_CHANNEL and not (isinstance(event, CallbackQuery) and event.data == "chk"):
                try:
                    mem = await bot.get_chat_member(REQUIRED_CHANNEL, u.id)
                    ok = mem.status in ("member", "administrator", "creator")
                except Exception as err:
                    logging.warning("channel check fail (bot kanalda admin emasmi?): %s", err)
                    ok = True
                if not ok:
                    markup = kb([[B("📢 Kanalga o'tish", url=f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}", style=P)],
                                 [B("✅ Tekshirish", "chk", G)]])
                    target = event.message if isinstance(event, CallbackQuery) else event
                    await target.answer("📢 Botdan foydalanish uchun avval kanalimizga obuna bo'ling:",
                                        reply_markup=markup)
                    if isinstance(event, CallbackQuery):
                        await event.answer()
                    return
        return await handler(event, data)


r = Router()
adm = Router()
adm.message.filter(IsAdmin())
adm.callback_query.filter(IsAdmin())


# ═══════════════════════ FOYDALANUVCHI: MENYU ═══════════════════════
async def main_menu(ev, uid, name):
    u = await one("SELECT * FROM users WHERE id=?", (uid,))
    if not u:  # baza tozalangan yoki foydalanuvchi /start bosmagan bo'lsa — avtomatik yaratamiz
        await ex("INSERT OR IGNORE INTO users(id,name,joined) VALUES(?,?,?)", (uid, name, int(time.time())))
        u = await one("SELECT * FROM users WHERE id=?", (uid,))
    _, lname, pct = level(u["spent"])
    welcome = await gs("welcome")
    text = (f"{pe('👑')} <b>GAME STORE</b>\n\n"
            f"Salom, <b>{e(name)}</b>! 👋\n{e(welcome)}\n\n"
            f"{pe('💰')} Balans: <b>{fmt(u['balance'])}</b>\n"
            f"🏅 Daraja: <b>{lname}</b>" + (f" (−{pct}% chegirma)" if pct else "") + "\n\n"
            f"👇 Kerakli bo'limni tanlang:")
    rows = [
        [B("🎮 Xarid qilish", "buy", G)],
        [B("⭐ Telegram Stars", "stars", P)],
        [B("💰 Hisobim", "acc", P), B("➕ Hisob to'ldirish", "top", G)],
        [B("📦 Buyurtmalarim", "orders"), B("👥 Referal", "ref", P)],
        [B("🎁 Promokod", "promo"), B("🏆 Top xaridorlar", "toplist")],
    ]
    if int(await gs("daily_bonus") or 0) > 0:
        rows.append([B("📅 Kunlik bonus", "daily", G)])
    rows.append([B("🆘 Yordam", "sup", P)])
    if uid in ADMIN_IDS:
        rows.append([B("⚙️ Admin panel", "adm", R)])
    await show(ev, text, kb(rows))


@r.message(CommandStart())
async def start(m: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    uid = m.from_user.id
    if not await one("SELECT 1 FROM users WHERE id=?", (uid,)):
        ref = None
        if command.args and command.args.startswith("ref_"):
            try:
                ref = int(command.args[4:])
            except ValueError:
                ref = None
            if ref == uid or not (ref and await one("SELECT 1 FROM users WHERE id=?", (ref,))):
                ref = None
        await ex("INSERT INTO users(id,name,username,ref_by,joined) VALUES(?,?,?,?,?)",
                 (uid, m.from_user.full_name, m.from_user.username, ref, int(time.time())))
        if ref:
            await safe_send(ref, f"👥 Sizning havolangiz orqali <b>{e(m.from_user.full_name)}</b> qo'shildi!")
    else:
        await ex("UPDATE users SET name=?, username=? WHERE id=?", (m.from_user.full_name, m.from_user.username, uid))
    await main_menu(m, uid, m.from_user.full_name)


@r.callback_query(F.data == "chk")
async def chk(c: CallbackQuery):
    await c.answer("✅")
    if not await one("SELECT 1 FROM users WHERE id=?", (c.from_user.id,)):
        await ex("INSERT INTO users(id,name,username,joined) VALUES(?,?,?,?)",
                 (c.from_user.id, c.from_user.full_name, c.from_user.username, int(time.time())))
    await main_menu(c, c.from_user.id, c.from_user.full_name)


@r.callback_query(F.data == "menu")
async def menu_cb(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await state.clear()
    await main_menu(c, c.from_user.id, c.from_user.full_name)


# ═══════════════════════ XARID ═══════════════════════
@r.callback_query(F.data == "buy")
async def buy(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await state.clear()
    games = await many("SELECT * FROM games WHERE active=1 ORDER BY id")
    rows = [[B(f"{g['emoji']} {g['title']}", f"g:{g['id']}", P)] for g in games]
    rows.append([B("⬅️ Menyu", "menu")])
    await show(c, "🎮 <b>O'yinni tanlang:</b>", kb(rows))


@r.callback_query(F.data.startswith("g:"))
async def game(c: CallbackQuery):
    await c.answer()
    gid = int(c.data[2:])
    g = await one("SELECT * FROM games WHERE id=?", (gid,))
    u = await one("SELECT spent FROM users WHERE id=?", (c.from_user.id,))
    _, _, pct = level(u["spent"])
    prods = await many("SELECT * FROM products WHERE game_id=? AND active=1 ORDER BY price", (gid,))
    rows = [[B(f"{p['title']} — {fmt(disc(p['price'], pct))}", f"p:{p['id']}", G)] for p in prods]
    rows.append([B("⬅️ Orqaga", "buy")])
    note = f"\n🏅 Sizga <b>−{pct}%</b> chegirma qo'llandi" if pct else ""
    text = f"{g['emoji']} <b>{e(g['title'])}</b>\n\nPaketni tanlang:{note}" if prods else \
        f"{g['emoji']} <b>{e(g['title'])}</b>\n\nHozircha paketlar yo'q."
    await show(c, text, kb(rows))


@r.callback_query(F.data.startswith("p:"))
async def prod(c: CallbackQuery, state: FSMContext):
    await c.answer()
    pid = int(c.data[2:])
    p = await one("SELECT p.*, g.prompt, g.title gt, g.emoji FROM products p JOIN games g ON g.id=p.game_id WHERE p.id=?",
                  (pid,))
    if not p:
        return
    await state.set_state(S.player)
    await state.update_data(pid=pid)
    await show(c, f"{p['emoji']} <b>{e(p['gt'])}</b> • {e(p['title'])}\n\n{p['prompt']}",
               kb([[B("❌ Bekor qilish", "menu", R)]]))


@r.message(S.player)
async def player(m: Message, state: FSMContext):
    pid_ = (m.text or "").strip()
    if not pid_ or len(pid_) > 64:
        return await m.answer("❌ Iltimos, ID ni matn ko'rinishida yuboring.")
    d = await state.get_data()
    p = await one("SELECT p.*, g.title gt FROM products p JOIN games g ON g.id=p.game_id WHERE p.id=?", (d["pid"],))
    u = await one("SELECT * FROM users WHERE id=?", (m.from_user.id,))
    _, _, pct = level(u["spent"])
    price = disc(p["price"], pct)
    await state.update_data(player=pid_, price=price)
    text = (f"🧾 <b>Buyurtmani tasdiqlang</b>\n\n"
            f"🎮 O'yin: <b>{e(p['gt'])}</b>\n📦 Paket: <b>{e(p['title'])}</b>\n"
            f"🆔 ID: <code>{e(pid_)}</code>\n💵 Narx: <b>{fmt(price)}</b>\n"
            f"{pe('💰')} Balansingiz: <b>{fmt(u['balance'])}</b>")
    if u["balance"] < price:
        text += f"\n\n⚠️ Balans yetarli emas. Yana <b>{fmt(price - u['balance'])}</b> kerak."
        rows = [[B("➕ Hisob to'ldirish", "top", G)], [B("⬅️ Menyu", "menu")]]
    else:
        rows = [[B("✅ Tasdiqlash", "ok", G), B("❌ Bekor", "menu", R)]]
    await m.answer(text, reply_markup=kb(rows))


@r.callback_query(F.data == "ok")
async def confirm(c: CallbackQuery, state: FSMContext):
    d = await state.get_data()
    if not d.get("pid"):
        await c.answer("Sessiya tugagan, qaytadan boshlang", show_alert=True)
        return
    p = await one("SELECT p.*, g.title gt FROM products p JOIN games g ON g.id=p.game_id WHERE p.id=?", (d["pid"],))
    price = d["price"]
    cur = await ex("UPDATE users SET balance=balance-?, spent=spent+? WHERE id=? AND balance>=?",
                   (price, price, c.from_user.id, price))
    if cur.rowcount == 0:
        await c.answer("❌ Balans yetarli emas", show_alert=True)
        return
    await c.answer("✅")
    cur = await ex("INSERT INTO orders(user_id,game,title,price,player_id,created) VALUES(?,?,?,?,?,?)",
                   (c.from_user.id, p["gt"], p["title"], price, d["player"], int(time.time())))
    oid = cur.lastrowid
    await state.clear()
    await show(c, f"✅ <b>Buyurtma #{oid} qabul qilindi!</b>\n\n"
                  f"🎮 {e(p['gt'])} • {e(p['title'])}\n🆔 <code>{e(d['player'])}</code>\n💵 {fmt(price)}\n\n"
                  f"⏳ Tez orada bajariladi. Natija haqida xabar beramiz.",
               kb([[B("🎮 Yana xarid", "buy", G)], [B("⬅️ Menyu", "menu")]]))
    u = c.from_user
    await notify_admins(
        f"🆕 <b>Yangi buyurtma #{oid}</b>\n\n👤 {e(u.full_name)} (@{e(u.username)}) • <code>{u.id}</code>\n"
        f"🎮 {e(p['gt'])} • <b>{e(p['title'])}</b>\n🆔 <code>{e(d['player'])}</code>\n💵 {fmt(price)}",
        kb([[B("✅ Bajarildi", f"od:{oid}", G), B("❌ Bekor + qaytarish", f"oc:{oid}", R)],
            [B("💬 Mijozga yozish", f"reply:{u.id}", P)]]))


# ═══════════════════════ TELEGRAM STARS ═══════════════════════
def stars_base_price(qty):
    for q, p in STARS_PACKAGES:
        if q == qty:
            return p
    return qty * PRICE_PER_STAR


@r.callback_query(F.data == "stars")
async def stars_menu(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await state.clear()
    u = await one("SELECT spent FROM users WHERE id=?", (c.from_user.id,))
    _, _, pct = level(u["spent"])
    rows, line = [], []
    for q, p in STARS_PACKAGES:
        line.append(B(f"⭐ {q} • {fmt(disc(p, pct))}", f"sp:{q}", G))
        if len(line) == 2:
            rows.append(line)
            line = []
    if line:
        rows.append(line)
    rows.append([B("⭐ Boshqa miqdor", "sc", P)])
    rows.append([B("⬅️ Menyu", "menu")])
    note = f"\n🏅 Sizga <b>−{pct}%</b> chegirma qo'llandi" if pct else ""
    await show(c, f"{pe('⭐')} <b>Telegram Stars</b>\n\nKerakli miqdorni tanlang:{note}", kb(rows))


async def stars_ask_user(ev, state, qty):
    await state.set_state(S.stars_user)
    await state.update_data(qty=qty)
    await show(ev, f"{pe('⭐')} <b>{qty} Stars</b>\n\nStars yuboriladigan <b>Telegram @username</b> ni yozing\n"
                   f"Masalan: <code>@username</code>",
               kb([[B("❌ Bekor qilish", "stars", R)]]))


@r.callback_query(F.data.startswith("sp:"))
async def stars_pick(c: CallbackQuery, state: FSMContext):
    await c.answer()
    qty = int(c.data[3:])
    if qty not in dict(STARS_PACKAGES):
        return
    await stars_ask_user(c, state, qty)


@r.callback_query(F.data == "sc")
async def stars_custom_btn(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await state.set_state(S.stars_custom)
    await show(c, f"{pe('⭐')} <b>Boshqa miqdor</b>\n\nNechta Stars kerak? ({MIN_CUSTOM} – {MAX_CUSTOM})\n"
                  f"💵 1 ta Star = <b>{fmt(PRICE_PER_STAR)}</b>",
               kb([[B("⬅️ Orqaga", "stars", R)]]))


@r.message(S.stars_custom)
async def stars_custom_in(m: Message, state: FSMContext):
    try:
        qty = int((m.text or "").replace(" ", ""))
    except ValueError:
        return await m.answer("❌ Faqat raqam yuboring. Masalan: 300")
    if not MIN_CUSTOM <= qty <= MAX_CUSTOM:
        return await m.answer(f"❌ Miqdor {MIN_CUSTOM} dan {MAX_CUSTOM} gacha bo'lishi kerak.")
    await stars_ask_user(m, state, qty)


@r.message(S.stars_user)
async def stars_user_in(m: Message, state: FSMContext):
    tg = (m.text or "").strip()
    if tg.startswith("https://t.me/"):
        tg = tg[len("https://t.me/"):]
    tg = tg.lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", tg):
        return await m.answer("❌ Username noto'g'ri. Masalan: <code>@username</code>")
    d = await state.get_data()
    qty = d["qty"]
    u = await one("SELECT * FROM users WHERE id=?", (m.from_user.id,))
    _, _, pct = level(u["spent"])
    price = disc(stars_base_price(qty), pct)
    await state.update_data(tg_user="@" + tg, price=price)
    text = (f"🧾 <b>Buyurtmani tasdiqlang</b>\n\n"
            f"{pe('⭐')} Miqdor: <b>{qty} Stars</b>\n👤 Qabul qiluvchi: <b>@{e(tg)}</b>\n"
            f"💵 Narx: <b>{fmt(price)}</b>\n{pe('💰')} Balansingiz: <b>{fmt(u['balance'])}</b>")
    if u["balance"] < price:
        text += f"\n\n⚠️ Balans yetarli emas. Yana <b>{fmt(price - u['balance'])}</b> kerak."
        rows = [[B("➕ Hisob to'ldirish", "top", G)], [B("⬅️ Menyu", "menu")]]
    else:
        rows = [[B("✅ Tasdiqlash", "sok", G), B("❌ Bekor", "menu", R)]]
    await m.answer(text, reply_markup=kb(rows))


@r.callback_query(F.data == "sok")
async def stars_confirm(c: CallbackQuery, state: FSMContext):
    d = await state.get_data()
    if not d.get("qty") or not d.get("tg_user"):
        return await c.answer("Sessiya tugagan, qaytadan boshlang", show_alert=True)
    qty, price, tg = d["qty"], d["price"], d["tg_user"]
    cur = await ex("UPDATE users SET balance=balance-?, spent=spent+? WHERE id=? AND balance>=?",
                   (price, price, c.from_user.id, price))
    if cur.rowcount == 0:
        return await c.answer("❌ Balans yetarli emas", show_alert=True)
    await c.answer("✅")
    cur = await ex("INSERT INTO orders(user_id,game,title,price,player_id,created) VALUES(?,?,?,?,?,?)",
                   (c.from_user.id, "Telegram Stars", f"{qty} Stars", price, tg, int(time.time())))
    oid = cur.lastrowid
    await state.clear()
    await show(c, f"✅ <b>Buyurtma #{oid} qabul qilindi!</b>\n\n{pe('⭐')} {qty} Stars\n"
                  f"👤 <code>{e(tg)}</code>\n💵 {fmt(price)}\n\n⏳ Tez orada yuboriladi. Natija haqida xabar beramiz.",
               kb([[B("⭐ Yana Stars", "stars", G)], [B("⬅️ Menyu", "menu")]]))
    u = c.from_user
    await notify_admins(
        f"🆕 <b>Yangi buyurtma #{oid}</b>\n\n👤 {e(u.full_name)} (@{e(u.username)}) • <code>{u.id}</code>\n"
        f"{pe('⭐')} <b>Telegram Stars — {qty}</b>\n📨 Yuborish: <b>{e(tg)}</b>\n💵 {fmt(price)}",
        kb([[B("✅ Bajarildi", f"od:{oid}", G), B("❌ Bekor + qaytarish", f"oc:{oid}", R)],
            [B("💬 Mijozga yozish", f"reply:{u.id}", P)]]))


# ═══════════════════════ HISOB ═══════════════════════
@r.callback_query(F.data == "acc")
async def account(c: CallbackQuery):
    await c.answer()
    u = await one("SELECT * FROM users WHERE id=?", (c.from_user.id,))
    idx, lname, pct = level(u["spent"])
    nxt = ""
    if idx + 1 < len(LEVELS):
        th, nn, np_ = LEVELS[idx + 1]
        nxt = f"\n📈 Keyingi daraja: {nn} (−{np_}%) uchun yana <b>{fmt(th - u['spent'])}</b>"
    cnt = (await one("SELECT COUNT(*) n FROM orders WHERE user_id=?", (u["id"],)))["n"]
    await show(c, f"{pe('💰')} <b>Hisobim</b>\n\n🆔 ID: <code>{u['id']}</code>\n"
                  f"💵 Balans: <b>{fmt(u['balance'])}</b>\n🛒 Jami xarid: <b>{fmt(u['spent'])}</b>\n"
                  f"📦 Buyurtmalar: <b>{cnt}</b>\n🏅 Daraja: <b>{lname}</b> (−{pct}%){nxt}",
               kb([[B("➕ Hisob to'ldirish", "top", G)], [B("📦 Buyurtmalarim", "orders", P)],
                   [B("⬅️ Menyu", "menu")]]))


@r.callback_query(F.data == "orders")
async def my_orders(c: CallbackQuery):
    await c.answer()
    rows = await many("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (c.from_user.id,))
    icon = {"pending": "⏳", "done": "✅", "cancelled": "❌"}
    text = "📦 <b>Oxirgi buyurtmalar</b>\n\n" + ("\n".join(
        f"{icon.get(o['status'], '•')} <b>#{o['id']}</b> {e(o['game'])} • {e(o['title'])} • {fmt(o['price'])}"
        for o in rows) if rows else "Hozircha buyurtmalar yo'q.")
    await show(c, text, kb([[B("🎮 Xarid qilish", "buy", G)], [B("⬅️ Menyu", "menu")]]))


@r.callback_query(F.data == "toplist")
async def toplist(c: CallbackQuery):
    await c.answer()
    rows = await many("SELECT name, spent FROM users WHERE spent>0 ORDER BY spent DESC LIMIT 10")
    medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
    text = "🏆 <b>Top xaridorlar</b>\n\n" + ("\n".join(
        f"{medals[i]} {e(u['name'])[:18]} — {fmt(u['spent'])}" for i, u in enumerate(rows))
        if rows else "Hali xaridlar yo'q.")
    await show(c, text, kb([[B("⬅️ Menyu", "menu")]]))


# ═══════════════════════ HISOB TO'LDIRISH ═══════════════════════
@r.callback_query(F.data == "top")
async def topup(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await state.set_state(S.top_amount)
    mn = int(await gs("min_topup"))
    rows = [[B(fmt(a), f"tamt:{a}", G) for a in (10000, 25000)],
            [B(fmt(a), f"tamt:{a}", G) for a in (50000, 100000)],
            [B("⬅️ Menyu", "menu")]]
    await show(c, f"➕ <b>Hisob to'ldirish</b>\n\nSummani tanlang yoki o'zingiz yozing.\n"
                  f"⬇️ Minimal: <b>{fmt(mn)}</b>", kb(rows))


async def ask_receipt(ev, state, amount):
    mn = int(await gs("min_topup"))
    if amount < mn:
        return await show(ev, f"❌ Minimal summa {fmt(mn)}. Qayta yozing.")
    await state.set_state(S.top_receipt)
    await state.update_data(amount=amount)
    await show(ev, f"💳 <b>To'lov ma'lumotlari</b>\n\nKarta: <code>{e(await gs('card_number'))}</code>\n"
                   f"Egasi: <b>{e(await gs('card_owner'))}</b>\nSumma: <b>{fmt(amount)}</b>\n\n"
                   f"Pulni o'tkazing va <b>chek rasmini</b> (skrinshot) shu yerga yuboring 👇",
               kb([[B("❌ Bekor qilish", "menu", R)]]))


@r.callback_query(F.data.startswith("tamt:"))
async def tamt(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await ask_receipt(c, state, int(c.data[5:]))


@r.message(S.top_amount)
async def top_amount(m: Message, state: FSMContext):
    try:
        amount = int((m.text or "").replace(" ", ""))
    except ValueError:
        return await m.answer("❌ Faqat raqam yuboring. Masalan: 50000")
    await ask_receipt(m, state, amount)


@r.message(S.top_receipt, F.photo)
async def top_receipt(m: Message, state: FSMContext):
    d = await state.get_data()
    cur = await ex("INSERT INTO topups(user_id,amount,created) VALUES(?,?,?)",
                   (m.from_user.id, d["amount"], int(time.time())))
    tid = cur.lastrowid
    await state.clear()
    await m.answer(f"✅ Chek qabul qilindi (#{tid}).\n⏳ Admin tekshirgach hisobingiz to'ldiriladi.",
                   reply_markup=kb([[B("⬅️ Menyu", "menu")]]))
    u = m.from_user
    await notify_admins(f"💳 <b>Yangi to'ldirish #{tid}</b>\n\n👤 {e(u.full_name)} (@{e(u.username)}) • <code>{u.id}</code>\n"
                        f"💵 Summa: <b>{fmt(d['amount'])}</b>",
                        kb([[B("✅ Tasdiqlash", f"tup_ok:{tid}", G), B("❌ Rad etish", f"tup_no:{tid}", R)],
                            [B("💬 Yozish", f"reply:{u.id}", P)]]), photo=m.photo[-1].file_id)


@r.message(S.top_receipt)
async def top_receipt_bad(m: Message):
    await m.answer("📸 Iltimos, to'lov chekini <b>rasm</b> ko'rinishida yuboring.")


# ═══════════════════════ REFERAL / PROMO / BONUS ═══════════════════════
@r.callback_query(F.data == "ref")
async def referral(c: CallbackQuery):
    await c.answer()
    me = await bot.get_me()
    u = await one("SELECT ref_earn FROM users WHERE id=?", (c.from_user.id,))
    cnt = (await one("SELECT COUNT(*) n FROM users WHERE ref_by=?", (c.from_user.id,)))["n"]
    paid = (await one("SELECT COUNT(*) n FROM users WHERE ref_by=? AND ref_paid=1", (c.from_user.id,)))["n"]
    bonus = int(await gs("ref_bonus"))
    link = f"https://t.me/{me.username}?start=ref_{c.from_user.id}"
    await show(c, f"👥 <b>Referal tizimi</b>\n\nDo'stingiz sizning havolangiz orqali kirib, hisobini birinchi marta "
                  f"to'ldirsa — sizga <b>{fmt(bonus)}</b> bonus!\n\n🔗 Havolangiz:\n<code>{link}</code>\n\n"
                  f"👤 Taklif qilinganlar: <b>{cnt}</b>\n✅ Faol (to'ldirgan): <b>{paid}</b>\n"
                  f"💰 Topilgan bonus: <b>{fmt(u['ref_earn'])}</b>",
               kb([[B("📤 Ulashish", url=f"https://t.me/share/url?url={link}", style=G)], [B("⬅️ Menyu", "menu")]]))


@r.callback_query(F.data == "promo")
async def promo(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await state.set_state(S.promo)
    await show(c, f"{pe('🎁')} <b>Promokodni yuboring:</b>", kb([[B("⬅️ Menyu", "menu")]]))


@r.message(S.promo)
async def promo_in(m: Message, state: FSMContext):
    code = (m.text or "").strip().upper()
    p = await one("SELECT * FROM promos WHERE code=?", (code,))
    back = kb([[B("⬅️ Menyu", "menu")]])
    if not p or p["uses_left"] <= 0:
        return await m.answer("❌ Promokod noto'g'ri yoki tugagan. Qayta urinib ko'ring.", reply_markup=back)
    if await one("SELECT 1 FROM promo_used WHERE code=? AND user_id=?", (code, m.from_user.id)):
        await state.clear()
        return await m.answer("⚠️ Siz bu promokodni ishlatgansiz.", reply_markup=back)
    cur = await ex("UPDATE promos SET uses_left=uses_left-1 WHERE code=? AND uses_left>0", (code,))
    if cur.rowcount == 0:
        return await m.answer("❌ Promokod tugagan.", reply_markup=back)
    await ex("INSERT INTO promo_used VALUES(?,?)", (code, m.from_user.id))
    await ex("UPDATE users SET balance=balance+? WHERE id=?", (p["amount"], m.from_user.id))
    await state.clear()
    await m.answer(f"🎉 Promokod faollashtirildi! Hisobingizga <b>{fmt(p['amount'])}</b> qo'shildi.", reply_markup=back)


@r.callback_query(F.data == "daily")
async def daily(c: CallbackQuery):
    amount = int(await gs("daily_bonus") or 0)
    today = time.strftime("%Y-%m-%d")
    u = await one("SELECT last_bonus FROM users WHERE id=?", (c.from_user.id,))
    if amount <= 0:
        return await c.answer("Bonus o'chirilgan", show_alert=True)
    if u["last_bonus"] == today:
        return await c.answer("📅 Bugungi bonusni olgansiz. Ertaga qaytib keling!", show_alert=True)
    await ex("UPDATE users SET balance=balance+?, last_bonus=? WHERE id=?", (amount, today, c.from_user.id))
    await c.answer(f"🎁 +{fmt(amount)} bonus olindi!", show_alert=True)
    await main_menu(c, c.from_user.id, c.from_user.full_name)


# ═══════════════════════ SUPPORT ═══════════════════════
@r.callback_query(F.data == "sup")
async def support(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await state.set_state(S.support)
    un = (await gs("support_username")).lstrip("@")
    rows = []
    if un:
        rows.append([B("👨‍💻 Admin bilan bog'lanish", url=f"https://t.me/{un}", style=P)])
    rows.append([B("⬅️ Menyu", "menu")])
    await show(c, "🆘 <b>Yordam</b>\n\nSavol yoki muammoingizni shu yerga yozing (matn yoki rasm) — "
                  "admin tez orada javob beradi 👇", kb(rows))


@r.message(S.support)
async def support_in(m: Message, state: FSMContext):
    u = m.from_user
    await notify_admins(f"🆘 <b>Yangi murojaat</b>\n👤 {e(u.full_name)} (@{e(u.username)}) • <code>{u.id}</code>",
                        kb([[B("💬 Javob berish", f"reply:{u.id}", G)]]))
    for a in ADMIN_IDS:
        try:
            await m.copy_to(a)
        except Exception:
            pass
    await state.clear()
    await m.answer("✅ Xabaringiz adminga yuborildi. Javobni shu yerda olasiz.",
                   reply_markup=kb([[B("⬅️ Menyu", "menu")]]))


# ═══════════════════════ ADMIN PANEL ═══════════════════════
def admin_kb():
    return kb([
        [B("📊 Statistika", "ast", P), B("⏳ Kutilayotganlar", "apend", P)],
        [B("🎮 O'yinlar va narxlar", "am", G)],
        [B("➕ Hisob qo'shish", "ain:addbal", G), B("➖ Hisob ayirish", "ain:subbal", R)],
        [B("👤 Foydalanuvchi", "ain:user", P), B("🚫 Ban / Unban", "ain:ban", R)],
        [B("📢 Xabar yuborish", "ain:bc", P), B("🎁 Promokod yaratish", "ain:promo", G)],
        [B("⚙️ Sozlamalar", "aset")],
        [B("⬅️ Menyu", "menu")],
    ])


@adm.message(Command("admin"))
async def admin_cmd(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("⚙️ <b>Admin panel</b>", reply_markup=admin_kb())


@adm.callback_query(F.data == "adm")
async def admin_cb(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await state.clear()
    await show(c, "⚙️ <b>Admin panel</b>", admin_kb())


@adm.callback_query(F.data == "ast")
async def stats(c: CallbackQuery):
    await c.answer()
    day = int(time.time()) - 86400
    n = lambda s, a=(): one(s, a)
    users = (await n("SELECT COUNT(*) x FROM users"))["x"]
    new = (await n("SELECT COUNT(*) x FROM users WHERE joined>?", (day,)))["x"]
    bal = (await n("SELECT COALESCE(SUM(balance),0) x FROM users"))["x"]
    pend = (await n("SELECT COUNT(*) x FROM orders WHERE status='pending'"))["x"]
    done = await n("SELECT COUNT(*) x, COALESCE(SUM(price),0) s FROM orders WHERE status='done'")
    tops = (await n("SELECT COALESCE(SUM(amount),0) x FROM topups WHERE status='ok'"))["x"]
    today = await n("SELECT COUNT(*) x, COALESCE(SUM(price),0) s FROM orders WHERE status='done' AND created>?", (day,))
    await show(c, f"📊 <b>Statistika</b>\n\n👥 Foydalanuvchilar: <b>{users}</b> (24 soatda +{new})\n"
                  f"💰 Jami balanslar: <b>{fmt(bal)}</b>\n💳 Tasdiqlangan to'ldirishlar: <b>{fmt(tops)}</b>\n\n"
                  f"⏳ Kutilayotgan buyurtmalar: <b>{pend}</b>\n✅ Bajarilgan: <b>{done['x']}</b> ({fmt(done['s'])})\n"
                  f"📅 24 soatda: <b>{today['x']}</b> ta ({fmt(today['s'])})",
               kb([[B("⬅️ Admin panel", "adm")]]))


@adm.callback_query(F.data == "apend")
async def pending(c: CallbackQuery):
    await c.answer()
    orders = await many("SELECT o.*, u.name, u.username FROM orders o JOIN users u ON u.id=o.user_id "
                        "WHERE o.status='pending' ORDER BY o.id LIMIT 15")
    if not orders:
        return await show(c, "✅ Kutilayotgan buyurtmalar yo'q.", kb([[B("⬅️ Admin panel", "adm")]]))
    await show(c, f"⏳ Kutilayotgan buyurtmalar: <b>{len(orders)}</b> ta (pastda)", kb([[B("⬅️ Admin panel", "adm")]]))
    for o in orders:
        await c.message.answer(
            f"🆕 <b>Buyurtma #{o['id']}</b>\n👤 {e(o['name'])} (@{e(o['username'])}) • <code>{o['user_id']}</code>\n"
            f"🎮 {e(o['game'])} • <b>{e(o['title'])}</b>\n🆔 <code>{e(o['player_id'])}</code>\n💵 {fmt(o['price'])}",
            reply_markup=kb([[B("✅ Bajarildi", f"od:{o['id']}", G), B("❌ Bekor + qaytarish", f"oc:{o['id']}", R)],
                             [B("💬 Mijozga yozish", f"reply:{o['user_id']}", P)]]))


@adm.callback_query(F.data.startswith("od:"))
async def order_done(c: CallbackQuery):
    oid = int(c.data[3:])
    cur = await ex("UPDATE orders SET status='done' WHERE id=? AND status='pending'", (oid,))
    if cur.rowcount == 0:
        return await c.answer("Allaqachon ishlangan", show_alert=True)
    await c.answer("✅")
    o = await one("SELECT * FROM orders WHERE id=?", (oid,))
    await append_status(c, "✅ <b>Bajarildi</b>")
    await safe_send(o["user_id"], f"✅ <b>Buyurtma #{oid} bajarildi!</b>\n🎮 {e(o['game'])} • {e(o['title'])}\n\n"
                                  f"Xaridingiz uchun rahmat! 🙏",
                    kb([[B("🎮 Yana xarid", "buy", G)]]))


@adm.callback_query(F.data.startswith("oc:"))
async def order_cancel(c: CallbackQuery):
    oid = int(c.data[3:])
    cur = await ex("UPDATE orders SET status='cancelled' WHERE id=? AND status='pending'", (oid,))
    if cur.rowcount == 0:
        return await c.answer("Allaqachon ishlangan", show_alert=True)
    await c.answer("❌")
    o = await one("SELECT * FROM orders WHERE id=?", (oid,))
    await ex("UPDATE users SET balance=balance+?, spent=MAX(spent-?,0) WHERE id=?",
             (o["price"], o["price"], o["user_id"]))
    await append_status(c, "❌ <b>Bekor qilindi, pul qaytarildi</b>")
    await safe_send(o["user_id"], f"❌ <b>Buyurtma #{oid} bekor qilindi.</b>\n"
                                  f"💰 {fmt(o['price'])} balansingizga qaytarildi.")


@adm.callback_query(F.data.startswith("tup_ok:"))
async def tup_ok(c: CallbackQuery):
    tid = int(c.data[7:])
    cur = await ex("UPDATE topups SET status='ok' WHERE id=? AND status='pending'", (tid,))
    if cur.rowcount == 0:
        return await c.answer("Allaqachon ishlangan", show_alert=True)
    await c.answer("✅")
    t = await one("SELECT * FROM topups WHERE id=?", (tid,))
    await credit(t["user_id"], t["amount"])
    await append_status(c, "✅ <b>Tasdiqlandi</b>")
    await safe_send(t["user_id"], f"✅ Hisobingiz <b>{fmt(t['amount'])}</b> ga to'ldirildi! 💰",
                    kb([[B("🎮 Xarid qilish", "buy", G)]]))


@adm.callback_query(F.data.startswith("tup_no:"))
async def tup_no(c: CallbackQuery):
    tid = int(c.data[7:])
    cur = await ex("UPDATE topups SET status='no' WHERE id=? AND status='pending'", (tid,))
    if cur.rowcount == 0:
        return await c.answer("Allaqachon ishlangan", show_alert=True)
    await c.answer("❌")
    t = await one("SELECT * FROM topups WHERE id=?", (tid,))
    await append_status(c, "❌ <b>Rad etildi</b>")
    await safe_send(t["user_id"], f"❌ To'ldirish #{tid} rad etildi. Muammo bo'lsa, «Yordam» bo'limiga yozing.")


# ---- O'yinlar va narxlar ----
@adm.callback_query(F.data == "am")
async def am(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await state.clear()
    games = await many("SELECT * FROM games ORDER BY id")
    rows = [[B(f"{'🟢' if g['active'] else '🔴'} {g['emoji']} {g['title']}", f"amg:{g['id']}", P)] for g in games]
    rows.append([B("⬅️ Admin panel", "adm")])
    await show(c, "🎮 <b>O'yinni tanlang</b> (narxlarni o'zgartirish uchun):", kb(rows))


@adm.callback_query(F.data.startswith("amg:"))
async def amg(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await state.clear()
    await amg_view(c, int(c.data[4:]))


async def amg_view(c, gid):
    g = await one("SELECT * FROM games WHERE id=?", (gid,))
    prods = await many("SELECT * FROM products WHERE game_id=? ORDER BY price", (gid,))
    rows = [[B(f"{'🟢' if p['active'] else '🔴'} {p['title']} — {fmt(p['price'])}", f"amp:{p['id']}", P)] for p in prods]
    rows.append([B("➕ Paket qo'shish", f"ain:addprod:{gid}", G)])
    rows.append([B("🔴 O'yinni o'chirish" if g["active"] else "🟢 O'yinni yoqish", f"amtog:{gid}", R if g["active"] else G)])
    rows.append([B("⬅️ Orqaga", "am")])
    await show(c, f"{g['emoji']} <b>{e(g['title'])}</b>\n\nPaketni bosib narxini o'zgartiring:", kb(rows))


@adm.callback_query(F.data.startswith("amtog:"))
async def amtog(c: CallbackQuery, state: FSMContext):
    gid = int(c.data[6:])
    await ex("UPDATE games SET active=1-active WHERE id=?", (gid,))
    await c.answer()
    await amg_view(c, gid)


@adm.callback_query(F.data.startswith("amp:"))
async def amp(c: CallbackQuery):
    await c.answer()
    await amp_view(c, int(c.data[4:]))


async def amp_view(c, pid):
    p = await one("SELECT * FROM products WHERE id=?", (pid,))
    rows = [[B("💵 Narxni o'zgartirish", f"ain:price:{pid}", G), B("✏️ Nomini o'zgartirish", f"ain:name:{pid}", P)],
            [B("🔴 O'chirish (yashirish)" if p["active"] else "🟢 Yoqish", f"ampt:{pid}", R if p["active"] else G),
             B("🗑 Butunlay o'chirish", f"ampd:{pid}", R)],
            [B("⬅️ Orqaga", f"amg:{p['game_id']}")]]
    await show(c, f"📦 <b>{e(p['title'])}</b>\n💵 Narx: <b>{fmt(p['price'])}</b>\n"
                  f"Holat: {'🟢 faol' if p['active'] else '🔴 yashirin'}", kb(rows))


@adm.callback_query(F.data.startswith("ampt:"))
async def ampt(c: CallbackQuery):
    pid = int(c.data[5:])
    await ex("UPDATE products SET active=1-active WHERE id=?", (pid,))
    await c.answer()
    await amp_view(c, pid)


@adm.callback_query(F.data.startswith("ampd:"))
async def ampd(c: CallbackQuery, state: FSMContext):
    pid = int(c.data[5:])
    p = await one("SELECT game_id FROM products WHERE id=?", (pid,))
    await ex("DELETE FROM products WHERE id=?", (pid,))
    await c.answer("🗑 O'chirildi")
    await amg_view(c, p["game_id"])


# ---- Umumiy kiritish (admin) ----
PROMPTS = {
    "price": "💵 Yangi narxni yozing (faqat raqam, so'mda):",
    "name": "✏️ Yangi nomni yozing:",
    "addprod": "➕ Paket qo'shish. Format: <code>Nomi | narx</code>\nMasalan: <code>660 UC | 120000</code>",
    "addbal": "➕ Format: <code>user_id summa</code>\nMasalan: <code>123456789 50000</code>",
    "subbal": "➖ Format: <code>user_id summa</code>\nMasalan: <code>123456789 20000</code>",
    "user": "👤 Foydalanuvchi ID sini yuboring:",
    "ban": "🚫 Ban/Unban qilinadigan foydalanuvchi ID sini yuboring:",
    "bc": "📢 Barcha foydalanuvchilarga yuboriladigan xabarni yuboring (matn/rasm/video):",
    "promo": "🎁 Format: <code>KOD summa soni</code>\nMasalan: <code>YANGI 5000 100</code>",
}


@adm.callback_query(F.data.startswith("ain:"))
async def ain(c: CallbackQuery, state: FSMContext):
    await c.answer()
    parts = c.data.split(":")
    act, tid = parts[1], (int(parts[2]) if len(parts) > 2 else None)
    await state.set_state(S.admin)
    await state.update_data(act=act, id=tid)
    await show(c, PROMPTS[act], kb([[B("❌ Bekor", "adm", R)]]))


@adm.callback_query(F.data.startswith("reply:"))
async def reply_btn(c: CallbackQuery, state: FSMContext):
    await c.answer()
    uid = int(c.data[6:])
    await state.set_state(S.admin)
    await state.update_data(act="reply", id=uid)
    await c.message.answer(f"💬 <code>{uid}</code> ga yuboriladigan xabarni yozing:",
                           reply_markup=kb([[B("❌ Bekor", "adm", R)]]))


@adm.callback_query(F.data == "aset")
async def aset(c: CallbackQuery, state: FSMContext):
    await c.answer()
    await state.clear()
    lines, rows = [], []
    for k, label in SETTING_LABELS.items():
        v = await gs(k)
        lines.append(f"{label}: <b>{e(v) or '—'}</b>")
        rows.append([B(f"✏️ {label}", f"aset:{k}", P)])
    rows.append([B("⬅️ Admin panel", "adm")])
    await show(c, "⚙️ <b>Sozlamalar</b>\n\n" + "\n".join(lines), kb(rows))


@adm.callback_query(F.data.startswith("aset:"))
async def aset_one(c: CallbackQuery, state: FSMContext):
    await c.answer()
    key = c.data[5:]
    await state.set_state(S.admin)
    await state.update_data(act=f"set:{key}", id=None)
    await show(c, f"✏️ {SETTING_LABELS[key]}\n\nHozirgi: <b>{e(await gs(key)) or '—'}</b>\n\nYangi qiymatni yozing:",
               kb([[B("❌ Bekor", "aset", R)]]))


@adm.message(S.admin)
async def admin_input(m: Message, state: FSMContext):
    d = await state.get_data()
    act, tid = d.get("act"), d.get("id")
    txt = (m.text or "").strip()
    back = kb([[B("⬅️ Admin panel", "adm")]])

    if act == "bc":
        users = await many("SELECT id FROM users WHERE banned=0")
        status = await m.answer(f"📤 Yuborilmoqda... (0/{len(users)})")
        ok = 0
        for i, u in enumerate(users, 1):
            try:
                await m.copy_to(u["id"])
                ok += 1
            except Exception:
                pass
            await asyncio.sleep(0.05)
        await state.clear()
        return await status.edit_text(f"✅ Yuborildi: <b>{ok}</b> / {len(users)}", reply_markup=back)

    if act == "reply":
        await state.clear()
        okk = await safe_send(tid, f"📩 <b>Admin javobi:</b>\n\n{e(txt)}", kb([[B("🆘 Javob yozish", "sup", P)]]))
        return await m.answer("✅ Yuborildi" if okk else "❌ Yuborib bo'lmadi (bot bloklangan bo'lishi mumkin)",
                              reply_markup=back)

    try:
        if act == "price":
            await ex("UPDATE products SET price=? WHERE id=?", (int(txt.replace(" ", "")), tid))
            res = "✅ Narx yangilandi"
        elif act == "name":
            await ex("UPDATE products SET title=? WHERE id=?", (txt, tid))
            res = "✅ Nom yangilandi"
        elif act == "addprod":
            name, price = [x.strip() for x in txt.rsplit("|", 1)]
            await ex("INSERT INTO products(game_id,title,price) VALUES(?,?,?)", (tid, name, int(price.replace(" ", ""))))
            res = "✅ Paket qo'shildi"
        elif act in ("addbal", "subbal"):
            uid_s, amt_s = txt.split()
            uid, amt = int(uid_s), int(amt_s)
            if not await one("SELECT 1 FROM users WHERE id=?", (uid,)):
                return await m.answer("❌ Bunday foydalanuvchi topilmadi. Qayta yuboring.")
            if act == "addbal":
                await credit(uid, amt)
                await safe_send(uid, f"✅ Hisobingiz <b>{fmt(amt)}</b> ga to'ldirildi! 💰")
                res = f"✅ {uid} ga {fmt(amt)} qo'shildi"
            else:
                await ex("UPDATE users SET balance=MAX(balance-?,0) WHERE id=?", (amt, uid))
                res = f"✅ {uid} dan {fmt(amt)} ayirildi"
        elif act == "user":
            u = await one("SELECT * FROM users WHERE id=?", (int(txt),))
            if not u:
                return await m.answer("❌ Topilmadi. Qayta yuboring.")
            cnt = (await one("SELECT COUNT(*) n FROM orders WHERE user_id=?", (u["id"],)))["n"]
            await state.clear()
            return await m.answer(
                f"👤 <b>{e(u['name'])}</b> (@{e(u['username'])})\n🆔 <code>{u['id']}</code>\n"
                f"💰 Balans: <b>{fmt(u['balance'])}</b>\n🛒 Xarid: <b>{fmt(u['spent'])}</b> • {cnt} ta\n"
                f"🏅 {level(u['spent'])[1]}\n🚫 Ban: {'ha' if u['banned'] else 'yo`q'}",
                reply_markup=kb([[B("💬 Yozish", f"reply:{u['id']}", P)],
                                 [B("🔓 Unban" if u["banned"] else "🚫 Ban", f"abt:{u['id']}", G if u["banned"] else R)],
                                 [B("⬅️ Admin panel", "adm")]]))
        elif act == "ban":
            uid = int(txt)
            u = await one("SELECT banned FROM users WHERE id=?", (uid,))
            if not u:
                return await m.answer("❌ Topilmadi. Qayta yuboring.")
            await ex("UPDATE users SET banned=1-banned WHERE id=?", (uid,))
            res = "🚫 Ban qilindi" if not u["banned"] else "🔓 Ban olib tashlandi"
        elif act == "promo":
            code, amt, cnt = txt.split()
            await ex("INSERT OR REPLACE INTO promos(code,amount,uses_left) VALUES(?,?,?)", (code.upper(), int(amt), int(cnt)))
            res = f"✅ Promokod <code>{e(code.upper())}</code> yaratildi: {fmt(int(amt))} × {cnt} marta"
        elif act and act.startswith("set:"):
            key = act[4:]
            if key in NUMERIC:
                txt = str(int(txt.replace(" ", "")))
            await ss(key, txt)
            res = "✅ Saqlandi"
        else:
            res = "❌ Noma'lum amal"
    except (ValueError, IndexError):
        return await m.answer("❌ Format noto'g'ri. Qayta yuboring yoki «Bekor» ni bosing.")
    await state.clear()
    await m.answer(res, reply_markup=back)


@adm.callback_query(F.data.startswith("abt:"))
async def ban_toggle(c: CallbackQuery):
    uid = int(c.data[4:])
    await ex("UPDATE users SET banned=1-banned WHERE id=?", (uid,))
    await c.answer("✅ O'zgartirildi", show_alert=True)


# ═══════════════════════ RENDER: HEALTH SERVER ═══════════════════════
async def health(_request):
    return web.Response(text="OK")


async def start_web():
    """Render Web Service port kutadi. Worker'da PORT yo'q, shuning uchun o'zi o'chib turadi."""
    port = os.getenv("PORT")
    if not port:
        return
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(port)).start()
    logging.info("Health server port %s da ishga tushdi", port)


# ═══════════════════════ ISHGA TUSHIRISH ═══════════════════════
async def main():
    global bot
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await init_db()
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.outer_middleware(Guard())
    dp.callback_query.outer_middleware(Guard())
    dp.include_router(adm)   # admin tugmalari birinchi
    dp.include_router(r)
    me = await bot.get_me()
    logging.info("Bot ishga tushdi: @%s", me.username)
    logging.info("Premium emoji: USE_PREMIUM=%s, ID kiritilgan: %d ta",
                 USE_PREMIUM, sum(1 for v in PREMIUM_EMOJI.values() if v))
    await bot.delete_webhook(drop_pending_updates=True)
    await start_web()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
