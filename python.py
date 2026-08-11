import os
import re
import random
import uuid
import sqlite3
import logging
import threading
import hashlib
import secrets
import json
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MessageEntity,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================================================
# НАСТРОЙКИ
# =========================================================

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])

# Ключ от твоего поставщика заказов.
# Партнёры этот ключ НЕ получают.
ELDER_API_KEY = os.environ["ELDER_API_KEY"]
ELDER_API_URL = os.environ.get(
    "ELDER_API_URL",
    "https://asosiy.elder.uz/api",
).rstrip("/")

DB_FILE = "bot_database.db"

CARD_NUMBER = os.environ.get(
    "CARD_NUMBER",
    "5614 6835 8985 1641",
)

PRICE_PER_STAR = 210

PREMIUM_PRICES = {
    3: 165000,
    6: 222000,
    12: 406000,
}

# Партнёрский API:
# GET  /api/v1/balance
# POST /api/v1/order
# Header: X-Partner-Key: sp_live_...
API_PREFIX = "/api/v1"

# =========================================================
# ЛОГИ
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# =========================================================
# СОСТОЯНИЯ
# =========================================================

REFILL_AMOUNT = 1
REFILL_CHECK = 2

BUY_AMOUNT = 3
BUY_USERNAME = 4
BUY_CONFIRM = 5

GIFT_SEND_TYPE = 6
GIFT_TEXT = 7
GIFT_USERNAME = 8

ADMIN_ADD_ID = 9
ADMIN_ADD_AMOUNT = 10
ADMIN_SUB_ID = 11
ADMIN_SUB_AMOUNT = 12

ADMIN_BAN_ID = 13
ADMIN_UNBAN_ID = 14

ADMIN_MESSAGE_ID = 15
ADMIN_MESSAGE_TEXT = 16

ADMIN_PARTNER_CREATE_NAME = 17
ADMIN_PARTNER_BALANCE_ID = 18
ADMIN_PARTNER_BALANCE_AMOUNT = 19
ADMIN_PARTNER_REVOKE_ID = 20

# =========================================================
# ПОДАРКИ
# =========================================================

GIFTS = {
    1: {
        "emoji": "🧸",
        "emoji_id": "5397971251878732060",
        "price": 4000,
        "stars": 15,
        "name": "Мишка",
    },
    2: {
        "emoji": "💝",
        "emoji_id": "5283228279988309088",
        "price": 4000,
        "stars": 15,
        "name": "Сердце",
    },
    3: {
        "emoji": "🌹",
        "emoji_id": "5280947338821524402",
        "price": 6000,
        "stars": 25,
        "name": "Роза",
    },
    4: {
        "emoji": "🎁",
        "emoji_id": "5280615440928758599",
        "price": 6000,
        "stars": 25,
        "name": "Подарок",
    },
    5: {
        "emoji": "🚀",
        "emoji_id": "5283080528818360566",
        "price": 10500,
        "stars": 50,
        "name": "Ракета",
    },
    6: {
        "emoji": "🎂",
        "emoji_id": "5280659198055572187",
        "price": 10500,
        "stars": 50,
        "name": "Торт",
    },
    7: {
        "emoji": "💐",
        "emoji_id": "5280774333243873175",
        "price": 10500,
        "stars": 50,
        "name": "Букет",
    },
    8: {
        "emoji": "🍾",
        "emoji_id": "5451905784734574339",
        "price": 10500,
        "stars": 50,
        "name": "Шампанское",
    },
    9: {
        "emoji": "💍",
        "emoji_id": "5280651583078556009",
        "price": 21000,
        "stars": 100,
        "name": "Кольцо",
    },
    10: {
        "emoji": "💎",
        "emoji_id": "5280922999241859582",
        "price": 21000,
        "stars": 100,
        "name": "Алмаз",
    },
    11: {
        "emoji": "🏆",
        "emoji_id": "5280769763398671636",
        "price": 21000,
        "stars": 100,
        "name": "Кубок",
    },
}

# =========================================================
# ЯЗЫКИ
# =========================================================

TEXTS = {
    "ru": {
        "welcome": (
            "👋 Привет, {name}!\n\n"
            "Добро пожаловать в магазин.\n\n"
            "💰 Баланс: {balance:,} сум"
        ),
        "services": "🛍 Услуги",
        "refill": "💳 Пополнить баланс",
        "language": "🌐 Язык",
        "back": "⬅️ Назад",
        "shop": "🛍 <b>Выберите услугу:</b>",
        "stars": (
            "💎 <b>Telegram Stars</b>\n\n"
            "💰 Цена: {price:,} сум за 1 Stars"
        ),
        "premium": (
            "🌟 <b>Telegram Premium</b>\n\n"
            "Выберите срок подписки:"
        ),
        "gifts": (
            "🎁 <b>Выберите подарок:</b>\n\n"
            "Цена указана в сумах."
        ),
        "enter_stars": (
            "✏️ Введите количество Stars.\n\n"
            "Минимум: 50\n"
            "Максимум: 10000"
        ),
        "enter_username": (
            "✏️ Введите юзернейм получателя.\n\n"
            "Без символа @"
        ),
        "not_enough": (
            "❌ Недостаточно средств.\n\n"
            "💰 Нужно: {price:,} сум\n"
            "💳 Баланс: {balance:,} сум"
        ),
        "processing": "🔄 Обрабатываем заказ...",
        "api_error": (
            "❌ Не удалось выполнить заказ.\n\n"
            "Попробуйте ещё раз позже."
        ),
        "cancelled": "❌ Действие отменено.",
        "refill_enter": (
            "💳 Введите сумму пополнения в сумах.\n\n"
            "Например: 50000"
        ),
        "refill_payment": (
            "💳 <b>Пополнение баланса</b>\n\n"
            "💰 Сумма для перевода: {amount:,} сум\n\n"
            "Переведите деньги на карту:\n"
            "<code>{card}</code>\n\n"
            "После оплаты ничего дополнительно отправлять не нужно.\n"
            "Баланс зачислится автоматически после получения SMS."
        ),
        "receipt_sent": "⏳ Чек отправлен администратору.",
        "send_receipt": "❌ Отправьте фото чека.",
        "gift_send_type": "🎁 <b>Как отправить подарок?</b>",
        "gift_text": "✍️ Напишите текст для подарка.",
        "gift_username": (
            "✏️ Введите юзернейм получателя подарка.\n\n"
            "Без символа @"
        ),
        "gift_success": (
            "✅ Заявка на подарок принята!\n\n"
            "Мы обработаем заказ."
        ),
        "confirm_order": (
            "🛒 <b>Проверьте заказ</b>\n\n"
            "📦 Товар: {product}\n"
            "👤 Получатель: @{username}\n"
            "💰 Цена: {price:,} сум\n\n"
            "Подтвердить покупку?"
        ),
    },
    "uz": {
        "welcome": (
            "👋 Salom, {name}!\n\n"
            "Do'konimizga xush kelibsiz.\n\n"
            "💰 Balans: {balance:,} so'm"
        ),
        "services": "🛍 Xizmatlar",
        "refill": "💳 Balansni to'ldirish",
        "language": "🌐 Til",
        "back": "⬅️ Orqaga",
        "shop": "🛍 <b>Xizmatni tanlang:</b>",
        "stars": (
            "💎 <b>Telegram Stars</b>\n\n"
            "💰 Narx: 1 Stars — {price:,} so'm"
        ),
        "premium": (
            "🌟 <b>Telegram Premium</b>\n\n"
            "Muddatni tanlang:"
        ),
        "gifts": (
            "🎁 <b>Sovg'ani tanlang:</b>\n\n"
            "Narx so'mda ko'rsatilgan."
        ),
        "enter_stars": (
            "✏️ Stars miqdorini kiriting.\n\n"
            "Minimum: 50\n"
            "Maksimum: 10000"
        ),
        "enter_username": (
            "✏️ Qabul qiluvchining username'ini kiriting.\n\n"
            "@ belgisiz"
        ),
        "not_enough": (
            "❌ Balans yetarli emas.\n\n"
            "💰 Kerak: {price:,} so'm\n"
            "💳 Balans: {balance:,} so'm"
        ),
        "processing": "🔄 Buyurtma bajarilmoqda...",
        "api_error": "❌ Buyurtmani bajarib bo'lmadi.",
        "cancelled": "❌ Bekor qilindi.",
        "refill_enter": (
            "💳 To'ldirish summasini so'mda kiriting.\n\n"
            "Masalan: 50000"
        ),
        "refill_payment": (
            "💳 <b>Balansni to'ldirish</b>\n\n"
            "💰 O'tkazma summasi: {amount:,} so'm\n\n"
            "Kartaga pul o'tkazing:\n"
            "<code>{card}</code>\n\n"
            "SMS kelgach balans avtomatik to'ldiriladi."
        ),
        "receipt_sent": "⏳ Chek administratorga yuborildi.",
        "send_receipt": "❌ Chek rasmini yuboring.",
        "gift_send_type": "🎁 <b>Sovg'a qanday yuborilsin?</b>",
        "gift_text": "✍️ Sovg'aga qo'shiladigan matnni yozing.",
        "gift_username": (
            "✏️ Qabul qiluvchining username'ini kiriting.\n\n"
            "@ belgisiz"
        ),
        "gift_success": "✅ <b>Sovg'a buyurtmasi qabul qilindi!</b>",
        "confirm_order": (
            "🛒 <b>Buyurtmani tekshiring</b>\n\n"
            "📦 Mahsulot: {product}\n"
            "👤 Qabul qiluvchi: @{username}\n"
            "💰 Narx: {price:,} so'm\n\n"
            "Xaridni tasdiqlaysizmi?"
        ),
    },
}

