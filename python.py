import os
import re
import random
import uuid
import sqlite3
import logging
import threading
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
ELDER_API_URL = "https://asosiy.elder.uz/api"

DB_FILE = "bot_database.db"

CARD_NUMBER = os.environ.get(
    "CARD_NUMBER",
    "5614 6835 8985 1641"
)

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
            "💰 Сумма к переводу: <b>{amount:,} сум</b>\n\n"
            "Переведите деньги на карту:\n"
            "<code>{card}</code>\n\n"
            "⚠️ Важно: переведите именно указанную сумму.\n\n"
            "После оплаты SMS от банка будет обработано автоматически."
        ),

        "receipt_sent": "⏳ Чек отправлен администратору.",

        "send_receipt": "❌ Отправьте фото чека.",

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

        "api_error": (
            "❌ Buyurtmani bajarib bo'lmadi."
        ),

        "cancelled": "❌ Bekor qilindi.",

        "refill_enter": (
            "💳 To'ldirish summasini so'mda kiriting.\n\n"
            "Masalan: 50000"
        ),

        "refill_payment": (
            "💳 <b>Balansni to'ldirish</b>\n\n"
            "💰 To'lov summasi: <b>{amount:,} so'm</b>\n\n"
            "Kartaga pul o'tkazing:\n"
            "<code>{card}</code>\n\n"
            "⚠️ Aynan ko'rsatilgan summani o'tkazing.\n\n"
            "Bank SMS xabari kelgach balans avtomatik to'ldiriladi."
        ),

        "receipt_sent": "⏳ Chek administratorga yuborildi.",

        "send_receipt": "❌ Chek rasmini yuboring.",

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

        "gift_success": (
            "✅ <b>Sovg'a buyurtmasi qabul qilindi!</b>"
        ),

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
    conn = sqlite3.connect(DB_FILE)
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

    conn.commit()
    conn.close()


def get_user(user_id, username="", name=""):
    conn = sqlite3.connect(DB_FILE)
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

        new_username = username or old_username or ""
        new_name = name or old_name or ""

        cursor.execute(
            """
            UPDATE users
            SET username = ?, name = ?
            WHERE user_id = ?
            """,
            (
                new_username,
                new_name,
                user_id,
            ),
        )

        conn.commit()

        result = {
            "username": new_username,
            "name": new_name,
            "balance": balance,
            "lang": lang or "ru",
            "is_banned": bool(is_banned),
        }

    conn.close()

    return result


def set_language(user_id, lang):
    conn = sqlite3.connect(DB_FILE)
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
    conn = sqlite3.connect(DB_FILE)
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
    conn = sqlite3.connect(DB_FILE)
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
    conn = sqlite3.connect(DB_FILE)
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

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):

        self.send_response(200)

        self.send_header(
            "Content-type",
            "text/html",
        )

        self.end_headers()

        self.wfile.write(
            b"Bot is running!"
        )

    def log_message(self, format, *args):
        return


