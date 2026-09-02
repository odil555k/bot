import os
import re
import uuid
import sqlite3
import logging
import threading
import random
import hashlib
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer

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

ELDER_API_KEY = os.environ["ELDER_API_KEY"]
ELDER_API_URL = "https://elder.uz"

DB_FILE = "bot_database.db"

CARD_NUMBER = os.environ.get("CARD_NUMBER", "УКАЖИ_НОМЕР_КАРТЫ")

# ID закрытой Telegram-группы, куда SMS2 Forwarder отправляет SMS.
# Пример: -1001234567890
SMS_GROUP_ID = int(os.environ.get("SMS_GROUP_ID", "0"))

# SMS2 Forwarder присылает банковское SMS в формате:
# From: 5800
# Time: ...
# Kartaga o'tkazma: ... Miqdor:1080.00 UZS Qoldiq:2001.85 UZS
# Кодовое слово не используется.

PRICE_PER_STAR = 210

PREMIUM_PRICES = {
    3: 165000,
    6: 222000,
    12: 406000,
}


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

ADMIN_USER_ID = 9
ADMIN_AMOUNT = 10
ADMIN_MESSAGE = 11


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
        "emoji": "💐",
        "emoji_id": "5280774333243873175",
        "price": 4000,
        "stars": 15,
        "name": "Букет",
    },
    3: {
        "emoji": "🚀",
        "emoji_id": "5283080528818360566",
        "price": 6000,
        "stars": 25,
        "name": "Ракета",
    },
    4: {
        "emoji": "🏆",
        "emoji_id": "5280769763398671636",
        "price": 6000,
        "stars": 25,
        "name": "Кубок",
    },
    5: {
        "emoji": "🎂",
        "emoji_id": "5280659198055572187",
        "price": 10500,
        "stars": 50,
        "name": "Торт",
    },
    6: {
        "emoji": "💎",
        "emoji_id": "5280922999241859582",
        "price": 10500,
        "stars": 50,
        "name": "Алмаз",
    },
    7: {
        "emoji": "🍾",
        "emoji_id": "5451905784734574339",
        "price": 10500,
        "stars": 50,
        "name": "Шампанское",
    },
    8: {
        "emoji": "🏆",
        "emoji_id": "5280769763398671636",
        "price": 21000,
        "stars": 100,
        "name": "Кубок",
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
        "emoji": "🍾",
        "emoji_id": "5451905784734574339",
        "price": 10500,
        "stars": 50,
        "name": "Шампанское",
    },
    12: {
        "emoji": "🎁",
        "emoji_id": "5280615440928758599",
        "price": 4000,
        "stars": 15,
        "name": "Подарок",
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
            "💰 На баланс будет зачислено: <b>{amount:,} сум</b>\n"
            "💳 Перевести нужно ровно: <b>{payment_amount:,} сум</b>\n\n"
            "Переведите деньги на карту:\n"
            "<code>{card}</code>\n\n"
            "📱 После перевода банковское SMS автоматически попадёт в систему.\n"
            "🤖 Бот проверит SMS и сам зачислит <b>{amount:,} сум</b>.\n\n"
            "⚠️ Переводите именно указанную сумму. Чек отправлять не нужно."
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
            "✅ <b>Заявка на подарок принята!</b>\n\n"
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
            "💰 Balansga tushadi: <b>{amount:,} so'm</b>\n"
            "💳 Aynan shuni o'tkazing: <b>{payment_amount:,} so'm</b>\n\n"
            "Kartaga pul o'tkazing:\n"
            "<code>{card}</code>\n\n"
            "📱 Bank SMS xabari avtomatik tekshiriladi.\n"
            "🤖 Bot <b>{amount:,} so'm</b>ni avtomatik qo'shadi.\n\n"
            "⚠️ Aynan ko'rsatilgan summani o'tkazing. Chek kerak emas."
        ),
        "receipt_sent": "⏳ Chek administratorga yuborildi.",
        "send_receipt": "❌ Chek rasmini yuboring.",
        "gift_send_type": "🎁 <b>Sovg'ani qanday yuborish?</b>",
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

def db():
    return sqlite3.connect(DB_FILE)