# =========================================================
# DATABASE
# =========================================================

def db_connect():
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            name TEXT,
            balance INTEGER DEFAULT 0,
            lang TEXT DEFAULT 'ru',
            is_banned INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_refills (
            amount INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL
        )
    """)

    # Партнёры. Сам API-ключ в БД не хранится в открытом виде.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS partners (
            partner_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            owner_user_id INTEGER,
            key_hash TEXT UNIQUE NOT NULL,
            key_prefix TEXT NOT NULL,
            balance INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS partner_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            partner_id INTEGER NOT NULL,
            order_id TEXT UNIQUE NOT NULL,
            product_type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            username TEXT NOT NULL,
            price INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def get_user(user_id, username="", name=""):
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT username, name, balance, lang, is_banned
        FROM users
        WHERE user_id = ?
    """, (user_id,))

    row = cursor.fetchone()

    if row is None:
        cursor.execute("""
            INSERT INTO users
            (user_id, username, name, balance, lang, is_banned)
            VALUES (?, ?, ?, 0, 'ru', 0)
        """, (user_id, username or "", name or ""))
        conn.commit()

        result = {
            "username": username or "",
            "name": name or "",
            "balance": 0,
            "lang": "ru",
            "is_banned": False,
        }
    else:
        old_username, old_name, balance, lang, is_banned = row

        cursor.execute("""
            UPDATE users
            SET username = ?, name = ?
            WHERE user_id = ?
        """, (
            username or old_username or "",
            name or old_name or "",
            user_id,
        ))
        conn.commit()

        result = {
            "username": username or old_username or "",
            "name": name or old_name or "",
            "balance": balance,
            "lang": lang or "ru",
            "is_banned": bool(is_banned),
        }

    conn.close()
    return result


def set_language(user_id, lang):
    conn = db_connect()
    conn.execute(
        "UPDATE users SET lang = ? WHERE user_id = ?",
        (lang, user_id),
    )
    conn.commit()
    conn.close()


def change_balance(user_id, amount):
    conn = db_connect()
    conn.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (amount, user_id),
    )
    conn.commit()
    conn.close()


def set_ban(user_id, value):
    conn = db_connect()
    conn.execute(
        "UPDATE users SET is_banned = ? WHERE user_id = ?",
        (value, user_id),
    )
    conn.commit()
    conn.close()


def get_users():
    conn = db_connect()
    rows = conn.execute("""
        SELECT user_id, username, name, balance, lang, is_banned
        FROM users
        ORDER BY user_id DESC
    """).fetchall()
    conn.close()
    return rows


def tr(user_id, key, **kwargs):
    data = get_user(user_id)
    lang = data.get("lang", "ru")
    text = TEXTS.get(lang, TEXTS["ru"]).get(key, key)
    return text.format(**kwargs)


# =========================================================
# PARTNER API KEY SYSTEM
# =========================================================

def hash_api_key(api_key):
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def generate_partner_key():
    # 32 байта случайности = сильный непредсказуемый токен.
    # Используем secrets, а не random.
    return "sp_live_" + secrets.token_urlsafe(32)


def create_partner(name, owner_user_id=None):
    api_key = generate_partner_key()
    key_hash = hash_api_key(api_key)
    key_prefix = api_key[:18]

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO partners
        (name, owner_user_id, key_hash, key_prefix, balance, is_active)
        VALUES (?, ?, ?, ?, 0, 1)
    """, (
        name,
        owner_user_id,
        key_hash,
        key_prefix,
    ))

    partner_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Полный ключ возвращается только в момент создания.
    return partner_id, api_key


def get_partner_by_key(api_key):
    if not api_key:
        return None

    key_hash = hash_api_key(api_key)

    conn = db_connect()
    row = conn.execute("""
        SELECT partner_id, name, owner_user_id, balance, is_active, created_at
        FROM partners
        WHERE key_hash = ?
    """, (key_hash,)).fetchone()
    conn.close()

    if not row:
        return None

    return {
        "partner_id": row[0],
        "name": row[1],
        "owner_user_id": row[2],
        "balance": row[3],
        "is_active": bool(row[4]),
        "created_at": row[5],
    }


def get_partner(partner_id):
    conn = db_connect()
    row = conn.execute("""
        SELECT partner_id, name, owner_user_id, balance,
               is_active, created_at, key_prefix
        FROM partners
        WHERE partner_id = ?
    """, (partner_id,)).fetchone()
    conn.close()

    if not row:
        return None

    return {
        "partner_id": row[0],
        "name": row[1],
        "owner_user_id": row[2],
        "balance": row[3],
        "is_active": bool(row[4]),
        "created_at": row[5],
        "key_prefix": row[6],
    }


def get_partners():
    conn = db_connect()
    rows = conn.execute("""
        SELECT partner_id, name, owner_user_id, balance,
               is_active, created_at, key_prefix
        FROM partners
        ORDER BY partner_id DESC
    """).fetchall()
    conn.close()
    return rows


def change_partner_balance(partner_id, amount):
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE partners
        SET balance = balance + ?
        WHERE partner_id = ?
    """, (amount, partner_id))

    conn.commit()
    conn.close()


def set_partner_active(partner_id, active):
    conn = db_connect()
    conn.execute("""
        UPDATE partners
        SET is_active = ?
        WHERE partner_id = ?
    """, (1 if active else 0, partner_id))
    conn.commit()
    conn.close()