def run_web():

    port = int(
        os.environ.get(
            "PORT",
            8080,
        )
    )

    server = HTTPServer(
        (
            "0.0.0.0",
            port,
        ),
        Handler,
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


    # BACK
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


    # LANGUAGE
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


    # SHOP
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


    # STARS
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


    # PREMIUM
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


    # GIFTS
    if query.data == "shop_gifts":

        keyboard = []

        for gift_id, gift in GIFTS.items():

            keyboard.append([

                InlineKeyboardButton(

                    f"{gift['emoji']} — "
                    f"{gift['price']:,} сум",

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


    # ACCOUNTS
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


    # ACCOUNT ORDER
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

                f"👤 Заказал: "
                f"@{escape(user.username or 'нет username')}\n"

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
# ELDER API
# =========================================================

async def send_order_to_elder(
    product_type,
    value,
    target,
):

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

        return False

    try:

        async with httpx.AsyncClient(
            timeout=30
        ) as client:

            response = await client.post(

                url,

                headers=headers,

                json=payload,

            )

        logger.info(

            "ELDER RESPONSE %s: %s",

            response.status_code,

            response.text,

        )

        if response.status_code != 200:
            return False

        data = response.json()

        return bool(
            data.get("success")
        )

    except Exception as e:

        logger.exception(
            "ELDER API ERROR: %s",
            e,
        )

        return False


# =========================================================
# ПОКУПКА STARS / PREMIUM
# =========================================================

async def buy_start(update, context):

    query = update.callback_query

    await query.answer()

    context.user_data.clear()

    data = query.data


    # Свои Stars
    if data == "buy_stars":

        context.user_data["product_type"] = "stars"

        await query.message.edit_text(

            "⭐ Введите количество Stars "
            "(от 50 до 10000):"

        )

        return BUY_AMOUNT


    # Готовое количество Stars
    if data.startswith("buy_stars_"):

        try:
            amount = int(
                data.split("_")[2]
            )
        except (ValueError, IndexError):

            await query.message.edit_text(
                "❌ Ошибка количества Stars."
            )

            return ConversationHandler.END

        context.user_data["product_type"] = "stars"

        context.user_data["amount"] = amount

        await query.message.edit_text(

            f"⭐ Вы выбрали {amount} Stars.\n\n"
            "Введите @username Telegram:"

        )

        return BUY_USERNAME


    # Premium
    if data.startswith("buy_premium_"):

        try:
            months = int(
                data.split("_")[2]
            )
        except (ValueError, IndexError):

            await query.message.edit_text(
                "❌ Ошибка срока Premium."
            )

            return ConversationHandler.END

        if months not in PREMIUM_PRICES:

            await query.message.edit_text(
                "❌ Такой срок Premium недоступен."
            )

            return ConversationHandler.END

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

    elif product_type == "premium":

        price = PREMIUM_PRICES.get(amount)

        if price is None:

            await update.message.reply_text(
                "❌ Ошибка цены Premium."
            )

            context.user_data.clear()

            return ConversationHandler.END

        product = (
            f"Telegram Premium на "
            f"{amount} мес."
        )

    else:

        await update.message.reply_text(
            "❌ Ошибка заказа."
        )

        context.user_data.clear()

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

    product_type = context.user_data.get(
        "product_type"
    )

    amount = context.user_data.get(
        "amount"
    )

    username = context.user_data.get(
        "username"
    )

    price = context.user_data.get(
        "price"
    )

    product = context.user_data.get(
        "product"
    )

    if not all([
        product_type,
        amount,
        username,
        price,
        product,
    ]):

        context.user_data.clear()

        await query.message.edit_text(
            "❌ Данные заказа потеряны. "
            "Начните покупку заново."
        )

        return ConversationHandler.END

    # Повторная проверка баланса
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

        tr(
            user.id,
            "processing",
        )

    )

    success = await send_order_to_elder(

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

    # Списываем деньги только после успешного API
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

    if base_amount > 100000000:

        await update.message.reply_text(
            "❌ Слишком большая сумма."
        )

        return REFILL_AMOUNT

    conn = sqlite3.connect(DB_FILE)

    cursor = conn.cursor()

    # Создаём уникальную сумму
    while True:

        amount = base_amount + random.randint(1, 999)

        cursor.execute(
            """
            SELECT 1
            FROM pending_refills
            WHERE amount = ?
            """,
            (amount,),
        )

        if cursor.fetchone() is None:
            break

    cursor.execute(
        """
        INSERT INTO pending_refills
        (amount, user_id)
        VALUES (?, ?)
        """,
        (
            amount,
            update.effective_user.id,
        ),
    )

    conn.commit()
    conn.close()

    context.user_data["refill_amount"] = amount

    context.user_data["refill_user_id"] = (
        update.effective_user.id
    )

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

    await update.message.reply_text(

        "⏳ Ожидайте поступления оплаты.\n\n"
        "После получения банковского SMS "
        "баланс пополнится автоматически."

    )

    return REFILL_CHECK


# =========================================================
# АВТОМАТИЧЕСКОЕ ПОПОЛНЕНИЕ ПО SMS
# =========================================================

async def process_bank_sms(update, context):

    if not update.message:
        return

    if not update.message.text:
        return

    # Обрабатываем только пересланные сообщения
    if not update.message.forward_origin:
        return

    sender = getattr(
        update.message.forward_origin,
        "sender_user",
        None,
    )

    if not sender:
        return

    # SMS должно быть переслано администратором
    if sender.id != ADMIN_ID:
        return

    text = update.message.text

    logger.info(
        "Получено пересланное сообщение от ADMIN: %s",
        text,
    )

    # Проверяем формат SMS
    if "From: 5800" not in text:
        return

    if "Miqdor:" not in text:
        return

    # Ищем сумму
    match = re.search(
        r"Miqdor:\s*([\d\s]+(?:\.\d+)?)\s*UZS",
        text,
        re.IGNORECASE,
    )

    if not match:
        logger.warning(
            "Не удалось найти сумму в банковском SMS."
        )
        return

    try:

        amount = int(
            float(
                match.group(1).replace(" ", "")
            )
        )

    except ValueError:

        logger.warning(
            "Ошибка преобразования суммы."
        )

        return

    conn = sqlite3.connect(DB_FILE)

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT user_id
        FROM pending_refills
        WHERE amount = ?
        """,
        (amount,),
    )

    row = cursor.fetchone()

    if row is None:

        conn.close()

        logger.info(
            "Заявка на сумму %s не найдена.",
            amount,
        )

        return

    user_id = row[0]

    # Проверяем, что пользователь существует
    cursor.execute(
        """
        SELECT user_id
        FROM users
        WHERE user_id = ?
        """,
        (user_id,),
    )

    user_exists = cursor.fetchone()

    if user_exists is None:

        conn.close()

        logger.warning(
            "Пользователь %s не найден.",
            user_id,
        )

        return

    # Зачисляем деньги
    cursor.execute(
        """
        UPDATE users
        SET balance = balance + ?
        WHERE user_id = ?
        """,
        (
            amount,
            user_id,
        ),
    )

    # Удаляем обработанную заявку
    cursor.execute(
        """
        DELETE FROM pending_refills
        WHERE amount = ?
        """,
        (amount,),
    )

    conn.commit()
    conn.close()

    logger.info(
        "Автопополнение выполнено: user=%s amount=%s",
        user_id,
        amount,
    )

    # Сообщение пользователю
    try:

        await context.bot.send_message(

            user_id,

            (
                "✅ <b>Баланс пополнен автоматически!</b>\n\n"
                f"💰 Зачислено: <b>{amount:,} сум</b>"
            ),

            parse_mode="HTML",

        )

    except Exception as e:

        logger.exception(
            "Не удалось уведомить пользователя: %s",
            e,
        )

    # Сообщение админу
    try:

        await context.bot.send_message(

            ADMIN_ID,

            (
                "✅ <b>Автопополнение выполнено</b>\n\n"
                f"👤 ID: <code>{user_id}</code>\n"
                f"💰 Сумма: <b>{amount:,} сум</b>"
            ),

            parse_mode="HTML",

        )

    except Exception as e:

        logger.exception(
            "Не удалось уведомить администратора: %s",
            e,
        )


# =========================================================
# ПОДАРКИ
# =========================================================

async def gift_start(update, context):

    query = update.callback_query

    await query.answer()

    try:

        gift_id = int(
            query.data.split("_")[1]
        )

    except (ValueError, IndexError):

        await query.message.edit_text(
            "❌ Ошибка подарка."
        )

        return ConversationHandler.END

    if gift_id not in GIFTS:

        await query.message.edit_text(
            "❌ Такой подарок не найден."
        )

        return ConversationHandler.END

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

    text = update.message.text.strip()

    if len(text) > 500:

        await update.message.reply_text(
            "❌ Текст слишком длинный. "
            "Максимум 500 символов."
        )

        return GIFT_TEXT

    context.user_data["gift_text"] = text

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

    try:

        await bot.send_message(

            chat_id=chat_id,

            text=emoji,

            entities=[

                MessageEntity(

                    type=MessageEntity.CUSTOM_EMOJI,

                    offset=0,

                    length=len(emoji),

                    custom_emoji_id=emoji_id,

                )

            ],

        )

    except Exception as e:

        logger.exception(
            "Ошибка отправки custom emoji: %s",
            e,
        )

        # Если custom emoji не отправился,
        # отправляем обычный emoji
        await bot.send_message(
            chat_id=chat_id,
            text=emoji,
        )


async def gift_username(update, context):

    username = update.message.text.strip()

    username = username.replace("@", "")

    if not re.fullmatch(

        r"[A-Za-z0-9_]{5,32}",

        username,

    ):

        await update.message.reply_text(

            "❌ Введите корректный юзернейм."

        )

        return GIFT_USERNAME

    user = update.effective_user

    gift_id = context.user_data.get(
        "gift_id"
    )

    if gift_id not in GIFTS:

        await update.message.reply_text(
            "❌ Ошибка подарка."
        )

        context.user_data.clear()

        return ConversationHandler.END

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

    # Списываем баланс
    change_balance(

        user.id,

        -gift["price"],

    )

    sender = (

        "Анонимно"

        if anonymous

        else

        f"@{user.username or 'нет username'}"

    )

    # Отправляем emoji админу
    await send_custom_emoji(

        context.bot,

        ADMIN_ID,

        gift["emoji"],

        gift["emoji_id"],

    )

    # Информация админу
    await context.bot.send_message(

        ADMIN_ID,

        (

            "🎁 <b>НОВЫЙ ЗАКАЗ ПОДАРКА</b>\n\n"

            f"🎁 Подарок: "
            f"<b>{escape(gift['name'])}</b>\n"

            f"💰 Цена: {gift['price']:,} сум\n\n"

            f"👤 Заказал: {escape(sender)}\n"

            f"🆔 ID заказчика: "
            f"<code>{user.id}</code>\n\n"

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

    elif update.message:

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

        total = sum(
            row[3]
            for row in users
        )

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
            1
            for row in users
            if not row[5]
        )

        banned = sum(
            1
            for row in users
            if row[5]
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

    try:

        await context.bot.send_message(

            user_id,

            (

                "💰 <b>Баланс изменён администратором</b>\n\n"

                f"➕ Добавлено: {amount:,} сум"

            ),

            parse_mode="HTML",

        )

    except Exception as e:

        logger.exception(e)

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

        return ADMIN_SUB_AMOUNT

    change_balance(user_id, -amount)

    try:

        await context.bot.send_message(

            user_id,

            (

                "💰 <b>Баланс изменён администратором</b>\n\n"

                f"➖ Снято: {amount:,} сум"

            ),

            parse_mode="HTML",

        )

    except Exception as e:

        logger.exception(e)

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

    except Exception as e:

        logger.exception(e)

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

    except Exception as e:

        logger.exception(e)

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
# ADMIN PAYMENT CALLBACK
# =========================================================

async def payment_callback(update, context):

    query = update.callback_query

    await query.answer()

    if not is_admin(query.from_user.id):
        return

    data = query.data

    if data.startswith("approve_refill_"):

        try:

            user_id = int(
                data.split("_")[-1]
            )

        except (ValueError, IndexError):

            await query.message.edit_text(
                "❌ Неверный ID пользователя."
            )

            return

        await query.message.edit_text(

            f"✅ Пополнение пользователя "
            f"<code>{user_id}</code> подтверждено.",

            parse_mode="HTML",

        )

        return


    if data.startswith("reject_refill_"):

        try:

            user_id = int(
                data.split("_")[-1]
            )

        except (ValueError, IndexError):

            await query.message.edit_text(
                "❌ Неверный ID пользователя."
            )

            return

        await query.message.edit_text(

            f"❌ Пополнение пользователя "
            f"<code>{user_id}</code> отклонено.",

            parse_mode="HTML",

        )

        return


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

    # База данных
    init_db()

    # Render Web Server
    threading.Thread(
        target=run_web,
        daemon=True,
    ).start()

    # Telegram Application
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

            # Пополнение
            CallbackQueryHandler(

                refill_start,

                pattern=r"^main_refill$",

            ),

            # Stars / Premium
            CallbackQueryHandler(

                buy_start,

                pattern=r"^buy_(stars|premium)(?:_\d+)?$",

            ),

            # Подарки
            CallbackQueryHandler(

                gift_start,

                pattern=r"^gift_\d+$",

            ),

            # Админ
            CallbackQueryHandler(

                admin_callback,

                pattern=r"^admin_(add|sub|ban|unban|message)$",

            ),

        ],

        states={

            # ---------------------------------------------
            # REFILL
            # ---------------------------------------------

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


            # ---------------------------------------------
            # BUY
            # ---------------------------------------------

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


            # ---------------------------------------------
            # GIFTS
            # ---------------------------------------------

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


            # ---------------------------------------------
            # ADMIN ADD
            # ---------------------------------------------

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


            # ---------------------------------------------
            # ADMIN SUB
            # ---------------------------------------------

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


            # ---------------------------------------------
            # ADMIN BAN
            # ---------------------------------------------

            ADMIN_BAN_ID: [

                MessageHandler(

                    filters.TEXT & ~filters.COMMAND,

                    admin_ban_id,

                )

            ],


            # ---------------------------------------------
            # ADMIN UNBAN
            # ---------------------------------------------

            ADMIN_UNBAN_ID: [

                MessageHandler(

                    filters.TEXT & ~filters.COMMAND,

                    admin_unban_id,

                )

            ],


            # ---------------------------------------------
            # ADMIN MESSAGE
            # ---------------------------------------------

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


    # =====================================================
    # SMS АВТОПОПОЛНЕНИЕ
    # =====================================================

    application.add_handler(

        MessageHandler(

            filters.TEXT & filters.FORWARDED,

            process_bank_sms,

        )

    )


    # =====================================================
    # CONVERSATION
    # =====================================================

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
    # LANGUAGE
    # =====================================================

    application.add_handler(

        CallbackQueryHandler(

            language_callback,

            pattern=r"^lang_(ru|uz)$",

        )

    )


    # =====================================================
    # PROFILE
    # =====================================================

    application.add_handler(

        CallbackQueryHandler(

            profile_callback,

            pattern=r"^(main_profile|profile)$",

        )

    )


    # =====================================================
    # PAYMENT CALLBACK
    # =====================================================

    application.add_handler(

        CallbackQueryHandler(

            payment_callback,

            pattern=r"^(approve_refill|reject_refill)_",

        )

    )


    # =====================================================
    # ADMIN CALLBACK
    # =====================================================

    application.add_handler(

        CallbackQueryHandler(

            admin_callback,

            pattern=r"^admin_",

        )

    )


    # =====================================================
    # MAIN BUTTONS
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
            unknown_callback
        )

    )


    logger.info("BOT STARTED")

    application.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# ЗАПУСК
# =========================================================

if __name__ == "__main__":
    main()