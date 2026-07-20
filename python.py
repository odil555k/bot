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
# БАН
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

    return False


# =========================================================
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
# КЛАВИАТУРА ГЛАВНОГО МЕНЮ
# =========================================================

def main_keyboard(user_id):

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    tr(user_id, "services"),
                    callback_data="main_shop"
                )
            ],

            [
                InlineKeyboardButton(
                    tr(user_id, "refill"),
                    callback_data="main_refill"
                ),

                InlineKeyboardButton(
                    tr(user_id, "profile"),
                    callback_data="main_profile"
                )
            ],

            [
                InlineKeyboardButton(
                    tr(user_id, "language"),
                    callback_data="language_menu"
                )
            ]
        ]
    )


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

    await update.message.reply_text(
        tr(
            user.id,
            "welcome",
            name=user.first_name,
            balance=data["balance"]
        ),
        reply_markup=main_keyboard(user.id),
        parse_mode="HTML"
    )

    return ConversationHandler.END


# =========================================================
# ГЛАВНЫЕ КНОПКИ
# =========================================================

async def main_buttons(
    update,
    context
):

    if await check_ban(update):
        return ConversationHandler.END

    query = update.callback_query

    await query.answer()

    user = query.from_user

    data = get_user(
        user.id,
        user.username,
        user.first_name
    )

    if query.data == "back_main":

        await query.message.edit_text(
            tr(
                user.id,
                "welcome",
                name=user.first_name,
                balance=data["balance"]
            ),
            reply_markup=main_keyboard(user.id),
            parse_mode="HTML"
        )

        return ConversationHandler.END

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
                    tr(user.id, "back"),
                    callback_data="back_main"
                )
            ]
        ]

        await query.message.edit_text(
            "🌐 <b>Выберите язык / Tilni tanlang</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return ConversationHandler.END

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
                    tr(user.id, "back"),
                    callback_data="back_main"
                )
            ]
        ]

        await query.message.edit_text(
            tr(
                user.id,
                "shop"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return ConversationHandler.END

    if query.data == "main_profile":

        keyboard = [
            [
                InlineKeyboardButton(
                    tr(user.id, "back"),
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
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return ConversationHandler.END

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
                    "200 Stars — 42 000 сум",
                    callback_data="buy_stars_200"
                )
            ],

            [
                InlineKeyboardButton(
                    "400 Stars — 84 000 сум",
                    callback_data="buy_stars_400"
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
                    tr(user.id, "back"),
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
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return ConversationHandler.END

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
                    tr(user.id, "back"),
                    callback_data="main_shop"
                )
            ]
        ]

        await query.message.edit_text(
            tr(
                user.id,
                "premium"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return ConversationHandler.END

    if query.data == "shop_gifts":

        keyboard = []

        for gift_id, gift in GIFTS.items():

            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{gift['emoji']} — {gift['price']:,} сум",
                        callback_data=f"gift_{gift_id}"
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    tr(user.id, "back"),
                    callback_data="main_shop"
                )
            ]
        )

        await query.message.edit_text(
            tr(
                user.id,
                "gifts"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return ConversationHandler.END

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
                    tr(user.id, "back"),
                    callback_data="main_shop"
                )
            ]
        ]

        await query.message.edit_text(
            tr(
                user.id,
                "accounts"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return ConversationHandler.END

    if query.data.startswith("account_"):

        countries = {
            "account_uz": "Узбекистан",
            "account_co": "Колумбия",
            "account_uk": "Великобритания",
            "account_us": "Америка"
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
                f"👤 Заказал: @{user.username or 'нет username'}\n"
                f"🆔 ID: {user.id}"
            )
        )

        await query.message.edit_text(
            "✅ Заявка принята!"
        )

        return ConversationHandler.END

    return ConversationHandler.END


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
            balance=get_user(user_id)["balance"]
        ),
        reply_markup=main_keyboard(user_id),
        parse_mode="HTML"
    )

    return ConversationHandler.END


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

    user = update.effective_user

    amount = context.user_data.get(
        "refill_amount",
        0
    )

    if update.message.photo:

        file_id = update.message.photo[-1].file_id

        await context.bot.send_photo(
            ADMIN_ID,
            file_id,
            caption=(
                "💰 Пополнение баланса\n\n"
                f"👤 Заказал: @{user.username or 'нет username'}\n"
                f"🆔 ID: {user.id}\n"
                f"💵 Сумма: {amount:,} сум"
            ),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "✅ Одобрить",
                            callback_data=f"pay_yes_{user.id}_{amount}"
                        ),

                        InlineKeyboardButton(
                            "❌ Отклонить",
                            callback_data=f"pay_no_{user.id}"
                        )
                    ]
                ]
            )
        )

    else:

        await update.message.reply_text(
            tr(
                user.id,
                "send_receipt"
            )
        )

        return REFILL_CHECK

    await update.message.reply_text(
        tr(
            user.id,
            "receipt_sent"
        )
    )

    context.user_data.clear()

    return ConversationHandler.END


