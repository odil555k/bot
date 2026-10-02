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
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "StarrPayy_support") # Укажите ваш юзернейм для связи (без @)

# Partner API для автоматической покупки Telegram Stars / Premium.
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
    "5614 6835 1772 2716"
)

PRICE_PER_STAR = 220

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

ADMIN_ADD_ID = 6
ADMIN_ADD_AMOUNT = 7

ADMIN_SUB_ID = 8
ADMIN_SUB_AMOUNT = 9

ADMIN_BAN_ID = 10
ADMIN_UNBAN_ID = 11

ADMIN_MESSAGE_ID = 12
ADMIN_MESSAGE_TEXT = 13

# Новые состояния для рассылки и промокодов
ADMIN_BROADCAST_TEXT = 14
ADMIN_PROMO_CODE = 15
ADMIN_PROMO_AMOUNT = 16
ADMIN_PROMO_USERS = 17
ACTIVATE_PROMO_STATE = 18


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

        "shop": "🛍 Выберите услугу:",

        "stars": (
            "💎 Telegram Stars\n\n"
            "💰 Цена: {price:,} сум за 1 Stars"
        ),

        "premium": (
            "🌟 Telegram Premium\n\n"
            "Выберите срок подписки:"
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

        "refill_choose": (
            "💳 Выберите способ пополнения баланса:"
        ),

        "refill_enter": (
            "💳 Введите сумму пополнения в сумах.\n\n"
            "Например: 50000"
        ),

        "refill_payment": (
            "💳 Пополнение баланса через карту\n\n"
            "💰 На баланс: {amount:,} сум\n"
            "💵 Перевести нужно: <code>{payment_amount:,}<code> сум\n\n"
            "Переведите точно эту сумму на карту:\n"
            "<code>{card}<code>\n\n"
            "⏳ После поступления перевода баланс будет пополнен автоматически."
        ),

        "refill_admin": (
            "👤 Пополнение через администратора\n\n"
            "Для пополнения баланса свяжитесь с администратором:\n"
            "👉 @{admin_username}"
        ),

        "receipt_sent": "⏳ Заявка отправлена администратору.",

        "send_receipt": "❌ Отправьте подтверждение оплаты.",

        "confirm_order": (
            "🛒 Проверьте заказ\n\n"
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

        "shop": "🛍 **Xizmatni tanlang:**",

        "stars": (
            "💎 Telegram Stars\n\n"
            "💰 Narx: 1 Stars — {price:,} so'm"
        ),

        "premium": (
            "🌟 Telegram Premium\n\n"
            "Muddatni tanlang:"
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

        "refill_choose": (
            "💳 Balansni to'ldirish usulini tanlang:"
        ),

        "refill_enter": (
            "💳 To'ldirish summasini so'mda kiriting.\n\n"
            "Masalan: 50000"
        ),

        "refill_payment": (
            "💳 Karta orqali balansni to'ldirish\n\n"
            "💰 Balansga: {amount:,} so'm\n"
            "💵 Aynan o'tkazish kerak: <code>{payment_amount:,}<code> so'm\n\n"
            "Kartaga aynan shu summani o'tkazing:\n"
            "<code>{card}<code>\n\n"
            "⏳ To'lov kelgach, balans avtomatik to'ldiriladi."
        ),

        "refill_admin": (
            "👤 Administrator orqali to'ldirish\n\n"
            "Balansni to'ldirish uchun administratorga murojaat qiling:\n"
            "👉 @{admin_username}"
        ),

        "receipt_sent": "⏳ So'rov administratorga yuborildi.",

        "send_receipt": "❌ To'lov tasdig'ini yuboring.",

        "confirm_order": (
            "🛒 Buyurtmani tekshiring\n\n"
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cardxabar_transactions (
            fingerprint TEXT PRIMARY KEY,
            payment_amount INTEGER NOT NULL,
            raw_text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS promos (
            code TEXT PRIMARY KEY,
            amount INTEGER NOT NULL,
            max_uses INTEGER NOT NULL,
            uses_count INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS promo_activations (
            user_id INTEGER,
            code TEXT,
            PRIMARY KEY (user_id, code)
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


def create_cardxabar_payment(user_id, requested_amount):
    if requested_amount < 1000 or requested_amount > 9_999_900:
        raise ValueError("Сумма должна быть от 1000 до 9 999 900 сум.")

    conn = sqlite3.connect(DB_FILE, timeout=20)
    cursor = conn.cursor()

    try:
        for _ in range(200):
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
                conn.rollback()
                continue

        raise RuntimeError("Не удалось создать уникальную сумму платежа.")
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
    try:
        user = get_user(user_id)
        lang = user.get("lang", "ru")
        if lang == "uz":
            text = (
                "✅ **Balans muvaffaqiyatli to'ldirildi!**\n\n"
                f"💰 Qo'shildi: **{credited_amount:,} so'm**\n"
                f"💳 Joriy balans: **{user['balance']:,} so'm**"
            )
        else:
            text = (
                "✅ **Баланс успешно пополнен!**\n\n"
                f"💰 Зачислено: **{credited_amount:,} сум**\n"
                f"💳 Текущий баланс: **{user['balance']:,} сум**"
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
                "🎁 Промокод",
                callback_data="main_promo",
            )
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

        "👤 **Мой профиль**\n\n"

        f"👤 Username: @{escape(username)}\n"

        f"🆔 ID: `{user.id}`\n"

        f"💰 Баланс: **{data['balance']:,} сум**"

    )

    await query.message.edit_text(

        text,

        reply_markup=keyboard,

        parse_mode="HTML",

    )


# =========================================================
# АКТИВАЦИЯ ПРОМОКОДА
# =========================================================

async def promo_menu_callback(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_main")]
    ])

    await query.message.edit_text(
        "🎟 Введите ваш промокод для активации:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    return ACTIVATE_PROMO_STATE


async def activate_promo_input(update, context):
    user = update.effective_user
    code = update.message.text.strip().upper()

    conn = sqlite3.connect(DB_FILE, timeout=20)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    promo = cursor.execute("SELECT * FROM promos WHERE code = ?", (code,)).fetchone()

    if not promo:
        conn.close()
        await update.message.reply_text("❌ Такого промокода не существует.")
        context.user_data.clear()
        return ConversationHandler.END

    activated = cursor.execute(
        "SELECT 1 FROM promo_activations WHERE user_id = ? AND code = ?",
        (user.id, code)
    ).fetchone()

    if activated:
        conn.close()
        await update.message.reply_text("❌ Вы уже активировали этот промокод.")
        context.user_data.clear()
        return ConversationHandler.END

    if promo["uses_count"] >= promo["max_uses"]:
        conn.close()
        await update.message.reply_text("❌ Лимит активаций этого промокода исчерпан.")
        context.user_data.clear()
        return ConversationHandler.END

    amount = promo["amount"]
    change_balance(user.id, amount)

    cursor.execute(
        "UPDATE promos SET uses_count = uses_count + 1 WHERE code = ?",
        (code,)
    )
    cursor.execute(
        "INSERT INTO promo_activations (user_id, code) VALUES (?, ?)",
        (user.id, code)
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ **Промокод успешно активирован!**\n\n"
        f"💰 Вам начислено: **{amount:,} сум**",
        parse_mode="HTML"
    )
    context.user_data.clear()
    return ConversationHandler.END


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

            "🌐 **Выберите язык / Tilni tanlang**",

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
            return False, None, "Недопустимый срок Premium."
        payload={"username":target,"duration":months}
    else:
        logger.error("UNKNOWN PRODUCT TYPE: %s",product_type)
        return False, None, "Неизвестный тип товара."
    result=await partner_api_request(endpoint,method="POST",payload=payload,idempotency_key=idem_key)
    if result.get("ok") is True:
        result_data=result.get("result") or {}
        order_id=result_data.get("order_id") if isinstance(result_data,dict) else None
        logger.info("PARTNER ORDER SUCCESS | type=%s | target=%s | value=%s | order_id=%s",product_type,target,value,order_id)
        return True, order_id, None

    api_error = (
        result.get("message")
        or result.get("error")
        or result.get("code")
        or "Partner API не выполнил заказ."
    )

    logger.error(
        "PARTNER ORDER FAILED | type=%s | target=%s | value=%s | HTTP=%s | "
        "message=%s | response=%s",
        product_type,
        target,
        value,
        result.get("_http_status"),
        api_error,
        str(result)[:2000],
    )
    return False, None, str(api_error)


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
            tr(
                query.from_user.id,
                "enter_stars",
            )
        )

        return BUY_AMOUNT

    if data.startswith("buy_stars_"):

        amount = int(data.split("_")[2])

        context.user_data["product_type"] = "stars"
        context.user_data["amount"] = amount

        await query.message.edit_text(
            f"⭐ Вы выбрали {amount} Stars.\n\nВведите @username Telegram:"
        )

        return BUY_USERNAME

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

    try:
        success, order_id, api_error = await send_order_to_partner(
            product_type,
            amount,
            username,
            user.id,
        )
    except Exception as exc:
        logger.exception(
            "STARS/PREMIUM ORDER EXCEPTION | user_id=%s | type=%s | target=%s | value=%s",
            user.id,
            product_type,
            username,
            amount,
        )
        await query.message.edit_text(
            f"❌ Ошибка при оформлении заказа.\n\n`{escape(str(exc))}`",
            parse_mode="HTML",
        )
        context.user_data.clear()
        return ConversationHandler.END

    if not success:
        error_text = api_error or "Partner API не выполнил заказ."
        await query.message.edit_text(
            f"❌ Не удалось выполнить заказ.\n\n{escape(str(error_text))}",
            parse_mode="HTML",
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

            "🛒 **НОВЫЙ ЗАКАЗ**\n\n"

            f"📦 Товар: {escape(product)}\n"

            f"👤 Получатель: @{escape(username)}\n"

            f"💰 Цена: {price:,} сум\n"
            f"🧾 Order ID: `{escape(str(order_id or 'не указан'))}`\n"

            f"🆔 ID заказчика: "
            f"`{user.id}`\n"

            f"👤 Заказал: "
            f"@{escape(user.username or 'нет username')}"

        ),

        parse_mode="HTML",

    )

    await query.message.edit_text(

        (

            "✅ **Заказ успешно выполнен!**\n\n"

            f"📦 {escape(product)}\n"
            f"👤 Получатель: @{escape(username)}\n"
            f"🧾 Order ID: `{escape(str(order_id or 'не указан'))}`"

        ),

        parse_mode="HTML",

    )

    context.user_data.clear()

    return ConversationHandler.END


# =========================================================
# ПОПОЛНЕНИЕ (ВЫБОР СПОСОБА)
# =========================================================

async def refill_start(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Автоматически через карту", callback_data="refill_card")],
        [InlineKeyboardButton("👤 Через администратора", callback_data="refill_admin")],
        [InlineKeyboardButton(tr(query.from_user.id, "back"), callback_data="back_main")]
    ])

    await query.message.edit_text(
        tr(query.from_user.id, "refill_choose"),
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def refill_card_start(update, context):
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


async def refill_admin_contact(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(tr(query.from_user.id, "back"), callback_data="main_refill")]
    ])

    await query.message.edit_text(
        tr(
            query.from_user.id,
            "refill_admin",
            admin_username=ADMIN_USERNAME
        ),
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def refill_amount(update, context):
    text = update.message.text.replace(" ", "").replace("_", "")

    if not text.isdigit():
        await update.message.reply_text(
            "❌ Введите корректную сумму цифрами. Например: 10000"
        )
        return REFILL_AMOUNT

    amount = int(text)

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
                "📢 Рассылка всем",
                callback_data="admin_broadcast",
            )
        ],

        [
            InlineKeyboardButton(
                "🎟 Создать промокод",
                callback_data="admin_create_promo",
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

        "🛠 **АДМИН-ПАНЕЛЬ**",

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

    if data == "admin_broadcast":
        await query.message.edit_text(
            "📢 Введите текст сообщения для рассылки всем пользователям:"
        )
        return ADMIN_BROADCAST_TEXT

    if data == "admin_create_promo":
        await query.message.edit_text(
            "🎟 Введите код нового промокода (например, SALE2026):"
        )
        return ADMIN_PROMO_CODE


    if data == "admin_users":

        users = get_users()

        if not users:

            await query.message.edit_text(
                "👥 Пользователей пока нет."
            )

            return ConversationHandler.END

        text = "👥 **ПОЛЬЗОВАТЕЛИ**\n\n"

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

                f"**{index}. "
                f"{escape(name or 'Без имени')}**\n"

                f"👤 {username_text}\n"

                f"🆔 `{user_id}`\n"

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

                "💰 **БАЛАНСЫ**\n\n"

                f"👥 Пользователей: {len(users)}\n"

                f"💵 Общий баланс: {total:,} сум"

            ),

            reply_markup=InlineKeyboardMarkup([

                [

                    InlineKeyboardButton(

                        "⬅ Назад",

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

                "📊 **СТАТИСТИКА**\n\n"

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

            "🛠 **АДМИН-ПАНЕЛЬ**",

            reply_markup=admin_keyboard(),

            parse_mode="HTML",

        )

        return ConversationHandler.END


# =========================================================
# АДМИН: РАССЫЛКА ВСЕМ
# =========================================================

async def admin_broadcast_text(update, context):
    text = update.message.text
    users = get_users()

    success_count = 0
    fail_count = 0

    status_msg = await update.message.reply_text("⏳ Начинаю рассылку...")

    for row in users:
        user_id = row[0]
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 **Рассылка:**\n\n{escape(text)}",
                parse_mode="HTML"
            )
            success_count += 1
        except Exception:
            fail_count += 1

    await status_msg.edit_text(
        f"✅ **Рассылка завершена!**\n\n"
        f"👥 Успешно отправлено: {success_count}\n"
        f"❌ Ошибок (заблокировали бота): {fail_count}",
        parse_mode="HTML"
    )

    context.user_data.clear()
    return ConversationHandler.END


# =========================================================
# АДМИН: СОЗДАНИЕ ПРОМОКОДА
# =========================================================

async def admin_promo_code(update, context):
    code = update.message.text.strip().upper()
    if not code:
        await update.message.reply_text("❌ Введите корректный код промокода.")
        return ADMIN_PROMO_CODE

    context.user_data["new_promo_code"] = code
    await update.message.reply_text("💰 Введите сумму промокода (в сумах):")
    return ADMIN_PROMO_AMOUNT


async def admin_promo_amount(update, context):
    text = update.message.text.replace(" ", "")
    if not text.isdigit():
        await update.message.reply_text("❌ Введите сумму цифрами.")
        return ADMIN_PROMO_AMOUNT

    amount = int(text)
    if amount <= 0:
        await update.message.reply_text("❌ Сумма должна быть больше 0.")
        return ADMIN_PROMO_AMOUNT

    context.user_data["new_promo_amount"] = amount
    await update.message.reply_text("👥 Введите количество пользователей, которые смогут использовать этот промокод:")
    return ADMIN_PROMO_USERS


async def admin_promo_users(update, context):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("❌ Введите число пользователей цифрами.")
        return ADMIN_PROMO_USERS

    max_uses = int(text)
    if max_uses <= 0:
        await update.message.reply_text("❌ Количество пользователей должно быть больше 0.")
        return ADMIN_PROMO_USERS

    code = context.user_data["new_promo_code"]
    amount = context.user_data["new_promo_amount"]

    conn = sqlite3.connect(DB_FILE, timeout=20)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO promos (code, amount, max_uses, uses_count) VALUES (?, ?, ?, 0)",
            (code, amount, max_uses)
        )
        conn.commit()
    except Exception as e:
        logger.exception("CREATE PROMO ERROR: %s", e)
        await update.message.reply_text("❌ Ошибка при создании промокода в базе данных.")
        conn.close()
        context.user_data.clear()
        return ConversationHandler.END
    finally:
        conn.close()

    await update.message.reply_text(
        f"✅ **Промокод успешно создан!**\n\n"
        f"🎟 Код: `{escape(code)}`\n"
        f"💰 Сумма: {amount:,} сум\n"
        f"👥 Лимит пользователей: {max_uses}",
        parse_mode="HTML"
    )

    context.user_data.clear()
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

        f"➕ Пользователь: `{user_id}`\n"
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

            "💰 **Баланс изменён администратором**\n\n"

            f"➕ Добавлено: {amount:,} сум"

        ),

        parse_mode="HTML",

    )

    await update.message.reply_text(

        f"✅ Добавлено **{amount:,} сум**\n"
        f"👤 ID: `{user_id}`",

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

        f"➖ Пользователь: `{user_id}`\n"
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

            "💰 **Баланс изменён администратором**\n\n"

            f"➖ Снято: {amount:,} сум"

        ),

        parse_mode="HTML",

    )

    await update.message.reply_text(

        f"✅ Убавлено **{amount:,} сум**\n"
        f"👤 ID: `{user_id}`",

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

        f"✅ Пользователь `{user_id}` заблокирован.",

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

        f"✅ Пользователь `{user_id}` разблокирован.",

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

        f"💬 ID пользователя: `{user_id}`\n\n"
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

                "📩 **Сообщение от администратора**\n\n"

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
    # =====================================================

    conversation_handler = ConversationHandler(

        entry_points=[

            CallbackQueryHandler(

                refill_card_start,

                pattern=r"^refill_card$",

            ),

            CallbackQueryHandler(
                buy_start,
                pattern=r"^buy_.*$",
            ),

            CallbackQueryHandler(

                admin_callback,

                pattern=r"^admin_(add|sub|ban|unban|message|broadcast|create_promo)$",

            ),

            CallbackQueryHandler(
                promo_menu_callback,
                pattern=r"^main_promo$",
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

            ADMIN_BROADCAST_TEXT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_broadcast_text,
                )
            ],

            ADMIN_PROMO_CODE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_promo_code,
                )
            ],

            ADMIN_PROMO_AMOUNT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_promo_amount,
                )
            ],

            ADMIN_PROMO_USERS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_promo_users,
                )
            ],

            ACTIVATE_PROMO_STATE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    activate_promo_input,
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
    # АДМИН
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
    # АДМИН
    # =====================================================

    application.add_handler(

        CallbackQueryHandler(

            admin_callback,

            pattern=r"^admin_",

        )

    )


    # =====================================================
    # ПОПОЛНЕНИЕ / ВЫБОР СПОСОБА
    # =====================================================

    application.add_handler(
        CallbackQueryHandler(
            refill_start,
            pattern=r"^main_refill$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            refill_admin_contact,
            pattern=r"^refill_admin$",
        )
    )


    # =====================================================
    # ГЛАВНЫЕ КНОПКИ
    # =====================================================

    application.add_handler(
        CallbackQueryHandler(
            main_buttons,
            pattern=r"^(main_shop|shop_.*|buy_.*|back_main|language_menu)$",
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