def debit_partner_if_possible(partner_id, amount):
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE partners
        SET balance = balance - ?
        WHERE partner_id = ?
          AND is_active = 1
          AND balance >= ?
    """, (amount, partner_id, amount))

    success = cursor.rowcount == 1
    conn.commit()
    conn.close()
    return success


# =========================================================
# ПРОВЕРКА БАНА
# =========================================================

async def check_ban(update):
    user = update.effective_user
    if not user:
        return False

    data = get_user(
        user.id,
        user.username,
        user.first_name,
    )

    if data["is_banned"]:
        if update.message:
            await update.message.reply_text("❌ Вы заблокированы.")
        elif update.callback_query:
            await update.callback_query.answer(
                "❌ Вы заблокированы.",
                show_alert=True,
            )
        return True

    return False


# =========================================================
# ELDER API — ТОЛЬКО ТВОЙ ВНУТРЕННИЙ КЛЮЧ
# =========================================================

async def send_order_to_elder(product_type, value, target):
    order_id = uuid.uuid4().hex[:16]

    headers = {
        "X-Api-Key": ELDER_API_KEY,
        "Content-Type": "application/json",
    }

    if product_type == "stars":
        url = f"{ELDER_API_URL}/stars/buy"
        payload = {
            "username": target,
            "amount": value,
            "client_order_id": order_id,
        }
    elif product_type == "premium":
        url = f"{ELDER_API_URL}/premium/buy"
        payload = {
            "username": target,
            "months": value,
            "client_order_id": order_id,
        }
    else:
        return False, "unsupported_product"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
            )

        logger.info(
            "PROVIDER RESPONSE %s: %s",
            response.status_code,
            response.text,
        )

        if response.status_code != 200:
            return False, f"http_{response.status_code}"

        data = response.json()
        return bool(data.get("success")), data

    except Exception as exc:
        logger.exception("PROVIDER API ERROR: %s", exc)
        return False, "provider_error"


# =========================================================
# RENDER WEB + PARTNER API
# =========================================================

def json_response(handler, status_code, payload):
    body = json.dumps(
        payload,
        ensure_ascii=False,
    ).encode("utf-8")

    handler.send_response(status_code)
    handler.send_header(
        "Content-Type",
        "application/json; charset=utf-8",
    )
    handler.send_header(
        "Content-Length",
        str(len(body)),
    )
    handler.end_headers()
    handler.wfile.write(body)


def get_request_api_key(handler):
    key = handler.headers.get("X-Partner-Key", "").strip()

    if key:
        return key

    authorization = handler.headers.get(
        "Authorization",
        "",
    ).strip()

    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()

    return ""


def read_json_body(handler):
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        length = 0

    if length <= 0:
        return None

    if length > 100_000:
        return None

    raw = handler.rfile.read(length)

    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def validate_username(username):
    if not isinstance(username, str):
        return False

    username = username.strip().lstrip("@")

    return bool(
        re.fullmatch(
            r"[A-Za-z0-9_]{5,32}",
            username,
        )
    )


def calculate_partner_order(product_type, amount):
    if product_type == "stars":
        if not isinstance(amount, int):
            return None

        if amount < 50 or amount > 10000:
            return None

        return amount * PRICE_PER_STAR

    if product_type == "premium":
        if not isinstance(amount, int):
            return None

        return PREMIUM_PRICES.get(amount)

    return None


class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        logger.info(
            "HTTP %s - %s",
            self.address_string(),
            fmt % args,
        )

    def do_GET(self):
        if self.path == "/":
            body = b"Bot is running!"
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/plain; charset=utf-8",
            )
            self.send_header(
                "Content-Length",
                str(len(body)),
            )
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == f"{API_PREFIX}/balance":
            self.api_balance()
            return

        if self.path == f"{API_PREFIX}/health":
            json_response(
                self,
                200,
                {
                    "success": True,
                    "service": "StarPay Partner API",
                    "status": "online",
                },
            )
            return

        json_response(
            self,
            404,
            {
                "success": False,
                "error": "not_found",
            },
        )

    def do_POST(self):
        if self.path == f"{API_PREFIX}/order":
            self.api_order()
            return

        json_response(
            self,
            404,
            {
                "success": False,
                "error": "not_found",
            },
        )

    def api_balance(self):
        api_key = get_request_api_key(self)
        partner = get_partner_by_key(api_key)

        if not partner or not partner["is_active"]:
            json_response(
                self,
                401,
                {
                    "success": False,
                    "error": "invalid_or_inactive_api_key",
                },
            )
            return

        json_response(
            self,
            200,
            {
                "success": True,
                "partner_id": partner["partner_id"],
                "balance": partner["balance"],
                "currency": "UZS",
            },
        )

    def api_order(self):
        api_key = get_request_api_key(self)
        partner = get_partner_by_key(api_key)

        if not partner or not partner["is_active"]:
            json_response(
                self,
                401,
                {
                    "success": False,
                    "error": "invalid_or_inactive_api_key",
                },
            )
            return

        payload = read_json_body(self)

        if not isinstance(payload, dict):
            json_response(
                self,
                400,
                {
                    "success": False,
                    "error": "invalid_json",
                },
            )
            return

        product_type = payload.get("type")
        amount = payload.get("amount")
        username = str(
            payload.get("username", "")
        ).strip().lstrip("@")

        if product_type not in ("stars", "premium"):
            json_response(
                self,
                400,
                {
                    "success": False,
                    "error": "type_must_be_stars_or_premium",
                },
            )
            return

        if not validate_username(username):
            json_response(
                self,
                400,
                {
                    "success": False,
                    "error": "invalid_username",
                },
            )
            return

        # JSON иногда передаёт 100 как float.
        if isinstance(amount, bool):
            amount = None
        elif isinstance(amount, float) and amount.is_integer():
            amount = int(amount)

        price = calculate_partner_order(
            product_type,
            amount,
        )

        if price is None:
            json_response(
                self,
                400,
                {
                    "success": False,
                    "error": "invalid_amount",
                    "hint": {
                        "stars": "50..10000",
                        "premium": [3, 6, 12],
                    },
                },
            )
            return

        # Атомарно резервируем деньги партнёра.
        if not debit_partner_if_possible(
            partner["partner_id"],
            price,
        ):
            fresh = get_partner(partner["partner_id"])

            json_response(
                self,
                402,
                {
                    "success": False,
                    "error": "insufficient_partner_balance",
                    "balance": (
                        fresh["balance"]
                        if fresh
                        else 0
                    ),
                    "required": price,
                },
            )
            return

        provider_success, provider_result = (
            self.run_provider_order(
                product_type,
                amount,
                username,
            )
        )

        if not provider_success:
            # Если поставщик отказал заказ — возвращаем деньги партнёру.
            change_partner_balance(
                partner["partner_id"],
                price,
            )

            json_response(
                self,
                502,
                {
                    "success": False,
                    "error": "provider_order_failed",
                    "refunded": True,
                },
            )
            return

        order_id = uuid.uuid4().hex[:16]

        conn = db_connect()
        conn.execute("""
            INSERT INTO partner_orders
            (partner_id, order_id, product_type, amount,
             username, price, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            partner["partner_id"],
            order_id,
            product_type,
            amount,
            username,
            price,
            "completed",
        ))
        conn.commit()
        conn.close()

        fresh = get_partner(partner["partner_id"])

        # Уведомляем администратора.
        try:
            from telegram import Bot
            # Здесь синхронный HTTP handler, поэтому уведомление
            # делаем отдельным async runner ниже через очередь.
            schedule_admin_notification({
                "type": "partner_order",
                "partner_id": partner["partner_id"],
                "partner_name": partner["name"],
                "product_type": product_type,
                "amount": amount,
                "username": username,
                "price": price,
                "order_id": order_id,
            })
        except Exception:
            logger.exception(
                "Could not schedule admin notification"
            )

        json_response(
            self,
            200,
            {
                "success": True,
                "order_id": order_id,
                "type": product_type,
                "amount": amount,
                "username": username,
                "price": price,
                "currency": "UZS",
                "balance": (
                    fresh["balance"]
                    if fresh
                    else None
                ),
            },
        )

    def run_provider_order(
        self,
        product_type,
        amount,
        username,
    ):
        # Handler работает в обычном HTTP-потоке,
        # поэтому запускаем async API-вызов в новом event loop.
        import asyncio

        return asyncio.run(
            send_order_to_elder(
                product_type,
                amount,
                username,
            )
        )


# Telegram Application назначается после создания.
TELEGRAM_APPLICATION = None


def schedule_admin_notification(data):
    global TELEGRAM_APPLICATION

    if TELEGRAM_APPLICATION is None:
        return

    async def send():
        if data["type"] == "partner_order":
            text = (
                "🤝 <b>НОВЫЙ ПАРТНЁРСКИЙ ЗАКАЗ</b>\n\n"
                f"🔑 Партнёр: <b>{escape(data['partner_name'])}</b>\n"
                f"🆔 Partner ID: <code>{data['partner_id']}</code>\n\n"
                f"📦 Тип: <b>{escape(data['product_type'])}</b>\n"
                f"🔢 Количество: <b>{data['amount']}</b>\n"
                f"👤 Получатель: @{escape(data['username'])}\n"
                f"💰 Цена: <b>{data['price']:,} сум</b>\n"
                f"🧾 Order ID: <code>{data['order_id']}</code>"
            )

            await TELEGRAM_APPLICATION.bot.send_message(
                ADMIN_ID,
                text,
                parse_mode="HTML",
            )

    try:
        loop = TELEGRAM_APPLICATION.bot._request._get_loop()
        asyncio_future = asyncio.run_coroutine_threadsafe(
            send(),
            loop,
        )
        asyncio_future.result(timeout=10)
    except Exception:
        # В разных версиях PTB внутренний loop может отличаться.
        # Ошибка уведомления не ломает API-заказ.
        logger.exception(
            "Partner admin notification failed"
        )


def run_web():
    port = int(os.environ.get("PORT", 8080))

    server = ThreadingHTTPServer(
        ("0.0.0.0", port),
        Handler,
    )

    logger.info(
        "WEB/API SERVER STARTED ON PORT %s",
        port,
    )

    server.serve_forever()


# =========================================================
# ГЛАВНОЕ МЕНЮ
# =========================================================

def main_keyboard(user_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                tr(user_id, "services"),
                callback_data="main_shop",
            )
        ],
        [
            InlineKeyboardButton(
                tr(user_id, "refill"),
                callback_data="main_refill",
            ),
            InlineKeyboardButton(
                "👤 Профиль",
                callback_data="main_profile",
            ),
        ],
        [
            InlineKeyboardButton(
                tr(user_id, "language"),
                callback_data="language_menu",
            )
        ],
    ])


# =========================================================
# START
# =========================================================

async def start(update, context):
    context.user_data.clear()

    if await check_ban(update):
        return ConversationHandler.END

    user = update.effective_user

    data = get_user(
        user.id,
        user.username,
        user.first_name,
    )

    await update.message.reply_text(
        tr(
            user.id,
            "welcome",
            name=user.first_name,
            balance=data["balance"],
        ),
        reply_markup=main_keyboard(user.id),
        parse_mode="HTML",
    )