def init_db():
    conn = db()
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

    # Ожидаемые автоматические пополнения.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auto_refills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            requested_amount INTEGER NOT NULL,
            payment_amount INTEGER NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            paid_at TEXT
        )
    """)

    # Уже обработанные SMS, чтобы одно SMS нельзя было зачислить дважды.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processed_sms (
            sms_hash TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def get_user(user_id, username="", name=""):
    conn = db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT username, name, balance, lang, is_banned
        FROM users
        WHERE user_id = ?
        """,
        (user_id,),
    )

    row = cursor.fetchone()

    if row is None:
        cursor.execute(
            """
            INSERT INTO users
            (user_id, username, name, balance, lang, is_banned)
            VALUES (?, ?, ?, 0, 'ru', 0)
            """,
            (user_id, username or "", name or ""),
        )

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

        cursor.execute(
            """
            UPDATE users
            SET username = ?, name = ?
            WHERE user_id = ?
            """,
            (
                username or old_username or "",
                name or old_name or "",
                user_id,
            ),
        )

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
    conn = db()
    conn.execute(
        "UPDATE users SET lang = ? WHERE user_id = ?",
        (lang, user_id),
    )
    conn.commit()
    conn.close()


def change_balance(user_id, amount):
    conn = db()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (amount, user_id),
    )

    changed = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return changed


def set_ban(user_id, value):
    conn = db()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET is_banned = ? WHERE user_id = ?",
        (1 if value else 0, user_id),
    )

    changed = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return changed


def get_users():
    conn = db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT user_id, username, name, balance, lang, is_banned
        FROM users
        ORDER BY user_id DESC
        """
    )

    rows = cursor.fetchall()
    conn.close()

    return rows


def create_auto_refill(user_id, requested_amount):
    """Создаёт один ожидающий платёж с уникальной контрольной суммой."""
    conn = db()
    cursor = conn.cursor()

    # У пользователя одновременно может быть только один активный платёж.
    cursor.execute(
        "UPDATE auto_refills SET status = 'cancelled' "
        "WHERE user_id = ? AND status = 'pending'",
        (user_id,),
    )

    # Например, 4000 -> 4080. Контрольная добавка: 10..99.
    for _ in range(100):
        suffix = random.SystemRandom().randint(10, 99)
        payment_amount = requested_amount + suffix

        cursor.execute(
            "SELECT 1 FROM auto_refills WHERE payment_amount = ? LIMIT 1",
            (payment_amount,),
        )
        if cursor.fetchone() is not None:
            continue

        cursor.execute(
            """
            INSERT INTO auto_refills
            (user_id, requested_amount, payment_amount, status, created_at)
            VALUES (?, ?, ?, 'pending', datetime('now'))
            """,
            (user_id, requested_amount, payment_amount),
        )
        conn.commit()
        conn.close()
        return payment_amount

    conn.close()
    raise RuntimeError("Не удалось создать уникальную сумму пополнения")


def extract_sms_amounts(text):
    """Извлекает только сумму после Miqdor: из банковского SMS."""
    if not text:
        return []

    match = re.search(
        r"Miqdor\s*:\s*([0-9][0-9\s\u00a0.,]*)\s*UZS\b",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return []

    value = match.group(1).replace("\u00a0", " ")
    value = re.sub(r"\s+", "", value)

    # Убираем .00 / ,00, не трогая Qoldiq.
    if re.fullmatch(r"\d+[.,]\d{1,2}", value):
        value = re.split(r"[.,]", value)[0]
    elif "." in value:
        left, right = value.rsplit(".", 1)
        value = left if len(right) <= 2 else value.replace(".", "")
    elif "," in value:
        left, right = value.rsplit(",", 1)
        value = left if len(right) <= 2 else value.replace(",", "")

    digits = re.sub(r"[^0-9]", "", value)
    if not digits:
        return []

    amount = int(digits)
    return [amount] if amount > 0 else []


def sms_has_bank_format(text):
    """Проверяет реальный формат банковского SMS от 5800."""
    if not text:
        return False

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lower = normalized.lower()

    has_sender = bool(
        re.search(r"(?m)^\s*From\s*:\s*5800\s*$", normalized, re.IGNORECASE)
    )
    has_transfer = "kartaga o'tkazma" in lower or "kartaga o‘tkazma" in lower
    has_amount = bool(
        re.search(
            r"Miqdor\s*:\s*[0-9][0-9\s\u00a0.,]*\s*UZS\b",
            normalized,
            re.IGNORECASE,
        )
    )
    return has_sender and has_transfer and has_amount


def process_sms_text(text, telegram_sender_id=0):
    """Проверяет SMS и атомарно зачисляет ожидающий платеж."""
    if not text or len(text) > 4000:
        return {"ok": False, "reason": "bad_text"}

    if not sms_has_bank_format(text):
        return {"ok": False, "reason": "bank_format_not_found"}

    amounts = extract_sms_amounts(text)
    if not amounts:
        return {"ok": False, "reason": "amount_not_found"}

    sms_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
    conn = db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT 1 FROM processed_sms WHERE sms_hash = ? LIMIT 1",
            (sms_hash,),
        )
        if cursor.fetchone() is not None:
            conn.close()
            return {"ok": False, "reason": "duplicate"}

        placeholders = ",".join("?" for _ in amounts)
        cursor.execute(
            f"""
            SELECT id, user_id, requested_amount, payment_amount
            FROM auto_refills
            WHERE status = 'pending'
              AND payment_amount IN ({placeholders})
              AND datetime(created_at) >= datetime('now', '-60 minutes')
            ORDER BY id ASC
            LIMIT 1
            """,
            amounts,
        )
        row = cursor.fetchone()

        if row is None:
            conn.close()
            return {"ok": False, "reason": "payment_not_found", "amounts": amounts}

        refill_id, user_id, requested_amount, payment_amount = row

        cursor.execute(
            """
            UPDATE auto_refills
            SET status = 'paid', paid_at = datetime('now')
            WHERE id = ? AND status = 'pending'
            """,
            (refill_id,),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            conn.close()
            return {"ok": False, "reason": "already_processed"}

        cursor.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (requested_amount, user_id),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            conn.close()
            return {"ok": False, "reason": "user_not_found"}

        cursor.execute(
            "INSERT INTO processed_sms (sms_hash, created_at) VALUES (?, datetime('now'))",
            (sms_hash,),
        )
        conn.commit()
        conn.close()

        return {
            "ok": True,
            "user_id": user_id,
            "requested_amount": requested_amount,
            "payment_amount": payment_amount,
        }
    except Exception:
        conn.rollback()
        conn.close()
        logger.exception("SMS PROCESSING ERROR")
        return {"ok": False, "reason": "database_error"}


async def sms_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает SMS2 Forwarder независимо от Telegram-отправителя."""
    message = update.effective_message
    if not message or not message.chat:
        return

    # Если указана группа, принимаем SMS только из неё. При 0 — из любого чата.
    if SMS_GROUP_ID and message.chat.id != SMS_GROUP_ID:
        return

    text = message.text or message.caption or ""
    if not text:
        return

    sender_id = message.from_user.id if message.from_user else 0
    result = process_sms_text(text, sender_id)

    if not result.get("ok"):
        if result.get("reason") not in {
            "bank_format_not_found",
            "amount_not_found",
            "payment_not_found",
            "duplicate",
        }:
            logger.info("SMS ignored: %s", result)
        return

    user_id = result["user_id"]
    credited = result["requested_amount"]
    received = result["payment_amount"]

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "✅ <b>Баланс пополнен автоматически!</b>\n\n"
                f"💰 Зачислено: <b>{credited:,} сум</b>\n"
                f"💳 Оплата: <b>{received:,} сум</b>\n\n"
                "Оплата подтверждена по банковскому SMS."
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.exception("AUTO REFILL USER NOTIFICATION ERROR: %s", e)

    if ADMIN_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "🤖 <b>АВТОПОПОЛНЕНИЕ</b>\n\n"
                    f"🆔 Пользователь: <code>{user_id}</code>\n"
                    f"💰 Зачислено: <b>{credited:,} сум</b>\n"
                    f"💳 SMS: <b>{received:,} сум</b>"
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.exception("AUTO REFILL ADMIN NOTIFICATION ERROR: %s", e)


