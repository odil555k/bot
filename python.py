import os
import re
import uuid
import sqlite3
import logging
import threading
import json
import hmac
import math
from datetime import datetime
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

# Partner API для автоматической покупки Telegram Stars / Premium.
# Ключ API хранится только в переменных окружения.
PARTNER_API_KEY = os.environ["PARTNER_API_KEY"]
PARTNER_API_URL = os.environ.get(
    "PARTNER_API_URL",
    "https://69544e6345d5c.xvest5.ru/AVOBuilder_v4/bots/AVOStarsUzBot/api/v2",
).rstrip("/")
PARTNER_API_TIMEOUT = float(os.environ.get("PARTNER_API_TIMEOUT", "40"))

# Секрет для связи отдельного клиента с ботом.
CARDXABAR_API_KEY = os.environ["CARDXABAR_API_KEY"]
CARDXABAR_DRY_RUN = os.environ.get("CARDXABAR_DRY_RUN", "false").strip().lower() in {"1", "true", "yes", "on"}

DB_FILE = "bot_database.db"

CARD_NUMBER = os.environ.get(
    "CARD_NUMBER",
    "5614 6812 1542 3546"
)

PRICE_PER_STAR = 220

PREMIUM_PRICES = {
    3: 165000,
    6: 222000,
    12: 406000,
}

# Наценка на номера: 30% прибыли от конечной цены.
# То есть если API/Batu берет 2000 сум, пользователь платит 2000 / 0.70.
NUMBER_PROFIT_PERCENT = 30

def number_sale_price(cost_uzs):
    """Цена для пользователя так, чтобы прибыль составляла 30% от продажи."""
    cost = int(cost_uzs)
    if cost <= 0:
        return 0
    return math.ceil(cost * 100 / (100 - NUMBER_PROFIT_PERCENT))


def country_flag(country_code):
    """Возвращает emoji-флаг по ISO-коду страны, например CA -> 🇨🇦."""
    code = str(country_code or "").strip().upper()
    if len(code) != 2 or not code.isalpha():
        return "🌍"
    return "".join(chr(ord("🇦") + ord(ch) - ord("A")) for ch in code)


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
        "emoji_id": "5280615440928758599",
        "price": 4000,
        "stars": 15,
        "name": "сердце",
    },

    3: {
        "emoji": "🌹",
        "emoji_id": "5280774333243873175",
        "price": 6000,
        "stars": 25,
        "name": "Роза",
    },

    4: {
        "emoji": "🎁",
        "emoji_id": "5283080528818360566",
        "price": 6000,
        "stars": 25,
        "name": "Подарок",
    },

    5: {
        "emoji": "🚀",
        "emoji_id": "5280769763398671636",
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
        "emoji_id": "5280922999241859582",
        "price": 10500,
        "stars": 50,
        "name": "Алмаз",
    },

    8: {
        "emoji": "🍾",
        "emoji_id": "5451905784734574339",
        "price": 10500,
        "stars": 50,
        "name": "Шампанское",
    },

    9: {
        "emoji": "🏆",
        "emoji_id": "5280769763398671636",
        "price": 21000,
        "stars": 100,
        "name": "Кубок",
    },

    10: {
        "emoji": "💍",
        "emoji_id": "5280651583078556009",
        "price": 21000,
        "stars": 100,
        "name": "Кольцо",
    },

    11: {
        "emoji": "💎",
        "emoji_id": "5280922999241859582",
        "price": 21000,
        "stars": 100,
        "name": "Алмаз",
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
            "💰 На баланс: <b>{amount:,} сум</b>\n"
            "💵 Перевести нужно: <b>{payment_amount:,} сум</b>\n\n"
            "Переведите <b>точно эту сумму</b> на карту:\n"
            "<code>{card}</code>\n\n"
            "После перевода чек отправлять не нужно.\n"
            "⏳ После поступления перевода баланс будет пополнен автоматически."
        ),

        "receipt_sent": "⏳ Заявка отправлена администратору.",

        "send_receipt": "❌ Отправьте подтверждение оплаты.",

        "gift_send_type": (
            "🎁 <b>Как отправить подарок?</b>"
        ),

        "gift_text": (
            "✍️ Напишите текст для подарка."
        ),

        "gift_username": (
            "✏️ Введите юзернейм получателя подарка.\n\n"
            "Без символа @"
        ),

        "gift_success": "✅ <b>Подарок успешно куплен!</b>",

        "numbers": (
            "📱 <b>Telegram номера</b>\n\n"
            "Выберите страну. Цена указана за номер."
        ),
        "numbers_empty": "😕 Сейчас доступных номеров нет.",
        "number_buying": "📱 Покупаем номер...",
        "number_success": (
            "✅ <b>Номер куплен!</b>\n\n"
            "🌍 Страна: <b>{country}</b>\n"
            "📞 Номер: <code>{phone}</code>\n"
            "💰 Цена: <b>{price:,} сум</b>\n\n"
            "🆔 Order ID: <code>{order_id}</code>"
        ),
        "number_waiting": (
            "⏳ <b>SMS пока не пришло.</b>\n\n"
            "📞 Номер: <code>{phone}</code>\n"
            "Нажмите кнопку ещё раз через несколько секунд."
        ),
        "number_finished": (
            "✅ <b>SMS получено!</b>\n\n"
            "📞 Номер: <code>{phone}</code>\n"
            "🔢 Код: <code>{code}</code>{password_line}\n\n"
            "🆔 Order ID: <code>{order_id}</code>"
        ),
        "number_orders": "📋 <b>Мои номера</b>",
        "number_no_orders": "📭 У вас пока нет купленных номеров.",
        "api_error_detailed": "❌ API: {message}",

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
            "💰 Balansga: <b>{amount:,} so'm</b>\n"
            "💵 Aynan o'tkazish kerak: <b>{payment_amount:,} so'm</b>\n\n"
            "Kartaga <b>aynan shu summani</b> o'tkazing:\n"
            "<code>{card}</code>\n\n"
            "To'lovdan keyin chek yuborish shart emas.\n"
            "⏳ To'lov kelgach, balans avtomatik to'ldiriladi."
        ),

        "receipt_sent": "⏳ So'rov administratorga yuborildi.",

        "send_receipt": "❌ To'lov tasdig'ini yuboring.",

        "gift_send_type": (
            "🎁 <b>Sovg'ani qanday yuborish?</b>"
        ),

        "gift_text": (
            "✍️ Sovg'aga qo'shiladigan matnni yozing."
        ),

        "gift_username": (
            "✏️ Qabul qiluvchining username'ini kiriting.\n\n"
            "@ belgisiz"
        ),

        "gift_success": "✅ <b>Sovg'a muvaffaqiyatli sotib olindi!</b>",

        "numbers": (
            "📱 <b>Telegram raqamlari</b>\n\n"
            "Davlatni tanlang. Narx bitta raqam uchun."
        ),
        "numbers_empty": "😕 Hozircha mavjud raqamlar yo'q.",
        "number_buying": "📱 Raqam sotib olinmoqda...",
        "number_success": (
            "✅ <b>Raqam sotib olindi!</b>\n\n"
            "🌍 Davlat: <b>{country}</b>\n"
            "📞 Raqam: <code>{phone}</code>\n"
            "💰 Narx: <b>{price:,} so'm</b>\n\n"
            "🆔 Order ID: <code>{order_id}</code>"
        ),
        "number_waiting": (
            "⏳ <b>SMS hali kelmadi.</b>\n\n"
            "📞 Raqam: <code>{phone}</code>\n"
            "Bir necha soniyadan keyin yana tekshiring."
        ),
        "number_finished": (
            "✅ <b>SMS keldi!</b>\n\n"
            "📞 Raqam: <code>{phone}</code>\n"
            "🔢 Kod: <code>{code}</code>{password_line}\n\n"
            "🆔 Order ID: <code>{order_id}</code>"
        ),
        "number_orders": "📋 <b>Mening raqamlarim</b>",
        "number_no_orders": "📭 Sizda hali sotib olingan raqamlar yo'q.",
        "api_error_detailed": "❌ API: {message}",

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