# =========================================================
# ПОКУПКА STARS / PREMIUM
# =========================================================

async def buy_start(
    update,
    context
):

    query = update.callback_query

    await query.answer()

    context.user_data.clear()

    if query.data == "buy_stars_manual":

        context.user_data["buy_type"] = "stars"

        await query.message.edit_text(
            tr(
                query.from_user.id,
                "enter_stars"
            )
        )

        return BUY_AMOUNT

    if query.data.startswith("buy_stars_"):

        value = int(
            query.data.split("_")[-1]
        )

        context.user_data["buy_type"] = "stars"
        context.user_data["buy_value"] = value
        context.user_data["buy_price"] = value * PRICE_PER_STAR

    elif query.data.startswith("buy_premium_"):

        value = int(
            query.data.split("_")[-1]
        )

        context.user_data["buy_type"] = "premium"
        context.user_data["buy_value"] = value
        context.user_data["buy_price"] = PREMIUM_PRICES[value]

    await query.message.edit_text(
        tr(
            query.from_user.id,
            "enter_username"
        )
    )

    return BUY_USERNAME


async def buy_amount(
    update,
    context
):

    text = update.message.text.strip()

    if not text.isdigit():

        await update.message.reply_text(
            "❌ Введите число."
        )

        return BUY_AMOUNT

    value = int(text)

    if value < 50 or value > 10000:

        await update.message.reply_text(
            "❌ Можно купить от 50 до 10000 Stars."
        )

        return BUY_AMOUNT

    context.user_data["buy_type"] = "stars"
    context.user_data["buy_value"] = value
    context.user_data["buy_price"] = value * PRICE_PER_STAR

    await update.message.reply_text(
        tr(
            update.effective_user.id,
            "enter_username"
        )
    )

    return BUY_USERNAME