def tr(user_id, key, **kwargs):
    data = get_user(user_id)
    lang = data.get("lang", "ru")

    text = TEXTS.get(lang, TEXTS["ru"]).get(key, key)
    return text.format(**kwargs)


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
# RENDER
# =========================================================

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Bot is running!")

    def log_message(self, format, *args):
        return


def run_web():
    port = int(os.environ.get("PORT", 8080))

    server = HTTPServer(
        ("0.0.0.0", port),
        Handler,
    )

    server.serve_forever()


# =========================================================
# КЛАВИАТУРЫ
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


def shop_keyboard(user_id):
    return InlineKeyboardMarkup([
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
                "📱 Телеграм-аккаунты",
                callback_data="shop_accounts",
            )
        ],
        [
            InlineKeyboardButton(
                tr(user_id, "back"),
                callback_data="back_main",
            )
        ],
    ])


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
# ОСНОВНЫЕ CALLBACK
# =========================================================

async def main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if await check_ban(update):
        return

    await query.answer()

    user = query.from_user
    data = get_user(
        user.id,
        user.username,
        user.first_name,
    )

    callback = query.data

    if callback == "back_main":
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

    if callback == "main_profile":
        username = user.username or "нет username"

        await query.message.edit_text(
            (
                "👤 <b>Мой профиль</b>\n\n"
                f"👤 Username: @{escape(username)}\n"
                f"🆔 ID: <code>{user.id}</code>\n"
                f"💰 Баланс: <b>{data['balance']:,} сум</b>"
            ),
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        tr(user.id, "back"),
                        callback_data="back_main",
                    )
                ]
            ]),
            parse_mode="HTML",
        )
        return

    if callback == "language_menu":
        await query.message.edit_text(
            "🌐 <b>Выберите язык / Tilni tanlang</b>",
            reply_markup=InlineKeyboardMarkup([
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
            ]),
            parse_mode="HTML",
        )
        return

    if callback == "main_shop":
        await query.message.edit_text(
            tr(user.id, "shop"),
            reply_markup=shop_keyboard(user.id),
            parse_mode="HTML",
        )
        return

    if callback == "shop_stars":
        await query.message.edit_text(
            tr(
                user.id,
                "stars",
                price=PRICE_PER_STAR,
            ),
            reply_markup=InlineKeyboardMarkup([
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
            ]),
            parse_mode="HTML",
        )
        return

    if callback == "shop_premium":
        await query.message.edit_text(
            tr(user.id, "premium"),
            reply_markup=InlineKeyboardMarkup([
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
            ]),
            parse_mode="HTML",
        )
        return

    if callback == "shop_gifts":
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

    if callback == "shop_accounts":
        await query.message.edit_text(
            "📱 <b>Выберите страну аккаунта:</b>",
            reply_markup=InlineKeyboardMarkup([
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
            ]),
            parse_mode="HTML",
        )
        return

    if callback.startswith("account_"):
        countries = {
            "account_uz": "Узбекистан",
            "account_co": "Колумбия",
            "account_uk": "Великобритания",
            "account_us": "Америка",
        }

        country = countries.get(callback, "Неизвестная страна")

        await context.bot.send_message(
            ADMIN_ID,
            (
                "📱 <b>НОВЫЙ ЗАКАЗ АККАУНТА</b>\n\n"
                f"🌍 Страна: {escape(country)}\n"
                f"👤 Заказал: "
                f"@{escape(user.username or 'нет username')}\n"
                f"🆔 ID: <code>{user.id}</code>"
            ),
            parse_mode="HTML",
        )

        await query.message.edit_text(
            "✅ <b>Заявка принята!</b>\n\n"
            "Администратор свяжется с вами.",
            parse_mode="HTML",
        )