# =========================================================
# ПРОФИЛЬ
# =========================================================

async def profile_callback(update, context):
    query = update.callback_query
    await query.answer()

    user = query.from_user

    data = get_user(
        user.id,
        user.username,
        user.first_name,
    )

    username = user.username or "нет username"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                tr(user.id, "back"),
                callback_data="back_main",
            )
        ]
    ])

    text = (
        "👤 <b>Мой профиль</b>\n\n"
        f"👤 Username: @{escape(username)}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"💰 Баланс: <b>{data['balance']:,} сум</b>"
    )

    await query.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )


# =========================================================
# ГЛАВНЫЕ КНОПКИ
# =========================================================

async def main_buttons(update, context):
    if await check_ban(update):
        return

    query = update.callback_query
    await query.answer()

    user = query.from_user

    data = get_user(
        user.id,
        user.username,
        user.first_name,
    )

    if query.data == "back_main":
        await query.message.edit_text(
            tr(
                user.id,
                "welcome",
                name=user.first_name,
                balance=data["balance"],
            ),
            reply_markup=main_keyboard(user.id),
            parse_mode="HTML",
        )
        return

    if query.data == "language_menu":
        keyboard = [
            [
                InlineKeyboardButton(
                    "🇷🇺 Русский",
                    callback_data="lang_ru",
                )
            ],
            [
                InlineKeyboardButton(
                    "🇺🇿 O'zbekcha",
                    callback_data="lang_uz",
                )
            ],
            [
                InlineKeyboardButton(
                    tr(user.id, "back"),
                    callback_data="back_main",
                )
            ],
        ]

        await query.message.edit_text(
            "🌐 <b>Выберите язык / Tilni tanlang</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
        return

    if query.data == "main_shop":
        keyboard = [
            [
                InlineKeyboardButton(
                    "💎 Stars",
                    callback_data="shop_stars",
                )
            ],
            [
                InlineKeyboardButton(
                    "🌟 Premium",
                    callback_data="shop_premium",
                )
            ],
            [
                InlineKeyboardButton(
                    "🎁 Подарки",
                    callback_data="shop_gifts",
                )
            ],
            [
                InlineKeyboardButton(
                    "📱 Аккаунты",
                    callback_data="shop_accounts",
                )
            ],
            [
                InlineKeyboardButton(
                    tr(user.id, "back"),
                    callback_data="back_main",
                )
            ],
        ]

        await query.message.edit_text(
            tr(user.id, "shop"),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
        return

    if query.data == "shop_stars":
        keyboard = [
            [
                InlineKeyboardButton(
                    "50 Stars — 10 500 сум",
                    callback_data="buy_stars_50",
                )
            ],
            [
                InlineKeyboardButton(
                    "100 Stars — 21 000 сум",
                    callback_data="buy_stars_100",
                )
            ],
            [
                InlineKeyboardButton(
                    "✏️ Ввести количество",
                    callback_data="buy_stars",
                )
            ],
            [
                InlineKeyboardButton(
                    tr(user.id, "back"),
                    callback_data="main_shop",
                )
            ],
        ]

        await query.message.edit_text(
            tr(
                user.id,
                "stars",
                price=PRICE_PER_STAR,
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
        return

    if query.data == "shop_premium":
        keyboard = [
            [
                InlineKeyboardButton(
                    "3 месяца — 165 000 сум",
                    callback_data="buy_premium_3",
                )
            ],
            [
                InlineKeyboardButton(
                    "6 месяцев — 222 000 сум",
                    callback_data="buy_premium_6",
                )
            ],
            [
                InlineKeyboardButton(
                    "12 месяцев — 406 000 сум",
                    callback_data="buy_premium_12",
                )
            ],
            [
                InlineKeyboardButton(
                    tr(user.id, "back"),
                    callback_data="main_shop",
                )
            ],
        ]

        await query.message.edit_text(
            tr(user.id, "premium"),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
        return

    if query.data == "shop_gifts":
        keyboard = []

        for gift_id, gift in GIFTS.items():
            keyboard.append([
                InlineKeyboardButton(
                    f"{gift['emoji']} — {gift['price']:,} сум",
                    callback_data=f"gift_{gift_id}",
                )
            ])

        keyboard.append([
            InlineKeyboardButton(
                tr(user.id, "back"),
                callback_data="main_shop",
            )
        ])

        await query.message.edit_text(
            tr(user.id, "gifts"),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
        return

    if query.data == "shop_accounts":
        keyboard = [
            [
                InlineKeyboardButton(
                    "🇺🇿 Узбекистан",
                    callback_data="account_uz",
                )
            ],
            [
                InlineKeyboardButton(
                    "🇨🇴 Колумбия",
                    callback_data="account_co",
                )
            ],
            [
                InlineKeyboardButton(
                    "🇬🇧 Великобритания",
                    callback_data="account_uk",
                )
            ],
            [
                InlineKeyboardButton(
                    "🇺🇸 Америка",
                    callback_data="account_us",
                )
            ],
            [
                InlineKeyboardButton(
                    tr(user.id, "back"),
                    callback_data="main_shop",
                )
            ],
        ]

        await query.message.edit_text(
            "📱 <b>Выберите страну аккаунта:</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
        return

    if query.data.startswith("account_"):
        countries = {
            "account_uz": "Узбекистан",
            "account_co": "Колумбия",
            "account_uk": "Великобритания",
            "account_us": "Америка",
        }

        country = countries.get(
            query.data,
            "Неизвестная страна",
        )

        await context.bot.send_message(
            ADMIN_ID,
            (
                "📱 <b>НОВЫЙ ЗАКАЗ АККАУНТА</b>\n\n"
                f"🌍 Страна: {escape(country)}\n"
                f"👤 Заказал: @{escape(user.username or 'нет username')}\n"
                f"🆔 ID: <code>{user.id}</code>"
            ),
            parse_mode="HTML",
        )

        await query.message.edit_text(
            "✅ Заявка принята!"
        )
        return


# =========================================================
# ЯЗЫК
# =========================================================

async def language_callback(update, context):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    set_language(
        user_id,
        "ru" if query.data == "lang_ru" else "uz",
    )

    data = get_user(user_id)

    await query.message.edit_text(
        tr(
            user_id,
            "welcome",
            name=query.from_user.first_name,
            balance=data["balance"],
        ),
        reply_markup=main_keyboard(user_id),
        parse_mode="HTML",
    )


# =========================================================
# ПОКУПКА STARS / PREMIUM
# =========================================================

async def buy_start(update, context):
    query = update.callback_query
    await query.answer()

    context.user_data.clear()
    data = query.data

    if data == "buy_stars":
        context.user_data["product_type"] = "stars"

        await query.message.edit_text(
            "⭐ Введите количество Stars (от 50 до 10000):"
        )
        return BUY_AMOUNT

    if data.startswith("buy_stars_"):
        amount = int(data.split("_")[2])

        context.user_data["product_type"] = "stars"
        context.user_data["amount"] = amount

        await query.message.edit_text(
            f"⭐ Вы выбрали {amount} Stars.\n\n"
            "Введите @username Telegram:"
        )
        return BUY_USERNAME

    if data.startswith("buy_premium_"):
        months = int(data.split("_")[2])

        context.user_data["product_type"] = "premium"
        context.user_data["amount"] = months
        context.user_data["months"] = months

        await query.message.edit_text(
            tr(
                query.from_user.id,
                "enter_username",
            )
        )
        return BUY_USERNAME

    return ConversationHandler.END


async def buy_amount(update, context):
    text = update.message.text.strip()

    if not text.isdigit():
        await update.message.reply_text(
            "❌ Введите корректное количество Stars."
        )
        return BUY_AMOUNT

    amount = int(text)

    if amount < 50 or amount > 10000:
        await update.message.reply_text(
            "❌ Можно купить от 50 до 10000 Stars."
        )
        return BUY_AMOUNT

    context.user_data["amount"] = amount

    await update.message.reply_text(
        tr(
            update.effective_user.id,
            "enter_username",
        )
    )

    return BUY_USERNAME


async def buy_username(update, context):
    username = update.message.text.strip().replace("@", "")

    if not validate_username(username):
        await update.message.reply_text(
            "❌ Введите корректный юзернейм."
        )
        return BUY_USERNAME

    user = update.effective_user
    product_type = context.user_data.get("product_type")
    amount = context.user_data.get("amount")

    if product_type == "stars":
        price = amount * PRICE_PER_STAR
        product = f"{amount} Stars"
    else:
        price = PREMIUM_PRICES.get(amount)

        if price is None:
            await update.message.reply_text(
                "❌ Неверный срок Premium."
            )
            context.user_data.clear()
            return ConversationHandler.END

        product = f"Telegram Premium на {amount} мес."

    data = get_user(
        user.id,
        user.username,
        user.first_name,
    )

    if data["balance"] < price:
        await update.message.reply_text(
            tr(
                user.id,
                "not_enough",
                price=price,
                balance=data["balance"],
            )
        )
        context.user_data.clear()
        return ConversationHandler.END

    context.user_data["username"] = username
    context.user_data["price"] = price
    context.user_data["product"] = product

    keyboard = [[
        InlineKeyboardButton(
            "✅ Купить",
            callback_data="confirm_buy",
        ),
        InlineKeyboardButton(
            "❌ Отмена",
            callback_data="cancel_buy",
        ),
    ]]

    await update.message.reply_text(
        tr(
            user.id,
            "confirm_order",
            product=product,
            username=username,
            price=price,
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )

    return BUY_CONFIRM


async def buy_confirm(update, context):
    query = update.callback_query
    await query.answer()

    user = query.from_user

    if query.data == "cancel_buy":
        context.user_data.clear()

        await query.message.edit_text(
            tr(user.id, "cancelled")
        )
        return ConversationHandler.END

    product_type = context.user_data.get("product_type")
    amount = context.user_data.get("amount")
    username = context.user_data.get("username")
    price = context.user_data.get("price")
    product = context.user_data.get("product")

    if not all([
        product_type,
        amount,
        username,
        price,
        product,
    ]):
        context.user_data.clear()
        await query.message.edit_text(
            "❌ Данные заказа потеряны. Попробуйте снова."
        )
        return ConversationHandler.END

    # Повторно проверяем баланс прямо перед списанием.
    data = get_user(
        user.id,
        user.username,
        user.first_name,
    )

    if data["balance"] < price:
        context.user_data.clear()
        await query.message.edit_text(
            tr(
                user.id,
                "not_enough",
                price=price,
                balance=data["balance"],
            )
        )
        return ConversationHandler.END

    await query.message.edit_text(
        tr(user.id, "processing")
    )

    success, provider_result = await send_order_to_elder(
        product_type,
        amount,
        username,
    )

    if not success:
        await query.message.edit_text(
            tr(user.id, "api_error")
        )
        context.user_data.clear()
        return ConversationHandler.END

    change_balance(user.id, -price)

    await context.bot.send_message(
        ADMIN_ID,
        (
            "🛒 <b>НОВЫЙ ЗАКАЗ</b>\n\n"
            f"📦 Товар: {escape(product)}\n"
            f"👤 Получатель: @{escape(username)}\n"
            f"💰 Цена: {price:,} сум\n"
            f"🆔 ID заказчика: <code>{user.id}</code>\n"
            f"👤 Заказал: @{escape(user.username or 'нет username')}"
        ),
        parse_mode="HTML",
    )

    await query.message.edit_text(
        (
            "✅ <b>Заказ успешно выполнен!</b>\n\n"
            f"📦 {escape(product)}\n"
            f"👤 Получатель: @{escape(username)}"
        ),
        parse_mode="HTML",
    )

    context.user_data.clear()
    return ConversationHandler.END


# =========================================================
# ПОПОЛНЕНИЕ
# =========================================================

async def refill_start(update, context):
    query = update.callback_query
    await query.answer()

    context.user_data.clear()

    await query.message.edit_text(
        tr(
            query.from_user.id,
            "refill_enter",
        )
    )

    return REFILL_AMOUNT


async def refill_amount(update, context):
    text = update.message.text.replace(" ", "")

    if not text.isdigit():
        await update.message.reply_text(
            "❌ Введите корректную сумму."
        )
        return REFILL_AMOUNT

    base_amount = int(text)

    if base_amount <= 0:
        await update.message.reply_text(
            "❌ Введите корректную сумму."
        )
        return REFILL_AMOUNT

    conn = db_connect()
    cursor = conn.cursor()

    # Уникальная сумма нужна для автоматического сопоставления SMS.
    # Ограничиваем число попыток.
    for _ in range(10000):
        amount = base_amount + random.randint(1, 999)

        cursor.execute(
            "SELECT 1 FROM pending_refills WHERE amount = ?",
            (amount,),
        )

        if cursor.fetchone() is None:
            break
    else:
        conn.close()
        await update.message.reply_text(
            "❌ Не удалось создать уникальную сумму. Попробуйте ещё раз."
        )
        return REFILL_AMOUNT

    cursor.execute("""
        INSERT INTO pending_refills
        (amount, user_id)
        VALUES (?, ?)
    """, (
        amount,
        update.effective_user.id,
    ))

    conn.commit()
    conn.close()

    context.user_data["refill_amount"] = amount
    context.user_data["refill_user_id"] = update.effective_user.id

    await update.message.reply_text(
        tr(
            update.effective_user.id,
            "refill_payment",
            amount=amount,
            card=CARD_NUMBER,
        ),
        parse_mode="HTML",
    )

    return REFILL_CHECK


async def refill_check(update, context):
    if update.message and update.message.text:
        await update.message.reply_text(
            "⏳ Ожидайте поступления оплаты.\n\n"
            "После оплаты баланс пополнится автоматически."
        )

    return REFILL_CHECK


# =========================================================
# АВТОМАТИЧЕСКОЕ ПОПОЛНЕНИЕ ПО ПЕРЕСЛАННОМУ SMS
# =========================================================

async def process_bank_sms(update, context):
    if not update.message or not update.message.text:
        return

    message = update.message

    if not message.forward_origin:
        return

    sender = getattr(
        message.forward_origin,
        "sender_user",
        None,
    )

    if not sender:
        return

    if sender.id != ADMIN_ID:
        return

    text = message.text

    if "From: 5800" not in text:
        return

    if "Miqdor:" not in text:
        return

    match = re.search(
        r"Miqdor:\s*([\d\s]+(?:\.\d+)?)\s*UZS",
        text,
    )

    if not match:
        return

    try:
        amount = int(
            float(
                match.group(1).replace(" ", "")
            )
        )
    except ValueError:
        return

    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT user_id
        FROM pending_refills
        WHERE amount = ?
    """, (amount,))

    row = cursor.fetchone()

    if row is None:
        conn.close()
        return

    user_id = row[0]

    cursor.execute("""
        DELETE FROM pending_refills
        WHERE amount = ?
    """, (amount,))

    deleted = cursor.rowcount

    if deleted != 1:
        conn.rollback()
        conn.close()
        return

    cursor.execute("""
        UPDATE users
        SET balance = balance + ?
        WHERE user_id = ?
    """, (
        amount,
        user_id,
    ))

    conn.commit()
    conn.close()

    await context.bot.send_message(
        user_id,
        (
            "✅ <b>Баланс пополнен автоматически!</b>\n\n"
            f"💰 Зачислено: <b>{amount:,} сум</b>"
        ),
        parse_mode="HTML",
    )

    await context.bot.send_message(
        ADMIN_ID,
        (
            "✅ <b>Автопополнение выполнено</b>\n\n"
            f"👤 ID: <code>{user_id}</code>\n"
            f"💰 Сумма: <b>{amount:,} сум</b>"
        ),
        parse_mode="HTML",
    )


# =========================================================
# ПОДАРКИ
# =========================================================

async def gift_start(update, context):
    query = update.callback_query
    await query.answer()

    gift_id = int(query.data.split("_")[1])

    context.user_data.clear()
    context.user_data["gift_id"] = gift_id

    keyboard = [
        [
            InlineKeyboardButton(
                "👤 Отправить не анонимно",
                callback_data="gift_anonymous_no",
            )
        ],
        [
            InlineKeyboardButton(
                "🕵️ Отправить анонимно",
                callback_data="gift_anonymous_yes",
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Отмена",
                callback_data="cancel_gift",
            )
        ],
    ]

    await query.message.edit_text(
        tr(
            query.from_user.id,
            "gift_send_type",
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )

    return GIFT_SEND_TYPE


async def gift_send_type(update, context):
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_gift":
        return await cancel(update, context)

    context.user_data["anonymous"] = (
        query.data == "gift_anonymous_yes"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "✍️ Добавить текст",
                callback_data="gift_text_yes",
            )
        ],
        [
            InlineKeyboardButton(
                "➡️ Без текста",
                callback_data="gift_text_no",
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Отмена",
                callback_data="cancel_gift",
            )
        ],
    ]

    await query.message.edit_text(
        "📝 <b>Добавить текст к подарку?</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )

    return GIFT_TEXT


async def gift_text_choice(update, context):
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_gift":
        return await cancel(update, context)

    if query.data == "gift_text_yes":
        await query.message.edit_text(
            tr(
                query.from_user.id,
                "gift_text",
            )
        )
        return GIFT_TEXT

    context.user_data["gift_text"] = ""

    await query.message.edit_text(
        tr(
            query.from_user.id,
            "gift_username",
        )
    )

    return GIFT_USERNAME


async def gift_text_input(update, context):
    context.user_data["gift_text"] = (
        update.message.text.strip()
    )

    await update.message.reply_text(
        tr(
            update.effective_user.id,
            "gift_username",
        )
    )

    return GIFT_USERNAME


async def send_custom_emoji(
    bot,
    chat_id,
    emoji,
    emoji_id,
):
    # len() для Unicode-эмодзи не всегда равен 2.
    # Для custom emoji Telegram нужен корректный UTF-16 offset/length.
    utf16_length = len(
        emoji.encode("utf-16-le")
    ) // 2

    await bot.send_message(
        chat_id=chat_id,
        text=emoji,
        entities=[
            MessageEntity(
                type=MessageEntity.CUSTOM_EMOJI,
                offset=0,
                length=utf16_length,
                custom_emoji_id=emoji_id,
            )
        ],
    )


async def gift_username(update, context):
    username = update.message.text.strip().replace("@", "")

    if not validate_username(username):
        await update.message.reply_text(
            "❌ Введите корректный юзернейм."
        )
        return GIFT_USERNAME

    user = update.effective_user
    gift_id = context.user_data["gift_id"]
    gift = GIFTS[gift_id]

    data = get_user(
        user.id,
        user.username,
        user.first_name,
    )

    if data["balance"] < gift["price"]:
        await update.message.reply_text(
            tr(
                user.id,
                "not_enough",
                price=gift["price"],
                balance=data["balance"],
            )
        )
        context.user_data.clear()
        return ConversationHandler.END

    anonymous = context.user_data.get(
        "anonymous",
        False,
    )

    gift_text = context.user_data.get(
        "gift_text",
        "",
    )

    change_balance(
        user.id,
        -gift["price"],
    )

    sender = (
        "Анонимно"
        if anonymous
        else f"@{user.username or 'нет username'}"
    )

    try:
        await send_custom_emoji(
            context.bot,
            ADMIN_ID,
            gift["emoji"],
            gift["emoji_id"],
        )
    except Exception:
        logger.exception(
            "Could not send custom emoji"
        )

    await context.bot.send_message(
        ADMIN_ID,
        (
            "🎁 <b>НОВЫЙ ЗАКАЗ ПОДАРКА</b>\n\n"
            f"🎁 Подарок: <b>{escape(gift['name'])}</b>\n"
            f"💰 Цена: {gift['price']:,} сум\n\n"
            f"👤 Заказал: {escape(sender)}\n"
            f"🆔 ID заказчика: <code>{user.id}</code>\n\n"
            f"🎯 Получатель: @{escape(username)}\n"
            f"📝 Текст: "
            f"{escape(gift_text) if gift_text else 'без текста'}\n\n"
            "⚠️ Отправьте подарок получателю."
        ),
        parse_mode="HTML",
    )

    await update.message.reply_text(
        tr(
            user.id,
            "gift_success",
        )
    )

    context.user_data.clear()
    return ConversationHandler.END


# =========================================================
# ОТМЕНА
# =========================================================

async def cancel(update, context):
    context.user_data.clear()

    user_id = update.effective_user.id

    if update.callback_query:
        query = update.callback_query

        try:
            await query.answer()
        except Exception:
            pass

        await query.message.edit_text(
            tr(
                user_id,
                "cancelled",
            )
        )
    else:
        await update.message.reply_text(
            tr(
                user_id,
                "cancelled",
            )
        )

    return ConversationHandler.END


# =========================================================
# АДМИН
# =========================================================

def is_admin(user_id):
    return user_id == ADMIN_ID


def admin_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "➕ Добавить баланс",
                callback_data="admin_add",
            ),
            InlineKeyboardButton(
                "➖ Убавить баланс",
                callback_data="admin_sub",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔨 Забанить",
                callback_data="admin_ban",
            ),
            InlineKeyboardButton(
                "🔓 Разбанить",
                callback_data="admin_unban",
            ),
        ],
        [
            InlineKeyboardButton(
                "💬 Отправить сообщение",
                callback_data="admin_message",
            )
        ],
        [
            InlineKeyboardButton(
                "👥 Пользователи",
                callback_data="admin_users",
            )
        ],
        [
            InlineKeyboardButton(
                "💰 Балансы",
                callback_data="admin_balances",
            )
        ],
        [
            InlineKeyboardButton(
                "📊 Статистика",
                callback_data="admin_stats",
            )
        ],
        [
            InlineKeyboardButton(
                "🤝 Партнёр API",
                callback_data="admin_partners",
            )
        ],
    ])


async def admin(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "❌ Нет доступа."
        )
        return

    await update.message.reply_text(
        "🛠 <b>АДМИН-ПАНЕЛЬ</b>",
        reply_markup=admin_keyboard(),
        parse_mode="HTML",
    )


# =========================================================
# АДМИН: PARTNER API
# =========================================================

def partner_admin_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "➕ Создать API Key",
                callback_data="partner_create",
            )
        ],
        [
            InlineKeyboardButton(
                "📋 Список ключей",
                callback_data="partner_list",
            )
        ],
        [
            InlineKeyboardButton(
                "💰 Добавить баланс",
                callback_data="partner_add_balance",
            )
        ],
        [
            InlineKeyboardButton(
                "🚫 Заблокировать",
                callback_data="partner_revoke",
            )
        ],
        [
            InlineKeyboardButton(
                "⬅️ Назад",
                callback_data="admin_back",
            )
        ],
    ])


async def show_partner_menu(query):
    await query.message.edit_text(
        (
            "🤝 <b>PARTNER API</b>\n\n"
            "Здесь можно создавать отдельные API-ключи "
            "для партнёров.\n\n"
            "Партнёр использует свой ключ, а твой "
            "внутренний ELDER_API_KEY ему не передаётся."
        ),
        reply_markup=partner_admin_keyboard(),
        parse_mode="HTML",
    )


async def partner_list(query):
    partners = get_partners()

    if not partners:
        await query.message.edit_text(
            "🤝 Партнёров пока нет.",
            reply_markup=partner_admin_keyboard(),
        )
        return

    lines = ["🤝 <b>ПАРТНЁРЫ</b>\n"]

    for row in partners[:50]:
        (
            partner_id,
            name,
            owner_user_id,
            balance,
            active,
            created_at,
            key_prefix,
        ) = row

        status = "🟢 Активен" if active else "🔴 Заблокирован"

        lines.append(
            f"<b>#{partner_id} — {escape(name)}</b>\n"
            f"🔑 {escape(key_prefix)}...\n"
            f"💰 Баланс: <b>{balance:,} сум</b>\n"
            f"👤 Owner ID: <code>{owner_user_id or '-'}</code>\n"
            f"{status}\n"
        )

    await query.message.edit_text(
        "\n".join(lines),
        reply_markup=partner_admin_keyboard(),
        parse_mode="HTML",
    )


async def admin_callback(update, context):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return ConversationHandler.END

    data = query.data

    if data == "admin_add":
        await query.message.edit_text(
            "➕ Введите ID пользователя:"
        )
        return ADMIN_ADD_ID

    if data == "admin_sub":
        await query.message.edit_text(
            "➖ Введите ID пользователя:"
        )
        return ADMIN_SUB_ID

    if data == "admin_ban":
        await query.message.edit_text(
            "🔨 Введите ID пользователя для бана:"
        )
        return ADMIN_BAN_ID

    if data == "admin_unban":
        await query.message.edit_text(
            "🔓 Введите ID пользователя для разбана:"
        )
        return ADMIN_UNBAN_ID

    if data == "admin_message":
        await query.message.edit_text(
            "💬 Введите ID пользователя:"
        )
        return ADMIN_MESSAGE_ID

    if data == "admin_users":
        users = get_users()

        if not users:
            await query.message.edit_text(
                "👥 Пользователей пока нет."
            )
            return ConversationHandler.END

        text = "👥 <b>ПОЛЬЗОВАТЕЛИ</b>\n\n"

        for index, row in enumerate(users[:50], 1):
            user_id, username, name, balance, lang, banned = row

            username_text = (
                f"@{escape(username)}"
                if username
                else "нет username"
            )

            status = (
                "🔴 БАН"
                if banned
                else "🟢 Активен"
            )

            text += (
                f"<b>{index}. "
                f"{escape(name or 'Без имени')}</b>\n"
                f"👤 {username_text}\n"
                f"🆔 <code>{user_id}</code>\n"
                f"💰 {balance:,} сум\n"
                f"🌐 {lang}\n"
                f"{status}\n\n"
            )

        await query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⬅️ Назад",
                        callback_data="admin_back",
                    )
                ]
            ]),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    if data == "admin_balances":
        users = get_users()
        total = sum(row[3] for row in users)

        await query.message.edit_text(
            (
                "💰 <b>БАЛАНСЫ</b>\n\n"
                f"👥 Пользователей: {len(users)}\n"
                f"💵 Общий баланс: {total:,} сум"
            ),
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⬅️ Назад",
                        callback_data="admin_back",
                    )
                ]
            ]),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    if data == "admin_stats":
        users = get_users()

        active = sum(
            1 for row in users if not row[5]
        )
        banned = sum(
            1 for row in users if row[5]
        )

        partners = get_partners()
        active_partners = sum(
            1 for row in partners if row[4]
        )

        await query.message.edit_text(
            (
                "📊 <b>СТАТИСТИКА</b>\n\n"
                f"👥 Всего пользователей: {len(users)}\n"
                f"🟢 Активных: {active}\n"
                f"🔴 Заблокированных: {banned}\n\n"
                f"🤝 Партнёров: {len(partners)}\n"
                f"🟢 Активных партнёров: {active_partners}"
            ),
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⬅️ Назад",
                        callback_data="admin_back",
                    )
                ]
            ]),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    if data == "admin_partners":
        await show_partner_menu(query)
        return ConversationHandler.END

    if data == "admin_back":
        await query.message.edit_text(
            "🛠 <b>АДМИН-ПАНЕЛЬ</b>",
            reply_markup=admin_keyboard(),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    # Partner API menu
    if data == "partner_create":
        await query.message.edit_text(
            "🤝 Введите название партнёра.\n\n"
            "Например: MyShop"
        )
        return ADMIN_PARTNER_CREATE_NAME

    if data == "partner_list":
        await partner_list(query)
        return ConversationHandler.END

    if data == "partner_add_balance":
        await query.message.edit_text(
            "💰 Введите Partner ID:"
        )
        return ADMIN_PARTNER_BALANCE_ID

    if data == "partner_revoke":
        await query.message.edit_text(
            "🚫 Введите Partner ID:"
        )
        return ADMIN_PARTNER_REVOKE_ID

    return ConversationHandler.END


async def admin_partner_create_name(update, context):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    name = update.message.text.strip()

    if len(name) < 2 or len(name) > 80:
        await update.message.reply_text(
            "❌ Название должно быть от 2 до 80 символов."
        )
        return ADMIN_PARTNER_CREATE_NAME

    partner_id, api_key = create_partner(
        name,
        update.effective_user.id,
    )

    await update.message.reply_text(
        (
            "✅ <b>Партнёр создан!</b>\n\n"
            f"🆔 Partner ID: <code>{partner_id}</code>\n"
            f"🏷 Название: <b>{escape(name)}</b>\n\n"
            "🔑 <b>API KEY:</b>\n"
            f"<code>{escape(api_key)}</code>\n\n"
            "⚠️ Этот полный ключ показывается только сейчас.\n"
            "Сохрани его и передай партнёру безопасным способом.\n\n"
            "Партнёр не получает твой ELDER_API_KEY."
        ),
        parse_mode="HTML",
        reply_markup=partner_admin_keyboard(),
    )

    return ConversationHandler.END


async def admin_partner_balance_id(update, context):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    text = update.message.text.strip()

    if not text.isdigit():
        await update.message.reply_text(
            "❌ Введите Partner ID цифрами."
        )
        return ADMIN_PARTNER_BALANCE_ID

    partner_id = int(text)
    partner = get_partner(partner_id)

    if not partner:
        await update.message.reply_text(
            "❌ Партнёр не найден."
        )
        return ADMIN_PARTNER_BALANCE_ID

    context.user_data["partner_id"] = partner_id

    await update.message.reply_text(
        (
            f"🤝 <b>{escape(partner['name'])}</b>\n"
            f"🆔 ID: <code>{partner_id}</code>\n"
            f"💰 Текущий баланс: <b>{partner['balance']:,} сум</b>\n\n"
            "Введите сумму для добавления:"
        ),
        parse_mode="HTML",
    )

    return ADMIN_PARTNER_BALANCE_AMOUNT


async def admin_partner_balance_amount(update, context):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    text = update.message.text.replace(" ", "").strip()

    if not text.isdigit():
        await update.message.reply_text(
            "❌ Введите сумму цифрами."
        )
        return ADMIN_PARTNER_BALANCE_AMOUNT

    amount = int(text)

    if amount <= 0:
        await update.message.reply_text(
            "❌ Сумма должна быть больше 0."
        )
        return ADMIN_PARTNER_BALANCE_AMOUNT

    partner_id = context.user_data.get("partner_id")

    if not partner_id:
        return ConversationHandler.END

    partner = get_partner(partner_id)

    if not partner:
        await update.message.reply_text(
            "❌ Партнёр не найден."
        )
        context.user_data.clear()
        return ConversationHandler.END

    change_partner_balance(
        partner_id,
        amount,
    )

    fresh = get_partner(partner_id)

    await update.message.reply_text(
        (
            "✅ <b>Баланс партнёра пополнен</b>\n\n"
            f"🤝 Партнёр: <b>{escape(fresh['name'])}</b>\n"
            f"🆔 ID: <code>{partner_id}</code>\n"
            f"➕ Добавлено: <b>{amount:,} сум</b>\n"
            f"💰 Новый баланс: <b>{fresh['balance']:,} сум</b>"
        ),
        parse_mode="HTML",
        reply_markup=partner_admin_keyboard(),
    )

    context.user_data.clear()
    return ConversationHandler.END


async def admin_partner_revoke(update, context):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    text = update.message.text.strip()

    if not text.isdigit():
        await update.message.reply_text(
            "❌ Введите Partner ID цифрами."
        )
        return ADMIN_PARTNER_REVOKE_ID

    partner_id = int(text)
    partner = get_partner(partner_id)

    if not partner:
        await update.message.reply_text(
            "❌ Партнёр не найден."
        )
        return ADMIN_PARTNER_REVOKE_ID

    set_partner_active(
        partner_id,
        False,
    )

    await update.message.reply_text(
        (
            "🚫 <b>API Key отключён</b>\n\n"
            f"🤝 Партнёр: <b>{escape(partner['name'])}</b>\n"
            f"🆔 ID: <code>{partner_id}</code>"
        ),
        parse_mode="HTML",
        reply_markup=partner_admin_keyboard(),
    )

    return ConversationHandler.END


# =========================================================
# АДМИН: ДОБАВИТЬ БАЛАНС ПОЛЬЗОВАТЕЛЮ
# =========================================================

async def admin_add_id(update, context):
    text = update.message.text.strip()

    if not text.isdigit():
        await update.message.reply_text(
            "❌ Введите правильный ID."
        )
        return ADMIN_ADD_ID

    user_id = int(text)
    user = get_user(user_id)

    context.user_data["admin_user_id"] = user_id

    await update.message.reply_text(
        f"➕ Пользователь: <code>{user_id}</code>\n"
        f"💰 Текущий баланс: {user['balance']:,} сум\n\n"
        "Введите сумму для добавления:",
        parse_mode="HTML",
    )

    return ADMIN_ADD_AMOUNT


async def admin_add_amount(update, context):
    text = update.message.text.replace(" ", "")

    if not text.isdigit():
        await update.message.reply_text(
            "❌ Введите сумму цифрами."
        )
        return ADMIN_ADD_AMOUNT

    amount = int(text)

    if amount <= 0:
        await update.message.reply_text(
            "❌ Сумма должна быть больше 0."
        )
        return ADMIN_ADD_AMOUNT

    user_id = context.user_data["admin_user_id"]

    change_balance(
        user_id,
        amount,
    )

    await context.bot.send_message(
        user_id,
        (
            "💰 <b>Баланс изменён администратором</b>\n\n"
            f"➕ Добавлено: {amount:,} сум"
        ),
        parse_mode="HTML",
    )

    await update.message.reply_text(
        f"✅ Добавлено <b>{amount:,} сум</b>\n"
        f"👤 ID: <code>{user_id}</code>",
        parse_mode="HTML",
    )

    context.user_data.clear()
    return ConversationHandler.END


# =========================================================
# АДМИН: УБАВИТЬ БАЛАНС
# =========================================================

async def admin_sub_id(update, context):
    text = update.message.text.strip()

    if not text.isdigit():
        await update.message.reply_text(
            "❌ Введите правильный ID."
        )
        return ADMIN_SUB_ID

    user_id = int(text)
    user = get_user(user_id)

    context.user_data["admin_user_id"] = user_id

    await update.message.reply_text(
        f"➖ Пользователь: <code>{user_id}</code>\n"
        f"💰 Текущий баланс: {user['balance']:,} сум\n\n"
        "Введите сумму для снятия:",
        parse_mode="HTML",
    )

    return ADMIN_SUB_AMOUNT


async def admin_sub_amount(update, context):
    text = update.message.text.replace(" ", "")

    if not text.isdigit():
        await update.message.reply_text(
            "❌ Введите сумму цифрами."
        )
        return ADMIN_SUB_AMOUNT

    amount = int(text)

    if amount <= 0:
        await update.message.reply_text(
            "❌ Сумма должна быть больше 0."
        )
        return ADMIN_SUB_AMOUNT

    user_id = context.user_data["admin_user_id"]
    user = get_user(user_id)

    if user["balance"] < amount:
        await update.message.reply_text(
            f"❌ У пользователя баланс только "
            f"{user['balance']:,} сум."
        )
        return ConversationHandler.END

    change_balance(
        user_id,
        -amount,
    )

    await context.bot.send_message(
        user_id,
        (
            "💰 <b>Баланс изменён администратором</b>\n\n"
            f"➖ Снято: {amount:,} сум"
        ),
        parse_mode="HTML",
    )

    await update.message.reply_text(
        f"✅ Убавлено <b>{amount:,} сум</b>\n"
        f"👤 ID: <code>{user_id}</code>",
        parse_mode="HTML",
    )

    context.user_data.clear()
    return ConversationHandler.END


# =========================================================
# АДМИН: БАН
# =========================================================

async def admin_ban_id(update, context):
    text = update.message.text.strip()

    if not text.isdigit():
        await update.message.reply_text(
            "❌ Введите правильный ID."
        )
        return ADMIN_BAN_ID

    user_id = int(text)

    get_user(user_id)
    set_ban(user_id, 1)

    try:
        await context.bot.send_message(
            user_id,
            "🔨 Вы были заблокированы администрацией.",
        )
    except Exception:
        pass

    await update.message.reply_text(
        f"✅ Пользователь <code>{user_id}</code> заблокирован.",
        parse_mode="HTML",
    )

    return ConversationHandler.END


# =========================================================
# АДМИН: РАЗБАН
# =========================================================

async def admin_unban_id(update, context):
    text = update.message.text.strip()

    if not text.isdigit():
        await update.message.reply_text(
            "❌ Введите правильный ID."
        )
        return ADMIN_UNBAN_ID

    user_id = int(text)

    get_user(user_id)
    set_ban(user_id, 0)

    try:
        await context.bot.send_message(
            user_id,
            "🔓 Вы были разблокированы администрацией.",
        )
    except Exception:
        pass

    await update.message.reply_text(
        f"✅ Пользователь <code>{user_id}</code> разблокирован.",
        parse_mode="HTML",
    )

    return ConversationHandler.END


# =========================================================
# АДМИН: СООБЩЕНИЕ
# =========================================================

async def admin_message_id(update, context):
    text = update.message.text.strip()

    if not text.isdigit():
        await update.message.reply_text(
            "❌ Введите правильный ID."
        )
        return ADMIN_MESSAGE_ID

    user_id = int(text)

    get_user(user_id)
    context.user_data["admin_user_id"] = user_id

    await update.message.reply_text(
        f"💬 ID пользователя: <code>{user_id}</code>\n\n"
        "Теперь напишите сообщение:",
        parse_mode="HTML",
    )

    return ADMIN_MESSAGE_TEXT


async def admin_message_text(update, context):
    user_id = context.user_data["admin_user_id"]
    text = update.message.text

    try:
        await context.bot.send_message(
            user_id,
            (
                "📩 <b>Сообщение от администратора</b>\n\n"
                f"{escape(text)}"
            ),
            parse_mode="HTML",
        )

        await update.message.reply_text(
            "✅ Сообщение отправлено."
        )

    except Exception as exc:
        logger.exception(exc)

        await update.message.reply_text(
            "❌ Не удалось отправить сообщение.\n"
            "Возможно, пользователь заблокировал бота."
        )

    context.user_data.clear()
    return ConversationHandler.END


# =========================================================
# UNKNOWN CALLBACK
# =========================================================

async def unknown_callback(update, context):
    query = update.callback_query

    try:
        await query.answer()
    except Exception:
        pass


# =========================================================
# MAIN
# =========================================================

def main():
    global TELEGRAM_APPLICATION

    init_db()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    TELEGRAM_APPLICATION = application

    # Web/API server.
    threading.Thread(
        target=run_web,
        daemon=True,
    ).start()

    # =====================================================
    # CONVERSATION HANDLER
    # =====================================================

    conversation_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                refill_start,
                pattern=r"^main_refill$",
            ),
            CallbackQueryHandler(
                buy_start,
                pattern=r"^buy_.*$",
            ),
            CallbackQueryHandler(
                gift_start,
                pattern=r"^gift_\d+$",
            ),
            CallbackQueryHandler(
                admin_callback,
                pattern=(
                    r"^(admin_add|admin_sub|admin_ban|"
                    r"admin_unban|admin_message|admin_partners|"
                    r"partner_create|partner_list|"
                    r"partner_add_balance|partner_revoke)$"
                ),
            ),
        ],
        states={
            REFILL_AMOUNT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    refill_amount,
                )
            ],
            REFILL_CHECK: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    refill_check,
                ),
            ],
            BUY_AMOUNT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    buy_amount,
                )
            ],
            BUY_USERNAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    buy_username,
                )
            ],
            BUY_CONFIRM: [
                CallbackQueryHandler(
                    buy_confirm,
                    pattern=r"^(confirm_buy|cancel_buy)$",
                )
            ],
            GIFT_SEND_TYPE: [
                CallbackQueryHandler(
                    gift_send_type,
                    pattern=(
                        r"^(gift_anonymous_yes|"
                        r"gift_anonymous_no|"
                        r"cancel_gift)$"
                    ),
                )
            ],
            GIFT_TEXT: [
                CallbackQueryHandler(
                    gift_text_choice,
                    pattern=(
                        r"^(gift_text_yes|"
                        r"gift_text_no|"
                        r"cancel_gift)$"
                    ),
                ),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    gift_text_input,
                ),
            ],
            GIFT_USERNAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    gift_username,
                )
            ],
            ADMIN_ADD_ID: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_add_id,
                )
            ],
            ADMIN_ADD_AMOUNT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_add_amount,
                )
            ],
            ADMIN_SUB_ID: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_sub_id,
                )
            ],
            ADMIN_SUB_AMOUNT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_sub_amount,
                )
            ],
            ADMIN_BAN_ID: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_ban_id,
                )
            ],
            ADMIN_UNBAN_ID: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_unban_id,
                )
            ],
            ADMIN_MESSAGE_ID: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_message_id,
                )
            ],
            ADMIN_MESSAGE_TEXT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_message_text,
                )
            ],
            ADMIN_PARTNER_CREATE_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_partner_create_name,
                )
            ],
            ADMIN_PARTNER_BALANCE_ID: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_partner_balance_id,
                )
            ],
            ADMIN_PARTNER_BALANCE_AMOUNT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_partner_balance_amount,
                )
            ],
            ADMIN_PARTNER_REVOKE_ID: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_partner_revoke,
                )
            ],
        },
        fallbacks=[
            CommandHandler(
                "cancel",
                cancel,
            ),
            CallbackQueryHandler(
                cancel,
                pattern=r"^cancel_",
            ),
        ],
        allow_reentry=True,
    )

    # Сначала обработчик пересланного банковского SMS.
    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.FORWARDED,
            process_bank_sms,
        )
    )

    application.add_handler(
        conversation_handler
    )

    # =====================================================
    # START
    # =====================================================

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    # =====================================================
    # ADMIN
    # =====================================================

    application.add_handler(
        CommandHandler(
            "admin",
            admin,
        )
    )

    # =====================================================
    # ЯЗЫК
    # =====================================================

    application.add_handler(
        CallbackQueryHandler(
            language_callback,
            pattern=r"^lang_(ru|uz)$",
        )
    )

    # =====================================================
    # ПРОФИЛЬ
    # =====================================================

    application.add_handler(
        CallbackQueryHandler(
            profile_callback,
            pattern=r"^(main_profile|profile)$",
        )
    )

    # =====================================================
    # ГЛАВНЫЕ КНОПКИ
    # =====================================================

    application.add_handler(
        CallbackQueryHandler(
            main_buttons,
            pattern=(
                r"^(main_shop|shop_.*|account_.*|"
                r"back_main|language_menu)$"
            ),
        )
    )

    # =====================================================
    # UNKNOWN CALLBACK
    # =====================================================

    application.add_handler(
        CallbackQueryHandler(
            unknown_callback,
        )
    )

    logger.info("BOT STARTED")
    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()