async def buy_username(
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

        return BUY_USERNAME

    context.user_data["target"] = username

    product_type = context.user_data["buy_type"]
    value = context.user_data["buy_value"]
    price = context.user_data["buy_price"]

    if product_type == "stars":

        product = f"{value} Stars"

    else:

        product = f"Premium на {value} месяцев"

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Купить",
                callback_data="confirm_buy"
            )
        ],

        [
            InlineKeyboardButton(
                "❌ Отмена",
                callback_data="cancel_buy"
            )
        ]
    ]

    await update.message.reply_text(
        (
            "📝 <b>Подтверждение покупки</b>\n\n"
            f"📦 Товар: {product}\n"
            f"👤 Получатель: @{username}\n"
            f"💰 Стоимость: <b>{price:,} сум</b>\n\n"
            "Подтвердить?"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

    return BUY_CONFIRM


async def buy_confirm(
    update,
    context
):

    query = update.callback_query

    await query.answer()

    if query.data == "cancel_buy":

        context.user_data.clear()

        await query.message.edit_text(
            tr(
                query.from_user.id,
                "cancelled"
            )
        )

        return ConversationHandler.END

    user = query.from_user

    data = get_user(
        user.id,
        user.username,
        user.first_name
    )

    product_type = context.user_data["buy_type"]
    value = context.user_data["buy_value"]
    price = context.user_data["buy_price"]
    target = context.user_data["target"]

    if data["balance"] < price:

        await query.message.edit_text(
            tr(
                user.id,
                "not_enough",
                price=price,
                balance=data["balance"]
            )
        )

        context.user_data.clear()

        return ConversationHandler.END

    await query.message.edit_text(
        tr(
            user.id,
            "processing"
        )
    )

    client_order_id = (
        f"{user.id}_{int(time.time() * 1000)}"
    )

    success = await elder_buy(
        product_type,
        value,
        target,
        client_order_id
    )

    if not success:

        await query.message.edit_text(
            tr(
                user.id,
                "api_error"
            )
        )

        context.user_data.clear()

        return ConversationHandler.END

    change_balance(
        user.id,
        -price
    )

    if product_type == "stars":

        product = f"{value} Stars"

    else:

        product = f"Premium на {value} месяцев"

    await query.message.edit_text(
        tr(
            user.id,
            "success",
            product=product,
            username=target
        ),
        parse_mode="HTML"
    )

    await context.bot.send_message(
        ADMIN_ID,
        (
            "🚀 Новый заказ\n\n"
            f"👤 Заказал: @{user.username or 'нет username'}\n"
            f"🆔 ID: {user.id}\n"
            f"📦 Товар: {product}\n"
            f"🎯 Получатель: @{target}\n"
            f"💰 Сумма: {price:,} сум"
        )
    )

    context.user_data.clear()

    return ConversationHandler.END


async def elder_buy(
    product_type,
    value,
    username,
    client_order_id
):

    username = username.replace(
        "@",
        ""
    ).strip()

    headers = {
        "X-Api-Key": ELDER_API_KEY,
        "Content-Type": "application/json"
    }

    if product_type == "stars":

        url = f"{ELDER_API_URL}/stars/buy"

        payload = {
            "username": username,
            "amount": value,
            "client_order_id": client_order_id
        }

    else:

        url = f"{ELDER_API_URL}/premium/buy"

        payload = {
            "username": username,
            "months": value,
            "client_order_id": client_order_id
        }

    try:

        async with httpx.AsyncClient() as client:

            response = await client.post(
                url,
                headers=headers,
                json=payload,
                timeout=30
            )

        data = response.json()

        return (
            response.status_code == 200
            and data.get("success") is True
        )

    except Exception as error:

        logger.error(
            "API ERROR: %s",
            error
        )

        return False


# =========================================================
# ПОДАРКИ
# =========================================================

async def gift_start(
    update,
    context
):

    query = update.callback_query

    await query.answer()

    context.user_data.clear()

    gift_id = int(
        query.data.split("_")[-1]
    )

    gift = GIFTS[gift_id]

    data = get_user(
        query.from_user.id
    )

    if data["balance"] < gift["price"]:

        await query.message.edit_text(
            tr(
                query.from_user.id,
                "not_enough",
                price=gift["price"],
                balance=data["balance"]
            )
        )

        return ConversationHandler.END

    context.user_data["gift_id"] = gift_id

    keyboard = [
        [
            InlineKeyboardButton(
                "🕵️ Отправить анонимно",
                callback_data="gift_anonymous_yes"
            )
        ],

        [
            InlineKeyboardButton(
                "👤 Не отправлять анонимно",
                callback_data="gift_anonymous_no"
            )
        ],

        [
            InlineKeyboardButton(
                tr(query.from_user.id, "back"),
                callback_data="cancel_gift"
            )
        ]
    ]

    await query.message.edit_text(
        tr(
            query.from_user.id,
            "gift_send_type"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

    return GIFT_SEND_TYPE


async def gift_send_type(
    update,
    context
):

    query = update.callback_query

    await query.answer()

    if query.data == "cancel_gift":

        context.user_data.clear()

        await query.message.edit_text(
            tr(
                query.from_user.id,
                "cancelled"
            )
        )

        return ConversationHandler.END

    context.user_data["anonymous"] = (
        query.data == "gift_anonymous_yes"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "✍️ Добавить текст",
                callback_data="gift_text_yes"
            )
        ],

        [
            InlineKeyboardButton(
                "🎁 Просто отправить",
                callback_data="gift_text_no"
            )
        ],

        [
            InlineKeyboardButton(
                tr(query.from_user.id, "back"),
                callback_data="cancel_gift"
            )
        ]
    ]

    await query.message.edit_text(
        "💬 <b>Добавить текст к подарку?</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

    return GIFT_TEXT


async def gift_text_choice(
    update,
    context
):

    query = update.callback_query

    await query.answer()

    if query.data == "cancel_gift":

        context.user_data.clear()

        await query.message.edit_text(
            tr(
                query.from_user.id,
                "cancelled"
            )
        )

        return ConversationHandler.END

    if query.data == "gift_text_yes":

        await query.message.edit_text(
            tr(
                query.from_user.id,
                "gift_text"
            )
        )

        return GIFT_TEXT

    context.user_data["gift_text"] = ""

    await query.message.edit_text(
        tr(
            query.from_user.id,
            "gift_username"
        )
    )

    return GIFT_USERNAME


async def gift_text_input(
    update,
    context
):

    context.user_data["gift_text"] = update.message.text

    await update.message.reply_text(
        tr(
            update.effective_user.id,
            "gift_username"
        )
    )

    return GIFT_USERNAME


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

    admin_text = (
        "🎁 Новый заказ подарка\n\n"
        f"🎁 Подарок: {gift['name']}\n\n"
        f"👤 Заказал: @{user.username or 'нет username'}\n"
        f"🆔 ID: {user.id}\n\n"
        f"🎯 Получатель: @{username}\n\n"
        f"🕵️ Анонимно: {'Да' if anonymous else 'Нет'}\n"
        f"💬 Текст: {gift_text if gift_text else 'Нет'}\n\n"
        f"💰 Цена: {gift['price']:,} сум"
    )

    emoji_utf16_length = len(
        gift["emoji"].encode("utf-16-le")
    ) // 2

    entities = [
        MessageEntity(
            type="custom_emoji",
            offset=0,
            length=emoji_utf16_length,
            custom_emoji_id=gift["emoji_id"]
        )
    ]

    await context.bot.send_message(
        ADMIN_ID,
        admin_text,
        entities=entities
    )

    await update.message.reply_text(
        tr(
            user.id,
            "gift_success"
        ),
        parse_mode="HTML"
    )

    context.user_data.clear()

    return ConversationHandler.END


# =========================================================
# АДМИН
# =========================================================

async def admin(
    update,
    context
):

    if update.effective_user.id != ADMIN_ID:
        return

    keyboard = [
        [
            InlineKeyboardButton(
                "👥 Пользователи",
                callback_data="admin_users_0"
            )
        ],

        [
            InlineKeyboardButton(
                "❌ Закрыть",
                callback_data="admin_close"
            )
        ]
    ]

    await update.message.reply_text(
        (
            "🛠 <b>Админ-панель</b>\n\n"
            "/setbal ID СУММА\n"
            "/ban ID\n"
            "/unban ID\n"
            "/msg ID ТЕКСТ"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )


async def admin_callback(
    update,
    context
):

    if update.effective_user.id != ADMIN_ID:

        await update.callback_query.answer(
            "⛔ Только для администратора!",
            show_alert=True
        )

        return

    query = update.callback_query

    await query.answer()

    if query.data == "admin_close":

        await query.message.delete()

        return

    if query.data.startswith("admin_users_"):

        page = int(
            query.data.split("_")[-1]
        )

        users = get_users()

        per_page = 10

        start_index = page * per_page
        end_index = start_index + per_page

        page_users = users[
            start_index:end_index
        ]

        total_pages = max(
            1,
            (len(users) + per_page - 1) // per_page
        )

        text = (
            "👥 <b>Пользователи</b>\n"
            f"📄 Страница {page + 1}/{total_pages}\n\n"
        )

        for (
            user_id,
            username,
            name,
            balance,
            lang,
            banned
        ) in page_users:

            username_text = (
                f"@{username}"
                if username
                else "❌ Нет username"
            )

            status = (
                "⛔ БАН"
                if banned
                else "🟢 Активен"
            )

            text += (
                "━━━━━━━━━━━━━━\n"
                f"👤 {username_text}\n"
                f"🆔 ID: {user_id}\n"
                f"💰 Баланс: {balance:,} сум\n"
                f"🌐 Язык: {lang}\n"
                f"🚫 Статус: {status}\n\n"
            )

        keyboard = []

        nav = []

        if page > 0:

            nav.append(
                InlineKeyboardButton(
                    "⬅️",
                    callback_data=f"admin_users_{page - 1}"
                )
            )

        if end_index < len(users):

            nav.append(
                InlineKeyboardButton(
                    "➡️",
                    callback_data=f"admin_users_{page + 1}"
                )
            )

        if nav:

            keyboard.append(nav)

        keyboard.append(
            [
                InlineKeyboardButton(
                    "❌ Закрыть",
                    callback_data="admin_close"
                )
            ]
        )

        await query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )


async def setbal(
    update,
    context
):

    if update.effective_user.id != ADMIN_ID:
        return

    if len(context.args) < 2:

        await update.message.reply_text(
            "Использование: /setbal ID СУММА"
        )

        return

    user_id = int(
        context.args[0]
    )

    amount = int(
        context.args[1]
    )

    change_balance(
        user_id,
        amount
    )

    data = get_user(user_id)

    await update.message.reply_text(
        f"✅ Баланс: {data['balance']:,} сум"
    )


async def ban(
    update,
    context
):

    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        return

    set_ban(
        int(context.args[0]),
        True
    )

    await update.message.reply_text(
        "⛔ Пользователь заблокирован."
    )


async def unban(
    update,
    context
):

    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        return

    set_ban(
        int(context.args[0]),
        False
    )

    await update.message.reply_text(
        "🟢 Пользователь разблокирован."
    )


async def msg(
    update,
    context
):

    if update.effective_user.id != ADMIN_ID:
        return

    if len(context.args) < 2:
        return

    user_id = int(
        context.args[0]
    )

    text = " ".join(
        context.args[1:]
    )

    await context.bot.send_message(
        user_id,
        text
    )

    await update.message.reply_text(
        "✅ Сообщение отправлено."
    )


# =========================================================
# ПОПОЛНЕНИЕ — АДМИН
# =========================================================

async def payment_callback(
    update,
    context
):

    if update.effective_user.id != ADMIN_ID:
        return

    query = update.callback_query

    await query.answer()

    if query.data.startswith("pay_yes_"):

        parts = query.data.split("_")

        user_id = int(parts[2])
        amount = int(parts[3])

        change_balance(
            user_id,
            amount
        )

        await query.message.edit_caption(
            "🟢 Пополнение одобрено."
        )

        try:

            await context.bot.send_message(
                user_id,
                "🎉 Баланс успешно пополнен!"
            )

        except Exception:

            pass

    elif query.data.startswith("pay_no_"):

        await query.message.edit_caption(
            "🔴 Пополнение отклонено."
        )


# =========================================================
# ВАЖНО:
# КНОПКИ МЕНЮ ВО ВРЕМЯ АКТИВНОЙ ПОКУПКИ
# =========================================================

async def conversation_global_callback(
    update,
    context
):

    query = update.callback_query

    if query.data == "language_menu":

        await main_buttons(
            update,
            context
        )

        return ConversationHandler.END

    if query.data.startswith("lang_"):

        await language_callback(
            update,
            context
        )

        return ConversationHandler.END

    await main_buttons(
        update,
        context
    )

    return ConversationHandler.END


# =========================================================
# ЗАПУСК
# =========================================================

def main():

    init_db()

    threading.Thread(
        target=run_web,
        daemon=True
    ).start()

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        ConversationHandler(
            entry_points=[

                CallbackQueryHandler(
                    refill_start,
                    pattern=r"^main_refill$"
                ),

                CallbackQueryHandler(
                    buy_start,
                    pattern=(
                        r"^buy_stars_manual$|"
                        r"^buy_stars_[0-9]+$|"
                        r"^buy_premium_[0-9]+$"
                    )
                ),

                CallbackQueryHandler(
                    gift_start,
                    pattern=r"^gift_[0-9]+$"
                )
            ],

            states={

                REFILL_AMOUNT: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        refill_amount
                    )
                ],

                REFILL_CHECK: [
                    MessageHandler(
                        filters.PHOTO,
                        refill_check
                    )
                ],

                BUY_AMOUNT: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        buy_amount
                    )
                ],

                BUY_USERNAME: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        buy_username
                    )
                ],

                BUY_CONFIRM: [
                    CallbackQueryHandler(
                        buy_confirm,
                        pattern=r"^confirm_buy$|^cancel_buy$"
                    )
                ],

                GIFT_SEND_TYPE: [
                    CallbackQueryHandler(
                        gift_send_type,
                        pattern=(
                            r"^gift_anonymous_yes$|"
                            r"^gift_anonymous_no$|"
                            r"^cancel_gift$"
                        )
                    )
                ],

                GIFT_TEXT: [

                    CallbackQueryHandler(
                        gift_text_choice,
                        pattern=(
                            r"^gift_text_yes$|"
                            r"^gift_text_no$|"
                            r"^cancel_gift$"
                        )
                    ),

                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        gift_text_input
                    )
                ],

                GIFT_USERNAME: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        gift_username
                    )
                ]
            },

            fallbacks=[

                CommandHandler(
                    "start",
                    start
                ),

                CallbackQueryHandler(
                    conversation_global_callback,
                    pattern=(
                        r"^main_shop$|"
                        r"^main_profile$|"
                        r"^back_main$|"
                        r"^shop_stars$|"
                        r"^shop_premium$|"
                        r"^shop_gifts$|"
                        r"^shop_accounts$|"
                        r"^account_|"
                        r"^language_menu$|"
                        r"^lang_"
                    )
                )
            ],

            allow_reentry=True
        )
    )

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "admin",
            admin
        )
    )

    app.add_handler(
        CommandHandler(
            "setbal",
            setbal
        )
    )

    app.add_handler(
        CommandHandler(
            "ban",
            ban
        )
    )

    app.add_handler(
        CommandHandler(
            "unban",
            unban
        )
    )

    app.add_handler(
        CommandHandler(
            "msg",
            msg
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            language_callback,
            pattern=r"^lang_|^language_menu$"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            admin_callback,
            pattern=r"^admin_"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            payment_callback,
            pattern=r"^pay_yes_|^pay_no_"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            main_buttons,
            pattern=(
                r"^main_shop$|"
                r"^main_profile$|"
                r"^back_main$|"
                r"^shop_stars$|"
                r"^shop_premium$|"
                r"^shop_gifts$|"
                r"^shop_accounts$|"
                r"^account_"
            )
        )
    )

    logger.info(
        "BOT STARTED"
    )

    app.run_polling()


if __name__ == "__main__":
    main()