# =========================================================
# ЯЗЫК
# =========================================================

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
# ELDER API
# =========================================================

async def send_order_to_elder(product_type, value, target):
    order_id = uuid.uuid4().hex[:16]

    headers = {
        "X-Api-Key": ELDER_API_KEY,
    }

    if product_type == "stars":
        url = "https://elder.uz/buyStars"
        params = {
            "username": target,
            "amount": value,
        }
    else:
        url = "https://elder.uz/buyPremium"
        params = {
            "username": target,
            "months": value,
        }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                url,
                headers=headers,
                params=params,
            )

        try:
            data = response.json()
        except ValueError:
            data = {}

        success = bool(data.get("success"))
        error_code = data.get("error_code") or data.get("error")

        # Точная ошибка API видна только в Render Logs.
        logger.info(
            "ELDER API | order_id=%s | type=%s | target=@%s | value=%s | "
            "status=%s | response=%s",
            order_id,
            product_type,
            target,
            value,
            response.status_code,
            response.text,
        )

        if response.status_code not in (200, 201) or not success:
            logger.error(
                "ELDER API FAILED | order_id=%s | status=%s | "
                "error_code=%s | error=%s",
                order_id,
                response.status_code,
                error_code or "UNKNOWN",
                data.get("error", "UNKNOWN"),
            )

            if error_code == "USER_NOT_FOUND":
                return False, "USER_NOT_FOUND"

            return False, error_code or "UNKNOWN"

        logger.info(
            "ELDER API SUCCESS | order_id=%s | type=%s | target=@%s | value=%s",
            order_id,
            product_type,
            target,
            value,
        )

        return True, None

    except httpx.TimeoutException as e:
        logger.exception(
            "ELDER API TIMEOUT | order_id=%s | error=%s",
            order_id,
            e,
        )
        return False, "TIMEOUT"

    except httpx.HTTPError as e:
        logger.exception(
            "ELDER API HTTP ERROR | order_id=%s | error=%s",
            order_id,
            e,
        )
        return False, "HTTP_ERROR"

    except Exception as e:
        logger.exception(
            "ELDER API EXCEPTION | order_id=%s | error=%s",
            order_id,
            e,
        )
        return False, "EXCEPTION"