def init_db():

    conn = sqlite3.connect(DB_FILE, timeout=20)

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

    # CardXabar: ожидаемые пополнения.
    # payment_amount — уникальная сумма, которую пользователь должен перевести.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cardxabar_payments (
            payment_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            requested_amount INTEGER NOT NULL,
            payment_amount INTEGER NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        )
    """)

    # CardXabar: защита от повторной обработки одного и того же сообщения.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cardxabar_transactions (
            fingerprint TEXT PRIMARY KEY,
            payment_amount INTEGER NOT NULL,
            raw_text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS number_orders (
            order_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            country_code TEXT,
            country_name TEXT,
            phone TEXT,
            price_uzs INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'waiting',
            sms_code TEXT,
            sms_password TEXT,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def get_user(
    user_id,
    username="",
    name=""
):

    conn = sqlite3.connect(DB_FILE, timeout=20)

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
            (
                user_id,
                username or "",
                name or "",
            ),
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

    conn = sqlite3.connect(DB_FILE, timeout=20)

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE users
        SET lang = ?
        WHERE user_id = ?
        """,
        (lang, user_id),
    )

    conn.commit()
    conn.close()


def change_balance(user_id, amount):

    conn = sqlite3.connect(DB_FILE, timeout=20)

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE users
        SET balance = balance + ?
        WHERE user_id = ?
        """,
        (amount, user_id),
    )

    conn.commit()
    conn.close()


def set_ban(user_id, value):

    conn = sqlite3.connect(DB_FILE, timeout=20)

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE users
        SET is_banned = ?
        WHERE user_id = ?
        """,
        (value, user_id),
    )

    conn.commit()
    conn.close()


def get_users():

    conn = sqlite3.connect(DB_FILE, timeout=20)

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


