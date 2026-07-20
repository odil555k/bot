import os
import time
import sqlite3
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MessageEntity
)

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters
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
    "УКАЖИ_НОМЕР_КАРТЫ_В_RENDER"
)

PRICE_PER_STAR = 210


PREMIUM_PRICES = {
    3: 165000,
    6: 222000,
    12: 406000
}


# =========================================================
# ЛОГИ
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
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
        "emoji": "🧸",
        "emoji_id": "5280598054901145762",
        "price": 4000,
        "name": "Мишка"
    },

    2: {
        "emoji": "💝",
        "emoji_id": "5283228279988309088",
        "price": 4000,
        "name": "Подарок"
    },

    3: {
        "emoji": "🎁",
        "emoji_id": "5280615440928758599",
        "price": 6000,
        "name": "Подарок"
    },

    4: {
        "emoji": "🌹",
        "emoji_id": "5280947338821524402",
        "price": 6000,
        "name": "Роза"
    },

    5: {
        "emoji": "🎂",
        "emoji_id": "5280659198055572187",
        "price": 10500,
        "name": "Торт"
    },

    6: {
        "emoji": "💐",
        "emoji_id": "5280774333243873175",
        "price": 10500,
        "name": "Букет"
    },

    7: {
        "emoji": "🚀",
        "emoji_id": "5283080528818360566",
        "price": 10500,
        "name": "Ракета"
    },

    8: {
        "emoji": "🏆",
        "emoji_id": "5280769763398671636",
        "price": 21000,
        "name": "Кубок"
    },

    9: {
        "emoji": "💍",
        "emoji_id": "5280651583078556009",
        "price": 21000,
        "name": "Кольцо"
    },

    10: {
        "emoji": "💎",
        "emoji_id": "5280922999241859582",
        "price": 21000,
        "name": "Алмаз"
    },

    11: {
        "emoji": "🍾",
        "emoji_id": "5451905784734574339",
        "price": 10500,
        "name": "Шампанское"
    },

    12: {
        "emoji": "🧸",
        "emoji_id": "5397971251878732060",
        "price": 10500,
        "name": "Мишка-футболист"
    }
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
            "После выбора настройте отправку подарка."
        ),

        "accounts": "📱 <b>Выберите страну аккаунта:</b>",

        "enter_stars": (
            "✏️ Введите количество Stars.\n\n"
            "Минимум: 50"
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

        "success": (
            "✅ <b>Заказ успешно выполнен!</b>\n\n"
            "📦 {product}\n"
            "👤 Получатель: @{username}"
        ),

        "api_error": (
            "❌ Не удалось выполнить заказ.\n\n"
            "Попробуйте ещё раз позже."
        ),

        "gift_send_type": "🎁 <b>Как отправить подарок?</b>",

        "gift_text": (
            "✍️ Напишите текст, который нужно добавить к подарку."
        ),

        "gift_username": (
            "✏️ Введите юзернейм получателя подарка.\n\n"
            "Без символа @"
        ),

        "gift_success": (
            "✅ <b>Заявка на подарок принята!</b>\n\n"
            "Мы обработаем заказ."
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
            "{card}\n\n"
            "После оплаты отправьте фото чека."
        ),

        "receipt_sent": (
            "⏳ Чек отправлен администратору."
        ),

        "send_receipt": (
            "❌ Отправьте фото чека."
        )
    },


    "uz": {
        "welcome": (
            "👋 Salom, {name}!\n\n"
            "Do'konimizga xush kelibsiz.\n\n"
            "💰 Balans: {balance:,} so'm"
        ),

        "services": "🛍 Xizmatlar",

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
            "Sovg'ani yuborish sozlamalarini tanlang."
        ),

        "accounts": "📱 <b>Akkaunt davlatini tanlang:</b>",

        "enter_stars": (
            "✏️ Stars miqdorini kiriting.\n\n"
            "Minimum: 50"
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

        "success": (
            "✅ <b>Buyurtma muvaffaqiyatli bajarildi!</b>\n\n"
            "📦 {product}\n"
            "👤 Qabul qiluvchi: @{username}"
        ),

        "api_error": (
            "❌ Buyurtmani bajarib bo'lmadi.\n\n"
            "Keyinroq qayta urinib ko'ring."
        ),

        "gift_send_type": "🎁 <b>Sovg'ani qanday yuborish?</b>",

        "gift_text": (
            "✍️ Sovg'aga qo'shiladigan matnni yozing."
        ),

        "gift_username": (
            "✏️ Qabul qiluvchining username'ini kiriting.\n\n"
            "@ belgisiz"
        ),

        "gift_success": (
            "✅ <b>Sovg'a buyurtmasi qabul qilindi!</b>\n\n"
            "Buyurtma tez orada ko'rib chiqiladi."
        ),

        "cancelled": "❌ Bekor qilindi.",

        "refill_enter": (
            "💳 To'ldirish summasini so'mda kiriting.\n\n"
            "Masalan: 50000"
        ),

        "refill_payment": (
            "💳 <b>Balansni to'ldirish</b>\n\n"
            "💰 Summa: {amount:,} so'm\n\n"
            "Kartaga pul o'tkazing:\n"
            "{card}\n\n"
            "To'lovdan keyin chek rasmini yuboring."
        ),

        "receipt_sent": (
            "⏳ Chek administratorga yuborildi."
        ),

        "send_receipt": (
            "❌ Chek rasmini yuboring."
        )
    }
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
        (user_id,)
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
                name or ""
            )
        )

        conn.commit()

        result = {
            "username": username or "",
            "name": name or "",
            "balance": 0,
            "lang": "ru",
            "is_banned": False
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
                user_id
            )
        )

        conn.commit()

        result = {
            "username": username or old_username or "",
            "name": name or old_name or "",
            "balance": balance,
            "lang": lang or "ru",
            "is_banned": bool(is_banned)
        }

    conn.close()

    return result