# =========================================================
# STARS / PREMIUM
# =========================================================

async def buy_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data.clear()

    data = query.data

    if data == "buy_stars":
        context.user_data["product_type"] = "stars"

        await query.message.edit_text(
            tr(query.from_user.id, "enter_stars")
        )

        return BUY_AMOUNT

    if data.startswith("buy_stars_"):
        amount = int(data.split("_")[2])

        context.user_data["product_type"] = "stars"
        context.user_data["amount"] = amount

        await query.message.edit_text(
            tr(query.from_user.id, "enter_username")
        )

        return BUY_USERNAME

    if data.startswith("buy_premium_"):
        months = int(data.split("_")[2])

        context.user_data["product_type"] = "premium"
        context.user_data["amount"] = months

        await query.message.edit_text(
            tr(query.from_user.id, "enter_username")
        )

        return BUY_USERNAME

    return ConversationHandler.END


async def buy_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        tr(update.effective_user.id, "enter_username")
    )

    return BUY_USERNAME


async def buy_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip().replace("@", "")

    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
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
        product = f"Telegram Premium на {amount} мес."

    if price is None:
        await update.message.reply_text("❌ Ошибка товара.")
        return ConversationHandler.END

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

    await update.message.reply_text(
        tr(
            user.id,
            "confirm_order",
            product=product,
            username=username,
            price=price,
        ),
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✅ Купить",
                    callback_data="confirm_buy",
                ),
                InlineKeyboardButton(
                    "❌ Отмена",
                    callback_data="cancel_buy",
                ),
            ]
        ]),
        parse_mode="HTML",
    )

    return BUY_CONFIRM