def save_number_order(order_id, user_id, country_code, country_name, phone, price_uzs, status="waiting"):
    conn = sqlite3.connect(DB_FILE, timeout=20)
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO number_orders
            (order_id, user_id, country_code, country_name, phone, price_uzs, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (order_id, user_id, country_code, country_name, phone, int(price_uzs), status, datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
    finally:
        conn.close()


def update_number_order(order_id, status=None, phone=None, sms_code=None, sms_password=None):
    conn = sqlite3.connect(DB_FILE, timeout=20)
    try:
        fields=[]
        values=[]
        if status is not None:
            fields.append("status = ?"); values.append(status)
        if phone is not None:
            fields.append("phone = ?"); values.append(phone)
        if sms_code is not None:
            fields.append("sms_code = ?"); values.append(sms_code)
        if sms_password is not None:
            fields.append("sms_password = ?"); values.append(sms_password)
        if not fields:
            return
        values.append(order_id)
        conn.execute(f"UPDATE number_orders SET {', '.join(fields)} WHERE order_id = ?", values)
        conn.commit()
    finally:
        conn.close()


def get_number_order(order_id, user_id=None):
    conn=sqlite3.connect(DB_FILE, timeout=20)
    conn.row_factory=sqlite3.Row
    try:
        if user_id is None:
            row=conn.execute("SELECT * FROM number_orders WHERE order_id = ?", (order_id,)).fetchone()
        else:
            row=conn.execute("SELECT * FROM number_orders WHERE order_id = ? AND user_id = ?", (order_id, user_id)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_number_orders(user_id, limit=10):
    conn=sqlite3.connect(DB_FILE, timeout=20)
    conn.row_factory=sqlite3.Row
    try:
        rows=conn.execute("SELECT * FROM number_orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, int(limit))).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def create_cardxabar_payment(user_id, requested_amount):
    """Создаёт уникальную сумму для перевода через CardXabar."""
    if requested_amount < 1000 or requested_amount > 9_999_900:
        raise ValueError("Сумма должна быть от 1000 до 9 999 900 сум.")

    conn = sqlite3.connect(DB_FILE, timeout=20)
    cursor = conn.cursor()

    try:
        for _ in range(200):
            # Двузначный суффикс: например 10000 -> 10047.
            suffix = uuid.uuid4().int % 90 + 10
            payment_amount = requested_amount + suffix

            try:
                payment_id = uuid.uuid4().hex
                cursor.execute(
                    """
                    INSERT INTO cardxabar_payments
                    (payment_id, user_id, requested_amount, payment_amount, status, created_at)
                    VALUES (?, ?, ?, ?, 'pending', ?)
                    """,
                    (
                        payment_id,
                        user_id,
                        requested_amount,
                        payment_amount,
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )
                conn.commit()
                return payment_id, payment_amount
            except sqlite3.IntegrityError:
                # Такая уникальная сумма уже занята другим ожидающим платежом.
                conn.rollback()
                continue

        raise RuntimeError("Не удалось создать уникальную сумму платежа.")
    finally:
        conn.close()


def get_cardxabar_payment(payment_amount):
    conn = sqlite3.connect(DB_FILE, timeout=20)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT payment_id, user_id, requested_amount, payment_amount, status, created_at
        FROM cardxabar_payments
        WHERE payment_amount = ? AND status = 'pending'
        ORDER BY created_at ASC
        LIMIT 1
        """,
        (payment_amount,),
    )
    row = cursor.fetchone()
    conn.close()
    return row


def mark_cardxabar_test_transaction(fingerprint, payment_amount, raw_text):
    """Записывает найденную транзакцию. Баланс НЕ меняет."""
    conn = sqlite3.connect(DB_FILE, timeout=20)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO cardxabar_transactions
            (fingerprint, payment_amount, raw_text, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                fingerprint,
                payment_amount,
                raw_text,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        conn.rollback()
        return False
    finally:
        conn.close()


def tr(user_id, key, **kwargs):

    data = get_user(user_id)

    lang = data.get("lang", "ru")

    text = TEXTS.get(
        lang,
        TEXTS["ru"],
    ).get(
        key,
        key,
    )

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

            await update.message.reply_text(
                "❌ Вы заблокированы."
            )

        elif update.callback_query:

            await update.callback_query.answer(
                "❌ Вы заблокированы.",
                show_alert=True,
            )

        return True

    return False


# =========================================================
# RENDER WEB SERVER
# =========================================================

def send_json(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def notify_user_balance(user_id, credited_amount):
    """Отправляет пользователю уведомление после успешного пополнения."""
    try:
        user = get_user(user_id)
        lang = user.get("lang", "ru")
        if lang == "uz":
            text = (
                "✅ <b>Balans muvaffaqiyatli to'ldirildi!</b>\n\n"
                f"💰 Qo'shildi: <b>{credited_amount:,} so'm</b>\n"
                f"💳 Joriy balans: <b>{user['balance']:,} so'm</b>"
            )
        else:
            text = (
                "✅ <b>Баланс успешно пополнен!</b>\n\n"
                f"💰 Зачислено: <b>{credited_amount:,} сум</b>\n"
                f"💳 Текущий баланс: <b>{user['balance']:,} сум</b>"
            )

        response = httpx.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": user_id,
                "text": text,
                "parse_mode": "HTML",
            },
            timeout=15,
        )
        response.raise_for_status()
    except Exception:
        logger.exception("BALANCE NOTIFICATION ERROR | user_id=%s", user_id)


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path != "/":
            send_json(self, 404, {"ok": False, "error": "Not found"})
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot is running!")

    def do_POST(self):
        if self.path != "/cardxabar":
            send_json(self, 404, {"ok": False, "error": "Not found"})
            return

        supplied_key = self.headers.get("X-CardXabar-Key", "")
        if not supplied_key or not hmac.compare_digest(supplied_key, CARDXABAR_API_KEY):
            send_json(self, 401, {"ok": False, "error": "Unauthorized"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > 256_000:
                send_json(self, 400, {"ok": False, "error": "Invalid request size"})
                return

            raw_body = self.rfile.read(content_length)
            payload = json.loads(raw_body.decode("utf-8"))

            payment_amount = int(payload.get("payment_amount", 0))
            fingerprint = str(payload.get("fingerprint", "")).strip()
            raw_text = str(payload.get("raw_text", ""))[:10000]

            if payment_amount <= 0:
                send_json(self, 400, {"ok": False, "error": "Invalid amount"})
                return

            if not fingerprint or len(fingerprint) > 128:
                send_json(self, 400, {"ok": False, "error": "Invalid fingerprint"})
                return

        except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
            send_json(self, 400, {"ok": False, "error": "Invalid JSON"})
            return

        conn = sqlite3.connect(DB_FILE, timeout=20)
        conn.row_factory = sqlite3.Row

        try:
            conn.execute("BEGIN IMMEDIATE")

            duplicate = conn.execute(
                "SELECT 1 FROM cardxabar_transactions WHERE fingerprint = ? LIMIT 1",
                (fingerprint,),
            ).fetchone()

            if duplicate:
                conn.commit()
                send_json(self, 200, {"ok": True, "status": "duplicate"})
                return

            payment = conn.execute(
                """
                SELECT payment_id, user_id, requested_amount, payment_amount, status, created_at
                FROM cardxabar_payments
                WHERE payment_amount = ?
                  AND status = 'pending'
                  AND datetime(created_at) >= datetime('now', '-60 minutes')
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (payment_amount,),
            ).fetchone()

            if not payment:
                conn.rollback()
                send_json(self, 404, {"ok": True, "status": "payment_not_found"})
                return

            user = conn.execute(
                "SELECT user_id, balance FROM users WHERE user_id = ?",
                (payment["user_id"],),
            ).fetchone()

            if not user:
                conn.rollback()
                send_json(self, 404, {"ok": False, "error": "User not found"})
                return

            if CARDXABAR_DRY_RUN:
                conn.rollback()
                send_json(
                    self,
                    200,
                    {
                        "ok": True,
                        "status": "found",
                        "payment_id": payment["payment_id"],
                        "user_id": payment["user_id"],
                        "requested_amount": payment["requested_amount"],
                        "payment_amount": payment["payment_amount"],
                    },
                )
                return

            conn.execute(
                """
                INSERT INTO cardxabar_transactions
                (fingerprint, payment_amount, raw_text, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    fingerprint,
                    payment_amount,
                    raw_text,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )

            conn.execute(
                """
                UPDATE users
                SET balance = balance + ?
                WHERE user_id = ?
                """,
                (payment["requested_amount"], payment["user_id"]),
            )

            conn.execute(
                """
                UPDATE cardxabar_payments
                SET status = 'paid'
                WHERE payment_id = ? AND status = 'pending'
                """,
                (payment["payment_id"],),
            )

            new_balance = conn.execute(
                "SELECT balance FROM users WHERE user_id = ?",
                (payment["user_id"],),
            ).fetchone()["balance"]

            conn.commit()

            user_id = payment["user_id"]
            credited_amount = payment["requested_amount"]

            send_json(
                self,
                200,
                {
                    "ok": True,
                    "status": "credited",
                    "payment_id": payment["payment_id"],
                    "user_id": user_id,
                    "credited_amount": credited_amount,
                    "balance": new_balance,
                },
            )

        except sqlite3.IntegrityError:
            conn.rollback()
            send_json(self, 200, {"ok": True, "status": "duplicate"})
        except Exception:
            conn.rollback()
            logger.exception("PAYMENT PROCESSING ERROR")
            send_json(self, 500, {"ok": False, "error": "Internal server error"})
        finally:
            conn.close()

        # Уведомление отправляется только после успешного commit.
        if not CARDXABAR_DRY_RUN and 'user_id' in locals() and 'credited_amount' in locals():
            notify_user_balance(user_id, credited_amount)

    def log_message(self, format, *args):
        return


def run_web():
    port = int(os.environ.get("PORT", 8080))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    logger.info("WEB SERVER STARTED ON PORT %s", port)
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
                    "📱 Номера",
                    callback_data="shop_numbers",
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
                    "50 Stars — 11 000 сум",
                    callback_data="buy_stars_50",
                )
            ],

            [
                InlineKeyboardButton(
                    "100 Stars — 22 000 сум",
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


    if query.data == "shop_numbers":
        result = await get_number_countries()
        if result.get("ok") is not True:
            await query.message.edit_text(
                tr(user.id,"api_error_detailed",message=result.get("message","Ошибка API")),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tr(user.id,"back"),callback_data="main_shop")]]),
                parse_mode="HTML",
            )
            return
        countries=result.get("result") or []
        if not countries:
            await query.message.edit_text(tr(user.id,"numbers_empty"),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tr(user.id,"back"),callback_data="main_shop")]]))
            return
        keyboard=[]
        for item in countries[:40]:
            code=str(item.get("code","")).upper()
            name=str(item.get("name",code))
            cost=int(item.get("price_uzs",0))
            sale_price=number_sale_price(cost)
            if not code or cost<=0 or sale_price<=0:
                continue

            flag=country_flag(code)

            keyboard.append([
                InlineKeyboardButton(
                    f"{flag} {name} — {sale_price:,} сум",
                    callback_data=f"number_country_{code}",
                )
            ])
        keyboard.append([InlineKeyboardButton("📋 Мои номера",callback_data="numbers_orders")])
        keyboard.append([InlineKeyboardButton(tr(user.id,"back"),callback_data="main_shop")])
        await query.message.edit_text(tr(user.id,"numbers"),reply_markup=InlineKeyboardMarkup(keyboard),parse_mode="HTML")
        return

    if query.data == "shop_gifts":
        result=await get_api_gifts()
        if result.get("ok") is not True:
            await query.message.edit_text(tr(user.id,"api_error_detailed",message=result.get("message","Ошибка API")),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tr(user.id,"back"),callback_data="main_shop")]]),parse_mode="HTML")
            return
        gifts=result.get("result") or []
        if not gifts:
            await query.message.edit_text("🎁 Сейчас доступных подарков нет.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tr(user.id,"back"),callback_data="main_shop")]]))
            return
        keyboard=[]
        for index,gift in enumerate(gifts[:30],1):
            gift_id=str(gift.get("gift_id",""))
            price=int(gift.get("price_uzs",0))
            if not gift_id or price<=0:
                continue
            keyboard.append([InlineKeyboardButton(f"🎁 Подарок #{index} — {price:,} сум",callback_data=f"giftapi_{gift_id}")])
        keyboard.append([InlineKeyboardButton(tr(user.id,"back"),callback_data="main_shop")])
        await query.message.edit_text("🎁 <b>Актуальные подарки</b>\n\nЦена загружается напрямую из API.",reply_markup=InlineKeyboardMarkup(keyboard),parse_mode="HTML")
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
# TELEGRAM STARS & PREMIUM PARTNER API v2
# =========================================================

async def partner_api_request(endpoint, method="GET", payload=None, idempotency_key=None):
    api_key = (PARTNER_API_KEY or "").strip().strip('"').strip("'")
    url = f"{PARTNER_API_URL}{endpoint}"
    headers = {
        "X-API-Key": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if idempotency_key:
        headers["X-Idempotency-Key"] = idempotency_key

    try:
        async with httpx.AsyncClient(timeout=PARTNER_API_TIMEOUT, follow_redirects=True) as client:
            if method.upper() == "POST":
                response = await client.post(url, headers=headers, json=payload or {})
            else:
                response = await client.get(url, headers=headers)

        logger.info(
            "PARTNER API v2 RESPONSE | endpoint=%s | HTTP=%s | BODY=%s",
            endpoint, response.status_code, response.text[:2000],
        )
        try:
            data=response.json()
        except Exception:
            return {"ok":False,"message":"API returned invalid JSON","_http_status":response.status_code}
        if not isinstance(data,dict):
            return {"ok":False,"message":"API returned invalid response","_http_status":response.status_code}
        data["_http_status"]=response.status_code
        return data
    except httpx.TimeoutException:
        logger.error("PARTNER API TIMEOUT | endpoint=%s", endpoint)
        return {"ok":False,"message":"API timeout","_http_status":0}
    except httpx.HTTPError as e:
        logger.error("PARTNER API HTTP ERROR | endpoint=%s | error=%s", endpoint, e)
        return {"ok":False,"message":str(e),"_http_status":0}
    except Exception as e:
        logger.exception("PARTNER API ERROR | endpoint=%s | error=%s", endpoint, e)
        return {"ok":False,"message":str(e),"_http_status":0}


async def check_telegram_user(username: str):
    res=await partner_api_request("/getInfo",method="POST",payload={"username":username})
    if res.get("_http_status")==404:
        return False,"User not found"
    if res.get("ok") is True:
        return True,res.get("result")
    return False,res.get("message","Unknown error")


async def get_number_countries():
    return await partner_api_request("/numbers/countries",method="GET")


async def buy_number(country_code,idempotency_key):
    return await partner_api_request(
        "/numbers/buy",method="POST",
        payload={"country_code":country_code},idempotency_key=idempotency_key,
    )


async def get_number_code(order_id):
    return await partner_api_request(f"/numbers/code/{order_id}",method="GET")


async def get_api_gifts():
    return await partner_api_request("/gifts",method="GET")


async def buy_api_gift(username,gift_id,comment,anonymous,idempotency_key):
    payload={"username":username,"gift_id":str(gift_id),"anonymous":bool(anonymous)}
    if comment:
        payload["comment"]=str(comment)[:200]
    return await partner_api_request(
        "/gift/buy",method="POST",payload=payload,idempotency_key=idempotency_key,
    )


async def send_order_to_partner(product_type,value,target,telegram_user_id):
    target=target.replace("@","").strip()
    idem_key=f"order-{product_type}-{telegram_user_id}-{int(datetime.now().timestamp())}"
    if product_type=="stars":
        endpoint="/stars/buy"
        payload={"username":target,"amount":int(value)}
    elif product_type=="premium":
        endpoint="/premium/buy"
        months=int(value)
        if months not in {3,6,12}:
            logger.error("INVALID PREMIUM MONTHS: %s",months)
            return False,None
        payload={"username":target,"duration":months}
    else:
        logger.error("UNKNOWN PRODUCT TYPE: %s",product_type)
        return False,None
    result=await partner_api_request(endpoint,method="POST",payload=payload,idempotency_key=idem_key)
    if result.get("ok") is True:
        result_data=result.get("result") or {}
        order_id=result_data.get("order_id") if isinstance(result_data,dict) else None
        logger.info("PARTNER ORDER SUCCESS | type=%s | target=%s | value=%s | order_id=%s",product_type,target,value,order_id)
        return True,order_id
    logger.error("PARTNER ORDER FAILED | type=%s | target=%s | value=%s | HTTP=%s | message=%s | response=%s",product_type,target,value,result.get("_http_status"),result.get("message","Unknown error"),str(result)[:2000])
    return False,None


# =========================================================
# ПОКУПКА STARS / PREMIUM
# =========================================================
async def buy_start(update, context):

    query = update.callback_query
    await query.answer()

    context.user_data.clear()

    data = query.data

    # Покупка Stars: ввод своего количества
    if data == "buy_stars":

        context.user_data["product_type"] = "stars"

        await query.message.edit_text(
            tr(
                query.from_user.id,
                "enter_stars",
            )
        )

        return BUY_AMOUNT

    # Покупка Stars: готовые варианты
    if data.startswith("buy_stars_"):

        amount = int(data.split("_")[2])

        context.user_data["product_type"] = "stars"
        context.user_data["amount"] = amount

        await query.message.edit_text(
            f"⭐ Вы выбрали {amount} Stars.\n\nВведите @username Telegram:"
        )

        return BUY_USERNAME

    # Покупка Premium


    if data.startswith("buy_premium_"):

        months = int(
            data.split("_")[2]
        )

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

    username = update.message.text.strip()

    username = username.replace("@", "")

    if not re.fullmatch(
        r"[A-Za-z0-9_]{5,32}",
        username,
    ):

        await update.message.reply_text(
            "❌ Введите корректный юзернейм."
        )

        return BUY_USERNAME

    user = update.effective_user

    product_type = context.user_data.get(
        "product_type"
    )

    amount = context.user_data.get(
        "amount"
    )

    if product_type == "stars":

        price = amount * PRICE_PER_STAR

        product = f"{amount} Stars"

    else:

        price = PREMIUM_PRICES.get(amount)

        product = (
            f"Telegram Premium на "
            f"{amount} мес."
        )

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

    keyboard = [

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

    ]

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

            tr(
                user.id,
                "cancelled",
            )

        )

        return ConversationHandler.END

    product_type = context.user_data["product_type"]

    amount = context.user_data["amount"]

    username = context.user_data["username"]

    price = context.user_data["price"]

    product = context.user_data["product"]

    await query.message.edit_text(

        tr(
            user.id,
            "processing",
        )

    )

    success, order_id = await send_order_to_partner(

        product_type,

        amount,

        username,

    )

    if not success:

        await query.message.edit_text(

            tr(
                user.id,
                "api_error",
            )

        )

        context.user_data.clear()

        return ConversationHandler.END

    change_balance(
        user.id,
        -price,
    )

    await context.bot.send_message(

        ADMIN_ID,

        (

            "🛒 <b>НОВЫЙ ЗАКАЗ</b>\n\n"

            f"📦 Товар: {escape(product)}\n"

            f"👤 Получатель: @{escape(username)}\n"

            f"💰 Цена: {price:,} сум\n"
            f"🧾 Order ID: <code>{escape(str(order_id or 'не указан'))}</code>\n"

            f"🆔 ID заказчика: "
            f"<code>{user.id}</code>\n"

            f"👤 Заказал: "
            f"@{escape(user.username or 'нет username')}"

        ),

        parse_mode="HTML",

    )

    await query.message.edit_text(

        (

            "✅ <b>Заказ успешно выполнен!</b>\n\n"

            f"📦 {escape(product)}\n"
            f"👤 Получатель: @{escape(username)}\n"
            f"🧾 Order ID: <code>{escape(str(order_id or 'не указан'))}</code>"

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
    text = update.message.text.replace(" ", "").replace("_", "")

    if not text.isdigit():
        await update.message.reply_text(
            "❌ Введите корректную сумму цифрами. Например: 10000"
        )
        return REFILL_AMOUNT

    amount = int(text)

    # Для уникальной суммы нужно оставить место под суффикс 10–99.
    if amount < 1000:
        await update.message.reply_text(
            "❌ Минимальная сумма пополнения — 1 000 сум."
        )
        return REFILL_AMOUNT

    if amount > 9_999_900:
        await update.message.reply_text(
            "❌ Максимальная сумма для этого способа — 9 999 900 сум."
        )
        return REFILL_AMOUNT

    user = update.effective_user

    try:
        payment_id, payment_amount = create_cardxabar_payment(
            user.id,
            amount,
        )
    except Exception as e:
        logger.exception("CARDXABAR PAYMENT CREATE ERROR: %s", e)
        await update.message.reply_text(
            "❌ Не удалось создать платёж. Попробуйте ещё раз."
        )
        return REFILL_AMOUNT

    context.user_data["cardxabar_payment_id"] = payment_id
    context.user_data["refill_amount"] = amount
    context.user_data["payment_amount"] = payment_amount

    await update.message.reply_text(
        tr(
            user.id,
            "refill_payment",
            amount=amount,
            payment_amount=payment_amount,
            card=CARD_NUMBER,
        ),
        parse_mode="HTML",
    )

    logger.info(
        "CARDXABAR PAYMENT CREATED | payment_id=%s | user_id=%s | requested=%s | payment_amount=%s",
        payment_id,
        user.id,
        amount,
        payment_amount,
    )

    context.user_data.clear()
    return ConversationHandler.END


async def refill_check(update, context):

    if not update.message.photo:

        await update.message.reply_text(

            tr(
                update.effective_user.id,
                "send_receipt",
            )

        )

        return REFILL_CHECK

    user = update.effective_user

    amount = context.user_data.get(
        "refill_amount",
        0,
    )

    photo = update.message.photo[-1]

    caption = (

        "💳 <b>НОВОЕ ПОПОЛНЕНИЕ</b>\n\n"

        f"👤 Пользователь: "
        f"@{escape(user.username or 'нет username')}\n"

        f"🆔 ID: <code>{user.id}</code>\n"

        f"💰 Сумма: <b>{amount:,} сум</b>"

    )

    keyboard = InlineKeyboardMarkup([

        [

            InlineKeyboardButton(

                "✅ Одобрить",

                callback_data=(
                    f"approve_refill_{user.id}_{amount}"
                ),

            ),

            InlineKeyboardButton(

                "❌ Отклонить",

                callback_data=(
                    f"reject_refill_{user.id}"
                ),

            ),

        ]

    ])

    await context.bot.send_photo(

        chat_id=ADMIN_ID,

        photo=photo.file_id,

        caption=caption,

        parse_mode="HTML",

        reply_markup=keyboard,

    )

    await update.message.reply_text(

        tr(
            user.id,
            "receipt_sent",
        )

    )

    context.user_data.clear()

    return ConversationHandler.END


async def payment_callback(update, context):

    query = update.callback_query

    if query.from_user.id != ADMIN_ID:
        await query.answer("❌ Нет доступа.", show_alert=True)
        return

    await query.answer()

    parts = query.data.split("_")

    if query.data.startswith("approve_refill_"):

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
            reply_markup=None,
        )

    elif query.data.startswith("reject_refill_"):

        user_id = int(parts[2])

        await context.bot.send_message(
            user_id,
            "❌ Пополнение отклонено.",
        )

        await query.edit_message_caption(
            caption=(query.message.caption or "") + "\n\n❌ ОТКЛОНЕНО",
            parse_mode="HTML",
            reply_markup=None,
        )


# =========================================================
# ПОДАРКИ
# =========================================================

async def gift_start(update, context):
    query=update.callback_query
    await query.answer()
    gift_id=query.data.split("giftapi_",1)[1]
    result=await get_api_gifts()
    if result.get("ok") is not True:
        await query.message.edit_text(tr(query.from_user.id,"api_error_detailed",message=result.get("message","Ошибка API")),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tr(query.from_user.id,"back"),callback_data="main_shop")]]),parse_mode="HTML")
        return ConversationHandler.END
    gift=next((item for item in (result.get("result") or []) if str(item.get("gift_id"))==str(gift_id)),None)
    if not gift:
        await query.message.edit_text("❌ Этот подарок больше недоступен.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎁 Обновить подарки",callback_data="shop_gifts")]]))
        return ConversationHandler.END
    price=int(gift.get("price_uzs",0))
    if price<=0:
        await query.message.edit_text("❌ API не вернул цену подарка.")
        return ConversationHandler.END
    context.user_data.clear()
    context.user_data["gift_api_id"]=str(gift_id)
    context.user_data["gift_api_price"]=price
    keyboard=[
        [InlineKeyboardButton("👤 Отправить не анонимно",callback_data="gift_anonymous_no")],
        [InlineKeyboardButton("🕵️ Отправить анонимно",callback_data="gift_anonymous_yes")],
        [InlineKeyboardButton("❌ Отмена",callback_data="cancel_gift")],
    ]
    await query.message.edit_text(f"🎁 <b>Подарок</b>\n\n💰 Цена: <b>{price:,} сум</b>\n\nКак отправить подарок?",reply_markup=InlineKeyboardMarkup(keyboard),parse_mode="HTML")
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

    await bot.send_message(

        chat_id=chat_id,

        text=emoji,

        entities=[

            MessageEntity(

                type=MessageEntity.CUSTOM_EMOJI,

                offset=0,

                length=2,

                custom_emoji_id=emoji_id,

            )

        ],

    )


async def gift_username(update, context):
    username=update.message.text.strip().replace("@","")
    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}",username):
        await update.message.reply_text("❌ Введите корректный юзернейм.")
        return GIFT_USERNAME
    user=update.effective_user
    gift_id=str(context.user_data.get("gift_api_id") or "")
    price=int(context.user_data.get("gift_api_price") or 0)
    anonymous=bool(context.user_data.get("anonymous",False))
    gift_text=str(context.user_data.get("gift_text", ""))[:200]
    if not gift_id or price<=0:
        await update.message.reply_text("❌ Параметры подарка потеряны. Откройте раздел подарков заново.")
        context.user_data.clear()
        return ConversationHandler.END
    data=get_user(user.id,user.username,user.first_name)
    if data["balance"]<price:
        await update.message.reply_text(tr(user.id,"not_enough",price=price,balance=data["balance"]))
        context.user_data.clear()
        return ConversationHandler.END
    status_msg=await update.message.reply_text("🔍 Проверяем username...")
    valid,info=await check_telegram_user(username)
    if not valid:
        await status_msg.edit_text(tr(user.id,"api_error_detailed",message=str(info)))
        context.user_data.clear()
        return ConversationHandler.END
    await status_msg.edit_text("🎁 Оформляем подарок через API...")
    idem_key=f"gift-{user.id}-{gift_id}-{update.message.message_id}"
    result=await buy_api_gift(username,gift_id,gift_text,anonymous,idem_key)
    if result.get("ok") is not True:
        await status_msg.edit_text(tr(user.id,"api_error_detailed",message=result.get("message","Не удалось купить подарок")),parse_mode="HTML")
        context.user_data.clear()
        return ConversationHandler.END
    api_result=result.get("result") or {}
    actual_price=int(api_result.get("cost_uzs") or price)
    order_id=str(api_result.get("order_id") or "")
    change_balance(user.id,-actual_price)
    try:
        await context.bot.send_message(
            ADMIN_ID,
            ("🎁 <b>НОВЫЙ API ЗАКАЗ ПОДАРКА</b>\n\n"
             f"🎁 Gift ID: <code>{escape(gift_id)}</code>\n"
             f"💰 Цена: {actual_price:,} сум\n"
             f"👤 Заказал: @{escape(user.username or 'нет username')}\n"
             f"🆔 ID: <code>{user.id}</code>\n"
             f"🎯 Получатель: @{escape(username)}\n"
             f"📝 Текст: {escape(gift_text) if gift_text else 'без текста'}\n"
             f"🕵️ Анонимно: {'да' if anonymous else 'нет'}\n"
             f"🧾 Order ID: <code>{escape(order_id or 'не указан')}</code>"),
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("GIFT ADMIN NOTIFICATION ERROR")
    await status_msg.edit_text(
        ("✅ <b>Подарок успешно куплен!</b>\n\n"
         f"🎁 Gift ID: <code>{escape(gift_id)}</code>\n"
         f"👤 Получатель: @{escape(username)}\n"
         f"💰 Списано: <b>{actual_price:,} сум</b>\n"
         f"🧾 Order ID: <code>{escape(order_id or 'не указан')}</code>"),
        parse_mode="HTML",
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

        await query.answer()

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


async def admin_callback(update, context):

    query = update.callback_query

    await query.answer()

    if not is_admin(query.from_user.id):
        return

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

                else

                "нет username"

            )

            status = (

                "🔴 БАН"

                if banned

                else

                "🟢 Активен"

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

        return ConversationHandler.END


    if data == "admin_back":

        await query.message.edit_text(

            "🛠 <b>АДМИН-ПАНЕЛЬ</b>",

            reply_markup=admin_keyboard(),

            parse_mode="HTML",

        )

        return ConversationHandler.END


# =========================================================
# АДМИН: ДОБАВИТЬ БАЛАНС
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

    change_balance(user_id, amount)

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

    change_balance(user_id, -amount)

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

    await context.bot.send_message(

        user_id,

        "🔨 Вы были заблокированы администрацией.",

    )

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

    await context.bot.send_message(

        user_id,

        "🔓 Вы были разблокированы администрацией.",

    )

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

    except Exception as e:

        logger.exception(e)

        await update.message.reply_text(

            "❌ Не удалось отправить сообщение.\n"
            "Возможно, пользователь заблокировал бота."

        )

    context.user_data.clear()

    return ConversationHandler.END


# =========================================================
# НОМЕРА: ПОКУПКА И SMS
# =========================================================

async def number_callback(update, context):
    query=update.callback_query
    await query.answer()
    user=query.from_user

    if query.data=="numbers_orders":
        orders=get_user_number_orders(user.id,10)
        if not orders:
            await query.message.edit_text(tr(user.id,"number_no_orders"),reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📱 Купить номер",callback_data="shop_numbers")],
                [InlineKeyboardButton(tr(user.id,"back"),callback_data="main_shop")],
            ]))
            return
        text=tr(user.id,"number_orders")+"\n\n"
        keyboard=[]
        for order in orders:
            phone=order.get("phone") or "номер не указан"
            status_text="✅ SMS готов" if order.get("status")=="finished" else "⏳ Ожидание SMS"
            country_code=str(order.get("country_code") or "").upper()
            country_name=escape(order.get('country_name') or country_code)
            flag=country_flag(country_code)
            text+=(f"{flag} {country_name}\n"
                    f"📞 <code>{escape(phone)}</code>\n{status_text}\n"
                    f"🆔 <code>{escape(order['order_id'])}</code>\n\n")
            keyboard.append([InlineKeyboardButton(f"📩 Проверить SMS — {phone}",callback_data=f"number_code_{order['order_id']}")])
        keyboard.append([InlineKeyboardButton("📱 Купить ещё",callback_data="shop_numbers")])
        keyboard.append([InlineKeyboardButton(tr(user.id,"back"),callback_data="main_shop")])
        await query.message.edit_text(text,reply_markup=InlineKeyboardMarkup(keyboard),parse_mode="HTML")
        return

    if query.data.startswith("number_country_"):
        country_code=query.data.split("number_country_",1)[1].upper()
        user_data=get_user(user.id,user.username,user.first_name)
        result=await get_number_countries()
        if result.get("ok") is not True:
            await query.message.edit_text(tr(user.id,"api_error_detailed",message=result.get("message","Ошибка API")),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 Назад к номерам",callback_data="shop_numbers")]]),parse_mode="HTML")
            return
        country=next((item for item in (result.get("result") or []) if str(item.get("code","")).upper()==country_code),None)
        if not country:
            await query.message.edit_text("❌ Эта страна больше недоступна.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 Обновить список",callback_data="shop_numbers")]]))
            return
        api_cost=int(country.get("price_uzs",0))
        country_name=str(country.get("name") or country_code)
        sale_price=number_sale_price(api_cost)

        if api_cost<=0 or sale_price<=0:
            await query.message.edit_text("❌ API не вернул цену для этой страны.")
            return

        if user_data["balance"]<sale_price:
            await query.message.edit_text(
                tr(
                    user.id,
                    "not_enough",
                    price=sale_price,
                    balance=user_data["balance"],
                ),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📱 Назад к номерам",callback_data="shop_numbers")]
                ]),
            )
            return
        await query.message.edit_text(tr(user.id,"number_buying"))
        idem_key=f"number-{user.id}-{country_code}-{query.message.message_id}"
        buy_result=await buy_number(country_code,idem_key)
        if buy_result.get("ok") is not True:
            await query.message.edit_text(tr(user.id,"api_error_detailed",message=buy_result.get("message","Не удалось купить номер")),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 Вернуться к номерам",callback_data="shop_numbers")]]),parse_mode="HTML")
            return
        api_result=buy_result.get("result") or {}
        order_id=str(api_result.get("order_id") or "")
        phone=str(api_result.get("phone") or "")
        actual_cost=int(api_result.get("cost_uzs") or api_cost)
        actual_sale_price=number_sale_price(actual_cost)
        actual_country_name=str(api_result.get("country_name") or country_name)
        if not order_id:
            await query.message.edit_text("❌ API не вернул order_id.")
            return

        # На момент покупки показываем/списываем цену с нашей наценкой 30%.
        # API/Batu получает свою себестоимость actual_cost, разница остается у магазина.
        if user_data["balance"]<actual_sale_price:
            logger.error(
                "NUMBER PRICE CHANGED AFTER API BUY | user_id=%s | country=%s | balance=%s | sale_price=%s | api_cost=%s",
                user.id,
                country_code,
                user_data["balance"],
                actual_sale_price,
                actual_cost,
            )
            await query.message.edit_text(
                "❌ Цена номера изменилась. Заказ выполнен API, но баланса пользователя недостаточно для списания. "
                "Свяжитесь с администратором.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 Мои номера",callback_data="numbers_orders")]
                ]),
            )
            return

        change_balance(user.id,-actual_sale_price)
        save_number_order(
            order_id,
            user.id,
            country_code,
            actual_country_name,
            phone,
            actual_sale_price,
            "waiting",
        )

        try:
            await context.bot.send_message(
                ADMIN_ID,
                (
                    "📱 <b>НОВЫЙ ЗАКАЗ НОМЕРА</b>\n\n"
                    f"🌍 Страна: {escape(actual_country_name)}\n"
                    f"📞 Номер: <code>{escape(phone)}</code>\n"
                    f"💰 Цена для клиента: {actual_sale_price:,} сум\n"
                    f"🏷 Себестоимость API: {actual_cost:,} сум\n"
                    f"📈 Доход: {actual_sale_price - actual_cost:,} сум\n"
                    f"🆔 Пользователь: <code>{user.id}</code>\n"
                    f"👤 @{escape(user.username or 'нет username')}\n"
                    f"🧾 Order ID: <code>{escape(order_id)}</code>"
                ),
                parse_mode="HTML",
            )
        except Exception:
            logger.exception("NUMBER ADMIN NOTIFICATION ERROR")

        keyboard=[
            [InlineKeyboardButton("📩 Проверить SMS",callback_data=f"number_code_{order_id}")],
            [InlineKeyboardButton("📋 Мои номера",callback_data="numbers_orders")],
            [InlineKeyboardButton("📱 Купить ещё",callback_data="shop_numbers")],
        ]

        await query.message.edit_text(
            tr(
                user.id,
                "number_success",
                country=actual_country_name,
                phone=phone,
                price=actual_sale_price,
                order_id=order_id,
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
        return

    if query.data.startswith("number_code_"):
        order_id=query.data.split("number_code_",1)[1]
        order=get_number_order(order_id,user.id)
        if not order:
            await query.message.edit_text("❌ Заказ номера не найден.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📋 Мои номера",callback_data="numbers_orders")]]))
            return
        result=await get_number_code(order_id)
        if result.get("ok") is not True:
            await query.message.edit_text(tr(user.id,"api_error_detailed",message=result.get("message","Не удалось получить SMS")),reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📩 Проверить ещё раз",callback_data=f"number_code_{order_id}")],
                [InlineKeyboardButton("📋 Мои номера",callback_data="numbers_orders")],
            ]),parse_mode="HTML")
            return
        api_result=result.get("result") or {}
        status=str(api_result.get("status") or "waiting")
        phone=str(api_result.get("phone") or order.get("phone") or "")
        if status=="finished" or api_result.get("code"):
            code=str(api_result.get("code") or "")
            password=str(api_result.get("password") or "")
            update_number_order(order_id,status="finished",phone=phone,sms_code=code,sms_password=password)
            password_line=f"\n🔐 Пароль: <code>{escape(password)}</code>" if password else ""
            await query.message.edit_text(tr(user.id,"number_finished",phone=phone,code=code,password_line=password_line,order_id=order_id),reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📩 Проверить ещё раз",callback_data=f"number_code_{order_id}")],
                [InlineKeyboardButton("📋 Мои номера",callback_data="numbers_orders")],
            ]),parse_mode="HTML")
            return
        update_number_order(order_id,status="waiting",phone=phone)
        await query.message.edit_text(tr(user.id,"number_waiting",phone=phone),reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📩 Проверить SMS",callback_data=f"number_code_{order_id}")],
            [InlineKeyboardButton("📋 Мои номера",callback_data="numbers_orders")],
        ]),parse_mode="HTML")


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


    # =====================================================
    # CONVERSATION HANDLER
    # ВАЖНО: СТАВИМ ПЕРВЫМ
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

                pattern=r"^giftapi_.+$",

            ),

            CallbackQueryHandler(

                admin_callback,

                pattern=r"^admin_(add|sub|ban|unban|message)$",

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

                    filters.PHOTO,

                    refill_check,

                ),

                MessageHandler(

                    filters.ALL,

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

    application.add_handler(conversation_handler)


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
    # ПОПОЛНЕНИЕ
    # =====================================================

    application.add_handler(

        CallbackQueryHandler(

            payment_callback,

            pattern=r"^(approve_refill|reject_refill)_",

        )

    )


    # =====================================================
    # АДМИН
    # =====================================================

    application.add_handler(

        CallbackQueryHandler(

            admin_callback,

            pattern=r"^admin_",

        )

    )


    # =====================================================
    # ГЛАВНЫЕ КНОПКИ
    # =====================================================

    application.add_handler(
        CallbackQueryHandler(
            number_callback,
            pattern=r"^(numbers_orders|number_country_.+|number_code_.+)$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            main_buttons,
            pattern=r"^(main_shop|shop_.*|buy_.*|gift_.*|back_main|language_menu)$",
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


async def unknown_callback(update, context):
    query = update.callback_query

    try:
        await query.answer()
    except Exception:
        pass


if __name__ == "__main__":

    main()

