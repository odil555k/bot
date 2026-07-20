import os
import re
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
    "УКАЖИ_НОМЕР_КАРТЫ"
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


# =========================================================
# ПОДАРКИ
# =========================================================

GIFTS = {
    1: {
        "emoji": "🎁",
        "emoji_id": "5280615440928758599",
        "price": 4000,
        "stars": 15,
        "name": "Подарок",
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
        "emoji": "🧸",
        "emoji_id": "5397971251878732060",
        "price": 10500,
        "stars": 50,
        "name": "Мишка-футболист",
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

        # ИСПРАВЛЕНО
        "profile_button": "👤 Профиль",

        "profile": (
            "👤 <b>Мой профиль</b>\n\n"
            "🆔 ID: <code>{user_id}</code>\n"
            "💰 Баланс: <b>{balance:,} сум</b>"
        ),

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
            "💰 Сумма: {amount:,} сум\n\n"
            "Переведите деньги на карту:\n"
            "<code>{card}</code>\n\n"
            "После оплаты отправьте фото чека."
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

        # ИСПРАВЛЕНО
        "profile_button": "👤 Profil",

        "profile": (
            "👤 <b>Mening profilim</b>\n\n"
            "🆔 ID: <code>{user_id}</code>\n"
            "💰 Balans: <b>{balance:,} so'm</b>"
        ),

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
            "💰 Summa: {amount:,} so'm\n\n"
            "Kartaga pul o'tkazing:\n"
            "<code>{card}</code>\n\n"
            "To'lovdan keyin chek rasmini yuboring."
        ),

        "receipt_sent": "⏳ Chek administratorga yuborildi.",

        "send_receipt": "❌ Chek rasmini yuboring.",

        "gift_send_type": (
            "🎁 <b>Sovg'a qanday yuboriladi?</b>"
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

    conn.commit()
    conn.close()


def get_user(
    user_id,
    username="",
    name=""
):

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

    kwargs.setdefault("user_id", user_id)

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
# WEB SERVER
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
# ГЛАВНАЯ КЛАВИАТУРА
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

            # ИСПРАВЛЕНО
            InlineKeyboardButton(
                tr(user_id, "profile_button"),
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

    if query.data == "main_profile":

        keyboard = [[

            InlineKeyboardButton(
                tr(user.id, "back"),
                callback_data="back_main",
            )

        ]]

        await query.message.edit_text(

            tr(
                user.id,
                "profile",
                user_id=user.id,
                balance=data["balance"],
            ),

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
                f"👤 Заказал: "
                f"@{escape(user.username or 'нет username')}\n"
                f"🆔 ID: <code>{user.id}</code>"
            ),

            parse_mode="HTML",
        )

        await query.message.edit_text(
            "✅ Заявка принята!"
        )


# =========================================================
# ЯЗЫК
# =========================================================

async def language_callback(update, context):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    if query.data == "lang_ru":

        set_language(user_id, "ru")

    elif query.data == "lang_uz":

        set_language(user_id, "uz")

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

    else:

        url = f"{ELDER_API_URL}/premium/buy"

        payload = {

            "username": target,

            "months": value,

            "client_order_id": order_id,

        }

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

        amount = int(
            data.split("_")[2]
        )

        context.user_data["product_type"] = "stars"

        context.user_data["amount"] = amount

        await query.message.edit_text(

            tr(
                query.from_user.id,
                "enter_username",
            )
        )

        return BUY_USERNAME

    if data.startswith("buy_premium_"):

        months = int(
            data.split("_")[2]
        )

        context.user_data["product_type"] = "premium"

        context.user_data["amount"] = months

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
            f"🆔 ID заказчика: <code>{user.id}</code>\n"
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

    amount = int(text)

    if amount <= 0:

        await update.message.reply_text(
            "❌ Введите корректную сумму."
        )

        return REFILL_AMOUNT

    context.user_data["refill_amount"] = amount

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
                callback_data=f"approve_refill_{user.id}_{amount}",
            ),

            InlineKeyboardButton(
                "❌ Отклонить",
                callback_data=f"reject_refill_{user.id}",
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

    await query.answer()

    if query.from_user.id != ADMIN_ID:

        return

    parts = query.data.split("_")

    action = parts[0]

    if action == "approve":

        user_id = int(parts[2])

        amount = int(parts[3])

        change_balance(
            user_id,
            amount,
        )

        await context.bot.send_message(

            user_id,

            (
                "✅ <b>Баланс пополнен!</b>\n\n"
                f"💰 Сумма: {amount:,} сум"
            ),

            parse_mode="HTML",
        )

        await query.edit_message_caption(

            caption=query.message.caption
            + "\n\n✅ ОДОБРЕНО",

            parse_mode="HTML",
        )

    else:

        user_id = int(parts[2])

        await context.bot.send_message(

            user_id,

            "❌ Пополнение отклонено.",
        )

        await query.edit_message_caption(

            caption=query.message.caption
            + "\n\n❌ ОТКЛОНЕНО",

            parse_mode="HTML",
        )


# =========================================================
# ПОДАРКИ
# =========================================================

async def gift_start(update, context):

    query = update.callback_query

    await query.answer()

    gift_id = int(
        query.data.split("_")[1]
    )

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

        else

        f"@{user.username or 'нет username'}"

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


async def admin(update, context):

    if not is_admin(
        update.effective_user.id
    ):

        await update.message.reply_text(
            "❌ Нет доступа."
        )

        return

    keyboard = [

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

    ]

    await update.message.reply_text(

        "🛠 <b>Админ-панель</b>",

        reply_markup=InlineKeyboardMarkup(keyboard),

        parse_mode="HTML",
    )


async def admin_callback(update, context):

    query = update.callback_query

    await query.answer()

    if not is_admin(
        query.from_user.id
    ):

        return

    if query.data == "admin_users":

        users = get_users()

        if not users:

            await query.message.edit_text(
                "👥 Пользователей пока нет."
            )

            return

        text = "👥 <b>ПОЛЬЗОВАТЕЛИ</b>\n\n"

        for index, row in enumerate(
            users[:50],
            1,
        ):

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

        return

    if query.data == "admin_balances":

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

        return

    if query.data == "admin_stats":

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

        return

    if query.data == "admin_back":

        keyboard = [

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

        ]

        await query.message.edit_text(

            "🛠 <b>Админ-панель</b>",

            reply_markup=InlineKeyboardMarkup(keyboard),

            parse_mode="HTML",
        )


# =========================================================
# НЕИЗВЕСТНЫЕ CALLBACK
# =========================================================

async def unknown_callback(update, context):

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

        CommandHandler(
            "start",
            start,
        )

    )

    application.add_handler(

        CommandHandler(
            "admin",
            admin,
        )

    )

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

            pattern=r"^admin_",

        )

    )

    application.add_handler(

        ConversationHandler(

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

                        filters.TEXT
                        & ~filters.COMMAND,

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

                        filters.TEXT
                        & ~filters.COMMAND,

                        buy_amount,

                    )

                ],

                BUY_USERNAME: [

                    MessageHandler(

                        filters.TEXT
                        & ~filters.COMMAND,

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

                        pattern=r"^(gift_anonymous_yes|gift_anonymous_no|cancel_gift)$",

                    )

                ],

                GIFT_TEXT: [

                    CallbackQueryHandler(

                        gift_text_choice,

                        pattern=r"^(gift_text_yes|gift_text_no|cancel_gift)$",

                    ),

                    MessageHandler(

                        filters.TEXT
                        & ~filters.COMMAND,

                        gift_text_input,

                    ),

                ],

                GIFT_USERNAME: [

                    MessageHandler(

                        filters.TEXT
                        & ~filters.COMMAND,

                        gift_username,

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

    )

    application.add_handler(

        CallbackQueryHandler(

            main_buttons,

            pattern=r"^(main_.*|shop_.*|back_main|account_.*|language_menu)$",

        )

    )

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