def set_language(
    user_id,
    lang
):

    conn = sqlite3.connect(DB_FILE)

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE users
        SET lang = ?
        WHERE user_id = ?
        """,
        (
            lang,
            user_id
        )
    )

    conn.commit()

    conn.close()


def tr(
    user_id,
    key,
    **kwargs
):

    data = get_user(user_id)

    lang = data.get(
        "lang",
        "ru"
    )

    text = TEXTS.get(
        lang,
        TEXTS["ru"]
    ).get(
        key,
        key
    )

    kwargs.setdefault(
        "user_id",
        user_id
    )

    return text.format(**kwargs)


def change_balance(
    user_id,
    amount
):

    conn = sqlite3.connect(DB_FILE)

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE users
        SET balance = balance + ?
        WHERE user_id = ?
        """,
        (
            amount,
            user_id
        )
    )

    conn.commit()

    conn.close()


def set_ban(
    user_id,
    value
):

    conn = sqlite3.connect(DB_FILE)

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE users
        SET is_banned = ?
        WHERE user_id = ?
        """,
        (
            1 if value else 0,
            user_id
        )
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
        user.first_name
    )

    if data["is_banned"]:

        if update.message:

            await update.message.reply_text(
                "❌ Вы заблокированы."
            )

        elif update.callback_query:

            await update.callback_query.answer(
                "❌ Вы заблокированы.",
                show_alert=True
            )

        return True

    return False# =========================================================
# WEB SERVER
# =========================================================

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):

        self.send_response(200)

        self.send_header(
            "Content-type",
            "text/html"
        )

        self.end_headers()

        self.wfile.write(
            b"Bot is running!"
        )

    def log_message(
        self,
        format,
        *args
    ):

        return


def run_web():

    port = int(
        os.environ.get(
            "PORT",
            8080
        )
    )

    server = HTTPServer(
        (
            "0.0.0.0",
            port
        ),
        Handler
    )

    server.serve_forever()


# =========================================================
# START
# =========================================================

async def start(
    update,
    context
):

    context.user_data.clear()

    if await check_ban(update):

        return ConversationHandler.END

    user = update.effective_user

    data = get_user(
        user.id,
        user.username,
        user.first_name
    )

    keyboard = [

        [
            InlineKeyboardButton(
                tr(
                    user.id,
                    "services"
                ),
                callback_data="main_shop"
            )
        ],

        [
            InlineKeyboardButton(
                tr(
                    user.id,
                    "refill"
                ),
                callback_data="main_refill"
            ),

            InlineKeyboardButton(
                tr(
                    user.id,
                    "profile"
                ),
                callback_data="main_profile"
            )
        ],

        [
            InlineKeyboardButton(
                tr(
                    user.id,
                    "language"
                ),
                callback_data="language_menu"
            )
        ]

    ]

    await update.message.reply_text(

        tr(
            user.id,
            "welcome",
            name=user.first_name,
            balance=data["balance"]
        ),

        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),

        parse_mode="HTML"
    )


# =========================================================
# ГЛАВНОЕ МЕНЮ
# =========================================================

async def main_buttons(
    update,
    context
):

    if await check_ban(update):

        return

    query = update.callback_query

    await query.answer()

    user = query.from_user

    data = get_user(
        user.id,
        user.username,
        user.first_name
    )


    if query.data == "back_main":

        keyboard = [

            [
                InlineKeyboardButton(
                    tr(
                        user.id,
                        "services"
                    ),
                    callback_data="main_shop"
                )
            ],

            [
                InlineKeyboardButton(
                    tr(
                        user.id,
                        "refill"
                    ),
                    callback_data="main_refill"
                ),

                InlineKeyboardButton(
                    tr(
                        user.id,
                        "profile"
                    ),
                    callback_data="main_profile"
                )
            ],

            [
                InlineKeyboardButton(
                    tr(
                        user.id,
                        "language"
                    ),
                    callback_data="language_menu"
                )
            ]

        ]

        await query.message.edit_text(

            tr(
                user.id,
                "welcome",
                name=user.first_name,
                balance=data["balance"]
            ),

            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),

            parse_mode="HTML"
        )

        return


    if query.data == "language_menu":

        keyboard = [

            [
                InlineKeyboardButton(
                    "🇷🇺 Русский",
                    callback_data="lang_ru"
                )
            ],

            [
                InlineKeyboardButton(
                    "🇺🇿 O'zbekcha",
                    callback_data="lang_uz"
                )
            ],

            [
                InlineKeyboardButton(
                    tr(
                        user.id,
                        "back"
                    ),
                    callback_data="back_main"
                )
            ]

        ]

        await query.message.edit_text(

            "🌐 <b>Выберите язык / Tilni tanlang</b>",

            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),

            parse_mode="HTML"
        )

        return


    if query.data == "main_shop":

        keyboard = [

            [
                InlineKeyboardButton(
                    "💎 Stars",
                    callback_data="shop_stars"
                )
            ],

            [
                InlineKeyboardButton(
                    "🌟 Premium",
                    callback_data="shop_premium"
                )
            ],

            [
                InlineKeyboardButton(
                    "🎁 Подарки",
                    callback_data="shop_gifts"
                )
            ],

            [
                InlineKeyboardButton(
                    "📱 Аккаунты",
                    callback_data="shop_accounts"
                )
            ],

            [
                InlineKeyboardButton(
                    tr(
                        user.id,
                        "back"
                    ),
                    callback_data="back_main"
                )
            ]

        ]

        await query.message.edit_text(

            tr(
                user.id,
                "shop"
            ),

            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),

            parse_mode="HTML"
        )

        return


    if query.data == "main_profile":

        keyboard = [

            [
                InlineKeyboardButton(
                    tr(
                        user.id,
                        "back"
                    ),
                    callback_data="back_main"
                )
            ]

        ]

        await query.message.edit_text(

            tr(
                user.id,
                "profile",
                user_id=user.id,
                balance=data["balance"]
            ),

            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),

            parse_mode="HTML"
        )

        return


    if query.data == "main_refill":

        await refill_start(
            update,
            context
        )

        return REFILL_AMOUNT


    if query.data == "shop_stars":

        keyboard = [

            [
                InlineKeyboardButton(
                    "50 Stars — 10 500 сум",
                    callback_data="buy_stars_50"
                )
            ],

            [
                InlineKeyboardButton(
                    "100 Stars — 21 000 сум",
                    callback_data="buy_stars_100"
                )
            ],

            [
                InlineKeyboardButton(
                    "✏️ Ввести количество",
                    callback_data="buy_stars_manual"
                )
            ],

            [
                InlineKeyboardButton(
                    tr(
                        user.id,
                        "back"
                    ),
                    callback_data="main_shop"
                )
            ]

        ]

        await query.message.edit_text(

            tr(
                user.id,
                "stars",
                price=PRICE_PER_STAR
            ),

            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),

            parse_mode="HTML"
        )

        return


    if query.data == "shop_premium":

        keyboard = [

            [
                InlineKeyboardButton(
                    "3 месяца — 165 000 сум",
                    callback_data="buy_premium_3"
                )
            ],

            [
                InlineKeyboardButton(
                    "6 месяцев — 222 000 сум",
                    callback_data="buy_premium_6"
                )
            ],

            [
                InlineKeyboardButton(
                    "12 месяцев — 406 000 сум",
                    callback_data="buy_premium_12"
                )
            ],

            [
                InlineKeyboardButton(
                    tr(
                        user.id,
                        "back"
                    ),
                    callback_data="main_shop"
                )
            ]

        ]

        await query.message.edit_text(

            tr(
                user.id,
                "premium"
            ),

            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),

            parse_mode="HTML"
        )

        return


    if query.data == "shop_gifts":

        keyboard = []

        for gift_id, gift in GIFTS.items():

            keyboard.append(

                [
                    InlineKeyboardButton(

                        f"{gift['emoji']} — "
                        f"{gift['price']:,} сум",

                        callback_data=f"gift_{gift_id}"

                    )
                ]

            )

        keyboard.append(

            [
                InlineKeyboardButton(
                    tr(
                        user.id,
                        "back"
                    ),
                    callback_data="main_shop"
                )
            ]

        )

        await query.message.edit_text(

            tr(
                user.id,
                "gifts"
            ),

            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),

            parse_mode="HTML"
        )

        return


    if query.data == "shop_accounts":

        keyboard = [

            [
                InlineKeyboardButton(
                    "🇺🇿 Страна: Узбекистан",
                    callback_data="account_uz"
                )
            ],

            [
                InlineKeyboardButton(
                    "🇨🇴 Страна: Колумбия",
                    callback_data="account_co"
                )
            ],

            [
                InlineKeyboardButton(
                    "🇬🇧 Страна: Великобритания",
                    callback_data="account_uk"
                )
            ],

            [
                InlineKeyboardButton(
                    "🇺🇸 Страна: Америка",
                    callback_data="account_us"
                )
            ],

            [
                InlineKeyboardButton(
                    tr(
                        user.id,
                        "back"
                    ),
                    callback_data="main_shop"
                )
            ]

        ]

        await query.message.edit_text(

            tr(
                user.id,
                "accounts"
            ),

            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),

            parse_mode="HTML"
        )

        return


    if query.data.startswith("account_"):

        countries = {

            "account_uz":
                "Узбекистан",

            "account_co":
                "Колумбия",

            "account_uk":
                "Великобритания",

            "account_us":
                "Америка"

        }

        country = countries.get(

            query.data,

            "Неизвестная страна"

        )

        await context.bot.send_message(

            ADMIN_ID,

            (
                "📱 Новый заказ аккаунта\n\n"

                f"🌍 Страна: {country}\n"

                f"👤 Заказал: "
                f"@{user.username or 'нет username'}\n"

                f"🆔 ID: {user.id}"
            )

        )

        await query.message.edit_text(
            "✅ Заявка принята!"
        )


# =========================================================
# ЯЗЫК
# =========================================================

async def language_callback(
    update,
    context
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id


    if query.data == "lang_ru":

        set_language(
            user_id,
            "ru"
        )


    elif query.data == "lang_uz":

        set_language(
            user_id,
            "uz"
        )


    await query.message.edit_text(

        tr(
            user_id,
            "welcome",
            name=query.from_user.first_name,
            balance=get_user(
                user_id
            )["balance"]
        ),

        reply_markup=InlineKeyboardMarkup(

            [

                [

                    InlineKeyboardButton(
                        tr(
                            user_id,
                            "services"
                        ),
                        callback_data="main_shop"
                    )

                ],

                [

                    InlineKeyboardButton(
                        tr(
                            user_id,
                            "refill"
                        ),
                        callback_data="main_refill"
                    ),

                    InlineKeyboardButton(
                        tr(
                            user_id,
                            "profile"
                        ),
                        callback_data="main_profile"
                    )

                ],

                [

                    InlineKeyboardButton(
                        tr(
                            user_id,
                            "language"
                        ),
                        callback_data="language_menu"
                    )

                ]

            ]

        ),

        parse_mode="HTML"

    )


# =========================================================
# ПОПОЛНЕНИЕ
# =========================================================

async def refill_start(
    update,
    context
):

    query = update.callback_query

    await query.answer()

    context.user_data.clear()

    await query.message.edit_text(

        tr(
            query.from_user.id,
            "refill_enter"
        )

    )

    return REFILL_AMOUNT


async def refill_amount(
    update,
    context
):

    text = update.message.text.replace(
        " ",
        ""
    )

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
            card=CARD_NUMBER
        ),

        parse_mode="HTML"
    )

    return REFILL_CHECK


async def refill_check(
    update,
    context
):

    if not update.message.photo:

        await update.message.reply_text(

            tr(
                update.effective_user.id,
                "send_receipt"
            )

        )

        return REFILL_CHECK


    user = update.effective_user

    amount = context.user_data.get(
        "refill_amount",
        0
    )

    photo = update.message.photo[-1]

    caption = (

        "💳 <b>Новый запрос на пополнение</b>\n\n"

        f"👤 Пользователь: "
        f"@{user.username or 'нет username'}\n"

        f"🆔 ID: <code>{user.id}</code>\n"

        f"💰 Сумма: <b>{amount:,} сум</b>"

    )

    keyboard = InlineKeyboardMarkup(

        [

            [

                InlineKeyboardButton(
                    "✅ Одобрить",
                    callback_data=f"approve_refill_{user.id}_{amount}"
                ),

                InlineKeyboardButton(
                    "❌ Отклонить",
                    callback_data=f"reject_refill_{user.id}"
                )

            ]

        ]

    )

    await context.bot.send_photo(

        chat_id=ADMIN_ID,

        photo=photo.file_id,

        caption=caption,

        parse_mode="HTML",

        reply_markup=keyboard

    )

    await update.message.reply_text(

        tr(
            user.id,
            "receipt_sent"
        )

    )

    context.user_data.clear()

    return ConversationHandler.END# =========================================================
# ПОДАРКИ — ПРОДОЛЖЕНИЕ
# =========================================================

async def gift_username(
    update,
    context
):

    username = update.message.text.strip()

    username = username.replace(
        "@",
        ""
    )

    if not username or " " in username:

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
        user.first_name
    )

    if data["balance"] < gift["price"]:

        await update.message.reply_text(

            tr(
                user.id,
                "not_enough",
                price=gift["price"],
                balance=data["balance"]
            )

        )

        context.user_data.clear()

        return ConversationHandler.END

    anonymous = context.user_data.get(
        "anonymous",
        False
    )

    gift_text = context.user_data.get(
        "gift_text",
        ""
    )

    change_balance(
        user.id,
        -gift["price"]
    )

    sender_name = (
        "Анонимно"
        if anonymous
        else
        f"@{user.username or 'нет username'}"
    )

    await context.bot.send_message(

        ADMIN_ID,

        (
            "🎁 <b>НОВЫЙ ЗАКАЗ ПОДАРКА</b>\n\n"

            f"🎁 Подарок: {gift['emoji']}\n"

            f"💰 Цена: {gift['price']:,} сум\n\n"

            f"👤 Заказал: {sender_name}\n"

            f"🆔 ID заказчика: <code>{user.id}</code>\n\n"

            f"🎯 Получатель: @{username}\n"

            f"📝 Текст: "
            f"{gift_text or 'без текста'}\n\n"

            "⚠️ Отправьте подарок получателю вручную."
        ),

        parse_mode="HTML"
    )

    await update.message.reply_text(

        tr(
            user.id,
            "gift_success"
        )

    )

    context.user_data.clear()

    return ConversationHandler.END


# =========================================================
# ОТМЕНА
# =========================================================

async def cancel(
    update,
    context
):

    context.user_data.clear()

    user_id = update.effective_user.id

    if update.callback_query:

        query = update.callback_query

        await query.answer()

        await query.message.edit_text(

            tr(
                user_id,
                "cancelled"
            )

        )

    else:

        await update.message.reply_text(

            tr(
                user_id,
                "cancelled"
            )

        )

    return ConversationHandler.END


# =========================================================
# АДМИН
# =========================================================

def is_admin(
    user_id
):

    return user_id == ADMIN_ID


async def admin(
    update,
    context
):

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
                callback_data="admin_users"
            )

        ],

        [

            InlineKeyboardButton(
                "💰 Балансы",
                callback_data="admin_balances"
            )

        ],

        [

            InlineKeyboardButton(
                "📊 Статистика",
                callback_data="admin_stats"
            )

        ]

    ]

    await update.message.reply_text(

        "🛠 <b>Админ-панель</b>",

        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),

        parse_mode="HTML"
    )


async def admin_callback(
    update,
    context
):

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
            1
        ):

            user_id, username, name, balance, lang, banned = row

            username_text = (
                f"@{username}"
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

                f"<b>{index}. {name or 'Без имени'}</b>\n"

                f"👤 {username_text}\n"

                f"🆔 <code>{user_id}</code>\n"

                f"💰 {balance:,} сум\n"

                f"🌐 {lang}\n"

                f"{status}\n\n"

            )

        keyboard = [

            [

                InlineKeyboardButton(
                    "⬅️ Назад",
                    callback_data="admin_back"
                )

            ]

        ]

        await query.message.edit_text(

            text,

            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),

            parse_mode="HTML"
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

            reply_markup=InlineKeyboardMarkup(

                [

                    [

                        InlineKeyboardButton(
                            "⬅️ Назад",
                            callback_data="admin_back"
                        )

                    ]

                ]

            ),

            parse_mode="HTML"
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

            reply_markup=InlineKeyboardMarkup(

                [

                    [

                        InlineKeyboardButton(
                            "⬅️ Назад",
                            callback_data="admin_back"
                        )

                    ]

                ]

            ),

            parse_mode="HTML"
        )

        return


    if query.data == "admin_back":

        keyboard = [

            [

                InlineKeyboardButton(
                    "👥 Пользователи",
                    callback_data="admin_users"
                )

            ],

            [

                InlineKeyboardButton(
                    "💰 Балансы",
                    callback_data="admin_balances"
                )

            ],

            [

                InlineKeyboardButton(
                    "📊 Статистика",
                    callback_data="admin_stats"
                )

            ]

        ]

        await query.message.edit_text(

            "🛠 <b>Админ-панель</b>",

            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),

            parse_mode="HTML"
        )


# =========================================================
# ОДОБРЕНИЕ ПОПОЛНЕНИЙ
# =========================================================

async def payment_callback(
    update,
    context
):

    query = update.callback_query

    await query.answer()

    if not is_admin(
        query.from_user.id
    ):

        return

    parts = query.data.split("_")

    action = parts[1]

    user_id = int(
        parts[2]
    )

    if action == "yes":

        amount = int(
            parts[3]
        )

        change_balance(
            user_id,
            amount
        )

        await context.bot.send_message(

            user_id,

            (
                "✅ <b>Баланс пополнен!</b>\n\n"

                f"💰 Сумма: {amount:,} сум"
            ),

            parse_mode="HTML"
        )

        await query.edit_message_caption(

            caption=(
                query.message.caption
                + "\n\n✅ ОДОБРЕНО"
            ),

            parse_mode="HTML"
        )

    else:

        await context.bot.send_message(

            user_id,

            "❌ Пополнение отклонено."
        )

        await query.edit_message_caption(

            caption=(
                query.message.caption
                + "\n\n❌ ОТКЛОНЕНО"
            ),

            parse_mode="HTML"
        )


# =========================================================
# ОБРАБОТКА НЕИЗВЕСТНЫХ КНОПОК
# =========================================================

async def unknown_callback(
    update,
    context
):

    query = update.callback_query

    await query.answer(
        "❌ Эта кнопка больше неактивна.",
        show_alert=True
    )


# =========================================================
# ГЛАВНАЯ ФУНКЦИЯ
# =========================================================

def main():

    init_db()

    threading.Thread(
        target=run_web,
        daemon=True
    ).start()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "admin",
            admin
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            language_callback,
            pattern=r"^lang_(ru|uz)$"
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            payment_callback,
            pattern=r"^pay_(yes|no)_"
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            admin_callback,
            pattern=r"^admin_"
        )
    )

    application.add_handler(
        ConversationHandler(

            entry_points=[

                CallbackQueryHandler(
                    refill_start,
                    pattern=r"^main_refill$"
                ),

                CallbackQueryHandler(
                    buy_start,
                    pattern=r"^buy_(stars|premium)"
                ),

                CallbackQueryHandler(
                    gift_start,
                    pattern=r"^gift_\d+$"
                )

            ],

            states={

                REFILL_AMOUNT: [

                    MessageHandler(
                        filters.TEXT
                        & ~filters.COMMAND,
                        refill_amount
                    )

                ],

                REFILL_CHECK: [

                    MessageHandler(
                        filters.PHOTO,
                        refill_check
                    ),

                    MessageHandler(
                        filters.ALL,
                        refill_check
                    )

                ],

                BUY_AMOUNT: [

                    MessageHandler(
                        filters.TEXT
                        & ~filters.COMMAND,
                        buy_amount
                    )

                ],

                BUY_USERNAME: [

                    MessageHandler(
                        filters.TEXT
                        & ~filters.COMMAND,
                        buy_username
                    )

                ],

                BUY_CONFIRM: [

                    CallbackQueryHandler(
                        buy_confirm,
                        pattern=r"^(confirm_buy|cancel_buy)$"
                    )

                ],

                GIFT_SEND_TYPE: [

                    CallbackQueryHandler(
                        gift_send_type,
                        pattern=r"^(gift_anonymous_yes|gift_anonymous_no|cancel_gift)$"
                    )

                ],

                GIFT_TEXT: [

                    CallbackQueryHandler(
                        gift_text_choice,
                        pattern=r"^(gift_text_yes|gift_text_no|cancel_gift)$"
                    ),

                    MessageHandler(
                        filters.TEXT
                        & ~filters.COMMAND,
                        gift_text_input
                    )

                ],

                GIFT_USERNAME: [

                    MessageHandler(
                        filters.TEXT
                        & ~filters.COMMAND,
                        gift_username
                    )

                ]

            },

            fallbacks=[

                CommandHandler(
                    "cancel",
                    cancel
                ),

                CallbackQueryHandler(
                    cancel,
                    pattern=r"^cancel_"
                )

            ],

            allow_reentry=True,

            per_user=True,

            per_chat=True

        )

    )

    application.add_handler(

        CallbackQueryHandler(
            main_buttons,
            pattern=r"^(main_|shop_|back_main|account_)"
        )

    )

    application.add_handler(

        CallbackQueryHandler(
            unknown_callback
        )

    )

    logger.info(
        "BOT STARTED"
    )

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":

    main()