async def buy_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user

    if query.data == "cancel_buy":
        context.user_data.clear()

        await query.message.edit_text(
            tr(user.id, "cancelled")
        )

        return ConversationHandler.END

    product_type = context.user_data["product_type"]
    amount = context.user_data["amount"]
    username = context.user_data["username"]
    price = context.user_data["price"]
    product = context.user_data["product"]

    await query.message.edit_text(
        tr(user.id, "processing")
    )

    success, error_code = await send_order_to_elder(
        product_type,
        amount,
        username,
    )

    if not success:
        if error_code == "USER_NOT_FOUND":
            await query.message.edit_text(
                "❌ <b>Пользователь не найден.</b>\n\n"
                "Проверьте правильность юзернейма и попробуйте снова.",
                parse_mode="HTML",
            )
        else:
            await query.message.edit_text(
                tr(user.id, "api_error")
            )

        context.user_data.clear()
        return ConversationHandler.END

    # Успешный ответ Elder API.
    change_balance(user.id, -price)

    await query.message.edit_text(
        "✅ <b>Заказ успешно выполнен!</b>\n\n"
        f"📦 Товар: <b>{escape(product)}</b>\n"
        f"👤 Получатель: @{escape(username)}\n"
        f"💰 Списано: <b>{price:,} сум</b>",
        parse_mode="HTML",
    )

    try:
        await context.bot.send_message(
            ADMIN_ID,
            (
                "✅ <b>НОВЫЙ УСПЕШНЫЙ ЗАКАЗ</b>\n\n"
                f"📦 Товар: <b>{escape(product)}</b>\n"
                f"👤 Получатель: @{escape(username)}\n"
                f"👤 Заказал: @{escape(user.username or 'нет username')}\n"
                f"🆔 ID: <code>{user.id}</code>\n"
                f"💰 Сумма: <b>{price:,} сум</b>"
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.exception("ADMIN ORDER NOTIFICATION ERROR: %s", e)

    context.user_data.clear()
    return ConversationHandler.END


# =========================================================
# ПОПОЛНЕНИЕ
# =========================================================

async def refill_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data.clear()

    await query.message.edit_text(
        tr(query.from_user.id, "refill_enter")
    )

    return REFILL_AMOUNT


async def refill_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace(" ", "")

    if not text.isdigit():
        await update.message.reply_text(
            "❌ Введите корректную сумму."
        )
        return REFILL_AMOUNT

    amount = int(text)

    if amount <= 0:
        await update.message.reply_text(
            "❌ Введите корректную сумму."
        )
        return REFILL_AMOUNT

    if SMS_GROUP_ID == 0:
        await update.message.reply_text(
            "❌ Автопополнение пока не настроено администратором."
        )
        return ConversationHandler.END

    try:
        payment_amount = create_auto_refill(
            update.effective_user.id,
            amount,
        )
    except Exception:
        logger.exception("AUTO REFILL CREATE ERROR")
        await update.message.reply_text(
            "❌ Не удалось создать платёж. Попробуйте ещё раз."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        tr(
            update.effective_user.id,
            "refill_payment",
            amount=amount,
            payment_amount=payment_amount,
            card=CARD_NUMBER,
        ),
        parse_mode="HTML",
    )

    context.user_data.clear()
    return ConversationHandler.END


async def payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query.from_user.id != ADMIN_ID:
        await query.answer("❌ Нет доступа.", show_alert=True)
        return

    await query.answer()

    parts = query.data.split("_")

    if parts[0] == "approve":
        user_id = int(parts[2])
        amount = int(parts[3])

        change_balance(user_id, amount)

        await context.bot.send_message(
            user_id,
            (
                "✅ <b>Баланс пополнен!</b>\n\n"
                f"💰 Сумма: {amount:,} сум"
            ),
            parse_mode="HTML",
        )

        await query.edit_message_caption(
            caption=(query.message.caption or "") + "\n\n✅ ОДОБРЕНО",
            parse_mode="HTML",
        )

    else:
        user_id = int(parts[2])

        await context.bot.send_message(
            user_id,
            "❌ Пополнение отклонено.",
        )

        await query.edit_message_caption(
            caption=(query.message.caption or "") + "\n\n❌ ОТКЛОНЕНО",
            parse_mode="HTML",
        )


# =========================================================
# ПОДАРКИ
# =========================================================

async def gift_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    gift_id = int(query.data.split("_")[1])

    context.user_data.clear()
    context.user_data["gift_id"] = gift_id

    await query.message.edit_text(
        tr(query.from_user.id, "gift_send_type"),
        reply_markup=InlineKeyboardMarkup([
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
        ]),
        parse_mode="HTML",
    )

    return GIFT_SEND_TYPE


async def gift_send_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_gift":
        return await cancel(update, context)

    context.user_data["anonymous"] = (
        query.data == "gift_anonymous_yes"
    )

    await query.message.edit_text(
        "📝 <b>Добавить текст к подарку?</b>",
        reply_markup=InlineKeyboardMarkup([
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
        ]),
        parse_mode="HTML",
    )

    return GIFT_TEXT


async def gift_text_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_gift":
        return await cancel(update, context)

    if query.data == "gift_text_yes":
        await query.message.edit_text(
            tr(query.from_user.id, "gift_text")
        )
        return GIFT_TEXT

    context.user_data["gift_text"] = ""

    await query.message.edit_text(
        tr(query.from_user.id, "gift_username")
    )

    return GIFT_USERNAME


async def gift_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["gift_text"] = update.message.text.strip()

    await update.message.reply_text(
        tr(update.effective_user.id, "gift_username")
    )

    return GIFT_USERNAME


async def send_custom_emoji(bot, chat_id, emoji, emoji_id):
    await bot.send_message(
        chat_id=chat_id,
        text=emoji,
        entities=[
            MessageEntity(
                type=MessageEntity.CUSTOM_EMOJI,
                offset=0,
                length=len(emoji.encode("utf-16-le")) // 2,
                custom_emoji_id=emoji_id,
            )
        ],
    )


async def gift_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip().replace("@", "")

    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
        await update.message.reply_text(
            "❌ Введите корректный юзернейм."
        )
        return GIFT_USERNAME

    user = update.effective_user
    gift = GIFTS[context.user_data["gift_id"]]

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

    anonymous = context.user_data.get("anonymous", False)
    gift_text = context.user_data.get("gift_text", "")

    change_balance(user.id, -gift["price"])

    sender = (
        "Анонимно"
        if anonymous
        else f"@{user.username or 'нет username'}"
    )

    await send_custom_emoji(
        context.bot,
        ADMIN_ID,
        gift["emoji"],
        gift["emoji_id"],
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
        tr(user.id, "gift_success")
    )

    context.user_data.clear()
    return ConversationHandler.END


# =========================================================
# ОТМЕНА
# =========================================================

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    user_id = update.effective_user.id

    if update.callback_query:
        query = update.callback_query
        await query.answer()

        await query.message.edit_text(
            tr(user_id, "cancelled")
        )

    else:
        await update.message.reply_text(
            tr(user_id, "cancelled")
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
                "👥 Пользователи",
                callback_data="admin_users",
            )
        ],
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
                "🔴 Забанить",
                callback_data="admin_ban",
            ),
            InlineKeyboardButton(
                "🟢 Разбанить",
                callback_data="admin_unban",
            ),
        ],
        [
            InlineKeyboardButton(
                "💰 Балансы",
                callback_data="admin_balances",
            )
        ],
        [
            InlineKeyboardButton(
                "📨 Отправить SMS по ID",
                callback_data="admin_message",
            )
        ],
        [
            InlineKeyboardButton(
                "📊 Статистика",
                callback_data="admin_stats",
            )
        ],
    ])


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Нет доступа.")
        return

    await update.message.reply_text(
        "🛠 <b>АДМИН-ПАНЕЛЬ</b>",
        reply_markup=admin_keyboard(),
        parse_mode="HTML",
    )


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if not is_admin(query.from_user.id):
        await query.answer("❌ Нет доступа.", show_alert=True)
        return

    await query.answer()

    if query.data == "admin_users":
        users = get_users()

        if not users:
            await query.message.edit_text(
                "👥 Пользователей пока нет.",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "⬅️ Назад",
                            callback_data="admin_back",
                        )
                    ]
                ]),
            )
            return

        text = "👥 <b>ПОЛЬЗОВАТЕЛИ</b>\n\n"

        for index, row in enumerate(users[:50], 1):
            user_id, username, name, balance, lang, banned = row

            username_text = (
                f"@{escape(username)}"
                if username
                else "нет username"
            )

            status = "🔴 БАН" if banned else "🟢 Активен"

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
        return

    if query.data == "admin_balances":
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
        return

    if query.data == "admin_stats":
        users = get_users()

        active = sum(1 for row in users if not row[5])
        banned = sum(1 for row in users if row[5])

        await query.message.edit_text(
            (
                "📊 <b>СТАТИСТИКА</b>\n\n"
                f"👥 Всего: {len(users)}\n"
                f"🟢 Активных: {active}\n"
                f"🔴 Заблокированных: {banned}"
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
        return

    if query.data == "admin_back":
        await query.message.edit_text(
            "🛠 <b>АДМИН-ПАНЕЛЬ</b>",
            reply_markup=admin_keyboard(),
            parse_mode="HTML",
        )


async def admin_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    text = update.message.text.strip()

    if not text.isdigit():
        await update.message.reply_text(
            "❌ Введите правильный Telegram ID."
        )
        return ADMIN_USER_ID

    user_id = int(text)

    if not get_user_exists(user_id):
        await update.message.reply_text(
            "❌ Пользователь с таким ID не найден в базе."
        )
        return ConversationHandler.END

    context.user_data["admin_target_id"] = user_id

    action = context.user_data["admin_action"]

    if action in ("add", "sub"):
        await update.message.reply_text(
            "💰 Введите сумму:"
        )
        return ADMIN_AMOUNT

    if action == "ban":
        set_ban(user_id, True)

        await update.message.reply_text(
            f"🔴 Пользователь <code>{user_id}</code> заблокирован.",
            parse_mode="HTML",
        )

        return ConversationHandler.END

    if action == "unban":
        set_ban(user_id, False)

        await update.message.reply_text(
            f"🟢 Пользователь <code>{user_id}</code> разблокирован.",
            parse_mode="HTML",
        )

        return ConversationHandler.END

    if action == "message":
        await update.message.reply_text(
            "📨 Введите сообщение:"
        )
        return ADMIN_MESSAGE

    return ConversationHandler.END


def get_user_exists(user_id):
    conn = db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT 1 FROM users WHERE user_id = ?",
        (user_id,),
    )

    result = cursor.fetchone() is not None

    conn.close()

    return result


async def admin_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    text = update.message.text.replace(" ", "")

    if not text.isdigit():
        await update.message.reply_text(
            "❌ Введите правильную сумму."
        )
        return ADMIN_AMOUNT

    amount = int(text)

    if amount <= 0:
        await update.message.reply_text(
            "❌ Сумма должна быть больше 0."
        )
        return ADMIN_AMOUNT

    user_id = context.user_data["admin_target_id"]
    action = context.user_data["admin_action"]

    if action == "add":
        change_balance(user_id, amount)

        await update.message.reply_text(
            (
                "✅ Баланс увеличен.\n\n"
                f"🆔 ID: <code>{user_id}</code>\n"
                f"➕ {amount:,} сум"
            ),
            parse_mode="HTML",
        )

        try:
            await context.bot.send_message(
                user_id,
                f"💰 Вам добавили {amount:,} сум на баланс.",
            )
        except Exception:
            pass

    else:
        change_balance(user_id, -amount)

        await update.message.reply_text(
            (
                "✅ Баланс уменьшен.\n\n"
                f"🆔 ID: <code>{user_id}</code>\n"
                f"➖ {amount:,} сум"
            ),
            parse_mode="HTML",
        )

        try:
            await context.bot.send_message(
                user_id,
                f"💰 С вашего баланса списано {amount:,} сум.",
            )
        except Exception:
            pass

    context.user_data.clear()
    return ConversationHandler.END


async def admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    user_id = context.user_data["admin_target_id"]
    text = update.message.text

    try:
        await context.bot.send_message(
            user_id,
            (
                "📨 <b>Сообщение от администратора</b>\n\n"
                f"{escape(text)}"
            ),
            parse_mode="HTML",
        )

        await update.message.reply_text(
            "✅ Сообщение отправлено."
        )

    except Exception as e:
        logger.exception("SEND ADMIN MESSAGE ERROR: %s", e)

        await update.message.reply_text(
            "❌ Не удалось отправить сообщение."
        )

    context.user_data.clear()
    return ConversationHandler.END


async def admin_action_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if not is_admin(query.from_user.id):
        await query.answer("❌ Нет доступа.", show_alert=True)
        return ConversationHandler.END

    await query.answer()

    actions = {
        "admin_add": ("add", "➕ Введите Telegram ID пользователя:"),
        "admin_sub": ("sub", "➖ Введите Telegram ID пользователя:"),
        "admin_ban": ("ban", "🔴 Введите Telegram ID пользователя:"),
        "admin_unban": ("unban", "🟢 Введите Telegram ID пользователя:"),
        "admin_message": ("message", "📨 Введите Telegram ID пользователя:"),
    }

    action, text = actions[query.data]

    context.user_data.clear()
    context.user_data["admin_action"] = action

    await query.message.edit_text(text)

    return ADMIN_USER_ID


# =========================================================
# UNKNOWN CALLBACK
# =========================================================

async def unknown_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer(
        "❌ Эта кнопка больше неактивна.",
        show_alert=True,
    )


# =========================================================
# MAIN
# =========================================================

def main():
    init_db()

    threading.Thread(
        target=run_web,
        daemon=True,
    ).start()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("admin", admin)
    )

    # СНАЧАЛА CALLBACKS, КОТОРЫЕ НЕ В CONVERSATION
    application.add_handler(
        CallbackQueryHandler(
            language_callback,
            pattern=r"^lang_(ru|uz)$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            payment_callback,
            pattern=r"^(approve_refill|reject_refill)_",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            admin_callback,
            pattern=r"^admin_(users|balances|stats|back)$",
        )
    )

    # ВАЖНО:
    # main_callback теперь ловит ТОЛЬКО главные кнопки.
    # Поэтому Stars / Premium / Gifts / Accounts
    # больше НЕ попадают в unknown_callback.
    application.add_handler(
        CallbackQueryHandler(
            main_callback,
            pattern=(
                r"^(back_main|main_profile|main_shop|"
                r"language_menu|shop_stars|shop_premium|"
                r"shop_gifts|shop_accounts|account_)"
            ),
        )
    )

    # ADMIN ACTION CONVERSATION
    admin_conversation = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                admin_action_start,
                pattern=r"^admin_(add|sub|ban|unban|message)$",
            )
        ],
        states={
            ADMIN_USER_ID: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_user_id,
                )
            ],
            ADMIN_AMOUNT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_amount,
                )
            ],
            ADMIN_MESSAGE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_message,
                )
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
        ],
        allow_reentry=True,
    )

    application.add_handler(admin_conversation)

    # REFILL / BUY / GIFTS
    shop_conversation = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                refill_start,
                pattern=r"^main_refill$",
            ),
            CallbackQueryHandler(
                buy_start,
                pattern=r"^buy_(stars|premium)(?:_\d+)?$",
            ),
            CallbackQueryHandler(
                gift_start,
                pattern=r"^gift_\d+$",
            ),
        ],
        states={
            REFILL_AMOUNT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    refill_amount,
                )
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
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(
                cancel,
                pattern=r"^cancel_",
            ),
        ],
        allow_reentry=True,
    )

    application.add_handler(shop_conversation)

    # SMS2 Forwarder -> этот обработчик.
    # Отправитель может быть другим ботом/пользователем.
    # Ставим ПОСЛЕ ConversationHandler, чтобы ввод суммы пополнения
    # пользователем (например, 1000) не перехватывался этим обработчиком.
    application.add_handler(
        MessageHandler(
            filters.ALL,
            sms_group_message,
        )
    )

    # UNKNOWN — САМЫЙ ПОСЛЕДНИЙ
    application.add_handler(
        CallbackQueryHandler(unknown_callback)
    )

    logger.info("BOT STARTED")

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()

