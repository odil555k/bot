import threading
import asyncio
import json
import logging
import os
import sqlite3
import time

from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    MessageEntity,
)

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)


# =========================================================
# ЛОГИРОВАНИЕ
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)


# =========================================================
# НАСТРОЙКИ
# =========================================================

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])

ELDER_API_KEY = os.environ["ELDER_API_KEY"]
ELDER_API_URL = "https://asosiy.elder.uz/api"

CARD_NUMBER = "5614 6835 8985 1641"

PRICE_PER_STAR = 210

PREMIUM_PRICES = {
    3: 165000,
    6: 222000,
    12: 406000
}

DB_FILE = "bot_database.db"

DEFAULT_LANG = "ru"


# =========================================================
# СОСТОЯНИЯ
# =========================================================

REFILL_AMOUNT = 1
REFILL_CHECK = 2

BUY_AMOUNT = 3
BUY_USERNAME = 4
BUY_CONFIRM = 5

GIFT_USERNAME = 6


# =========================================================
# ПОДАРКИ
# =========================================================

GIFTS = {
    1: {
        "emoji": "🧸",
        "emoji_id": "5280598054901145762",
        "price": 3500,
        "name": "Подарок"
    },
    2: {
        "emoji": "💝",
        "emoji_id": "5283228279988309088",
        "price": 3500,
        "name": "Подарок"
    },
    3: {
        "emoji": "🎁",
        "emoji_id": "5280615440928758599",
        "price": 5000,
        "name": "Подарок"
    },
    4: {
        "emoji": "🌹",
        "emoji_id": "5280947338821524402",
        "price": 5000,
        "name": "Подарок"
    },
    5: {
        "emoji": "🎂",
        "emoji_id": "5280659198055572187",
        "price": 10000,
        "name": "Подарок"
    },
    6: {
        "emoji": "💐",
        "emoji_id": "5280774333243873175",
        "price": 10000,
        "name": "Подарок"
    },
    7: {
        "emoji": "🚀",
        "emoji_id": "5283080528818360566",
        "price": 10000,
        "name": "Подарок"
    },
    8: {
        "emoji": "🏆",
        "emoji_id": "5280769763398671636",
        "price": 20500,
        "name": "Подарок"
    },
    9: {
        "emoji": "💍",
        "emoji_id": "5280651583078556009",
        "price": 20500,
        "name": "Подарок"
    },
    10: {
        "emoji": "💎",
        "emoji_id": "5280922999241859582",
        "price": 20500,
        "name": "Подарок"
    },
    11: {
        "emoji": "🍾",
        "emoji_id": "5451905784734574339",
        "price": 10000,
        "name": "Подарок"
    }
}


# =========================================================
# ТЕКСТЫ
# =========================================================

TEXTS = {
    "ru": {
        "welcome": (
            "👋 Привет, {name}!\n\n"
            "Добро пожаловать в магазин Telegram Stars & Premium.\n\n"
            "💰 Ваш баланс: {balance:,} сум"
        ),

        "btn_shop": "🛍 Услуги",
        "btn_refill": "💳 Пополнить баланс",
        "btn_profile": "👤 Мой профиль",
        "btn_back": "⬅️ Назад",
        "btn_cancel": "❌ Отмена",

        "profile_text": (
            "👤 <b>Мой профиль</b>\n\n"
            "🆔 ID: <code>{user_id}</code>\n"
            "💰 Баланс: <b>{balance:,} сум</b>\n\n"
            "🌐 Выберите язык:"
        ),

        "shop_main": "🛍 <b>Выберите услугу:</b>",

        "shop_stars": "💎 Telegram Stars",
        "shop_premium": "🌟 Telegram Premium",
        "shop_gifts": "🎁 Telegram подарки",
        "shop_accounts": "📱 Telegram аккаунты",

        "stars_desc": (
            "💎 <b>Telegram Stars</b>\n\n"
            "💵 Цена: {price} сум за 1 Stars"
        ),

        "stars_manual": "✏️ Ввести количество",

        "premium_desc": (
            "🌟 <b>Telegram Premium</b>\n\n"
            "🔹 3 месяца — 165,000 сум\n"
            "🔹 6 месяцев — 222,000 сум\n"
            "🔹 12 месяцев — 406,000 сум"
        ),

        "gifts_desc": (
            "🎁 <b>Выберите подарок:</b>\n\n"
            "После выбора нужно будет указать юзернейм получателя."
        ),

        "accounts_desc": "📱 <b>Выберите страну номера:</b>",

        "refill_start": (
            "💳 Введите сумму пополнения в сумах.\n\n"
            "Например: <code>50000</code>"
        ),

        "refill_bad_num": "❌ Введите корректную сумму.",

        "refill_invoice": (
            "💳 <b>Заявка на пополнение</b>\n\n"
            "💰 Сумма: <b>{amount:,} сум</b>\n\n"
            "Переведите ровно эту сумму на карту:\n"
            "<code>{card}</code>\n\n"
            "После оплаты отправьте фото или скриншот чека."
        ),

        "refill_bad_photo": "❌ Отправьте именно фото или скриншот чека.",

        "refill_done": (
            "⏳ Чек отправлен администратору на проверку."
        ),

        "buy_stars_enter": (
            "✏️ Введите количество Telegram Stars.\n\n"
            "Минимум: 50"
        ),

        "buy_username_enter": (
            "✏️ Введите Telegram юзернейм получателя.\n\n"
            "Без символа @\n"
            "Например: <code>durov</code>"
        ),

        "buy_confirm": (
            "📝 <b>Подтверждение покупки</b>\n\n"
            "📦 Товар: {product}\n"
            "👤 Получатель: @{target}\n"
            "💰 Стоимость: <b>{price:,} сум</b>\n\n"
            "Подтвердить покупку?"
        ),

        "buy_confirm_btn": "✅ Купить",

        "not_enough": (
            "❌ Недостаточно средств.\n\n"
            "💰 Нужно: {price:,} сум\n"
            "💳 Ваш баланс: {balance:,} сум"
        ),

        "api_error": (
            "❌ Не удалось выполнить заказ.\n\n"
            "Деньги не списаны. Попробуйте позже."
        ),

        "order_success": (
            "✅ <b>Заказ успешно выполнен!</b>\n\n"
            "📦 {product}\n"
            "👤 Получатель: @{target}"
        ),

        "gift_username": (
            "✏️ Введите юзернейм получателя подарка.\n\n"
            "Без символа @"
        ),

        "gift_success": (
            "✅ <b>Заказ подарка принят!</b>\n\n"
            "🎁 Подарок будет отправлен получателю."
        ),

        "banned": "❌ Вы заблокированы в этом боте."
    }
}


# =========================================================
# БАЗА ДАННЫХ
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


def get_user_data(user_id, username="", name=""):
    conn = sqlite3.connect(DB_FILE)

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT balance, username, name, lang, is_banned
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
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                username or "",
                name or "",
                0,
                DEFAULT_LANG,
                0
            )
        )

        conn.commit()

        result = {
            "balance": 0,
            "username": username or "",
            "name": name or "",
            "lang": DEFAULT_LANG,
            "is_banned": False
        }

    else:
        balance, old_username, old_name, lang, is_banned = row

        # ОБНОВЛЯЕМ USERNAME И ИМЯ
        if username or name:
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
            "balance": balance,
            "username": username or old_username or "",
            "name": name or old_name or "",
            "lang": lang,
            "is_banned": bool(is_banned)
        }

    conn.close()

    return result


def update_user_balance(user_id, amount):
    conn = sqlite3.connect(DB_FILE)

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE users
        SET balance = balance + ?
        WHERE user_id = ?
        """,
        (amount, user_id)
    )

    conn.commit()
    conn.close()


def update_user_lang(user_id, lang):
    conn = sqlite3.connect(DB_FILE)

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE users
        SET lang = ?
        WHERE user_id = ?
        """,
        (lang, user_id)
    )

    conn.commit()
    conn.close()


def update_user_ban(user_id, is_banned):
    conn = sqlite3.connect(DB_FILE)

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE users
        SET is_banned = ?
        WHERE user_id = ?
        """,
        (1 if is_banned else 0, user_id)
    )

    conn.commit()
    conn.close()


def get_all_users():
    conn = sqlite3.connect(DB_FILE)

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT user_id, username, name, balance, is_banned
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

async def is_user_banned(update: Update):
    user = update.effective_user

    if not user:
        return False

    user_data = get_user_data(
        user.id,
        user.username,
        user.first_name
    )

    if not user_data["is_banned"]:
        return False

    if update.message:
        await update.message.reply_text(
            TEXTS["ru"]["banned"]
        )

    elif update.callback_query:
        await update.callback_query.answer(
            TEXTS["ru"]["banned"],
            show_alert=True
        )

    return True


# =========================================================
# WEB SERVER ДЛЯ RENDER
# =========================================================

class WebServerHandler(BaseHTTPRequestHandler):

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

    def log_message(self, format, *args):
        return


def run_web_server():
    port = int(
        os.environ.get(
            "PORT",
            8080
        )
    )

    server = HTTPServer(
        ("0.0.0.0", port),
        WebServerHandler
    )

    logger.info(
        f"Web server started on port {port}"
    )

    server.serve_forever()


# =========================================================
# API ЗАКАЗОВ
# =========================================================

async def send_order_to_api(
    product_type,
    value,
    username,
    client_order_id
):

    username = username.replace("@", "").strip()

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

        logger.info(
            f"API status: {response.status_code}"
        )

        try:
            data = response.json()

        except Exception:
            logger.error(
                "API returned invalid JSON"
            )

            return False

        if response.status_code == 200 and data.get("success") is True:
            return True

        logger.error(
            f"Order failed: {data}"
        )

        return False

    except Exception as e:

        logger.error(
            f"API connection error: {e}"
        )

        return False


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if await is_user_banned(update):
        return ConversationHandler.END

    context.user_data.clear()

    user = update.effective_user

    user_data = get_user_data(
        user.id,
        user.username,
        user.first_name
    )

    text = TEXTS["ru"]["welcome"].format(
        name=user.first_name,
        balance=user_data["balance"]
    )

    keyboard = [
        [
            InlineKeyboardButton(
                TEXTS["ru"]["btn_shop"],
                callback_data="main_shop"
            )
        ],
        [
            InlineKeyboardButton(
                TEXTS["ru"]["btn_refill"],
                callback_data="main_refill"
            ),
            InlineKeyboardButton(
                TEXTS["ru"]["btn_profile"],
                callback_data="main_profile"
            )
        ]
    ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )


# =========================================================
# ГЛАВНОЕ МЕНЮ
# =========================================================

async def menu_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if await is_user_banned(update):
        return

    query = update.callback_query

    await query.answer()

    user = query.from_user

    user_data = get_user_data(
        user.id,
        user.username,
        user.first_name
    )

    t = TEXTS["ru"]

    # ГЛАВНОЕ МЕНЮ
    if query.data == "back_to_main":

        keyboard = [
            [
                InlineKeyboardButton(
                    t["btn_shop"],
                    callback_data="main_shop"
                )
            ],
            [
                InlineKeyboardButton(
                    t["btn_refill"],
                    callback_data="main_refill"
                ),
                InlineKeyboardButton(
                    t["btn_profile"],
                    callback_data="main_profile"
                )
            ]
        ]

        text = t["welcome"].format(
            name=user.first_name,
            balance=user_data["balance"]
        )

        await query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return

    # УСЛУГИ
    if query.data == "main_shop":

        keyboard = [
            [
                InlineKeyboardButton(
                    t["shop_stars"],
                    callback_data="shop_stars"
                )
            ],
            [
                InlineKeyboardButton(
                    t["shop_premium"],
                    callback_data="shop_premium"
                )
            ],
            [
                InlineKeyboardButton(
                    t["shop_gifts"],
                    callback_data="shop_gifts"
                )
            ],
            [
                InlineKeyboardButton(
                    t["shop_accounts"],
                    callback_data="shop_accounts"
                )
            ],
            [
                InlineKeyboardButton(
                    t["btn_back"],
                    callback_data="back_to_main"
                )
            ]
        ]

        await query.message.edit_text(
            t["shop_main"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return

    # ПРОФИЛЬ
    if query.data == "main_profile":

        keyboard = [
            [
                InlineKeyboardButton(
                    "🇷🇺 Русский",
                    callback_data="setlang_ru"
                ),
                InlineKeyboardButton(
                    "🇺🇿 O'zbekcha",
                    callback_data="setlang_uz"
                )
            ],
            [
                InlineKeyboardButton(
                    t["btn_back"],
                    callback_data="back_to_main"
                )
            ]
        ]

        text = t["profile_text"].format(
            user_id=user.id,
            balance=user_data["balance"]
        )

        await query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return

    # ЯЗЫК
    if query.data.startswith("setlang_"):

        lang = query.data.split("_")[1]

        update_user_lang(
            user.id,
            lang
        )

        await query.answer(
            "Язык изменён!"
        )

        return

    # STARS
    if query.data == "shop_stars":

        keyboard = [
            [
                InlineKeyboardButton(
                    "⭐ 50 Stars — 10 500 сум",
                    callback_data="buy_stars_fixed_50"
                )
            ],
            [
                InlineKeyboardButton(
                    "⭐ 100 Stars — 21 000 сум",
                    callback_data="buy_stars_fixed_100"
                )
            ],
            [
                InlineKeyboardButton(
                    t["stars_manual"],
                    callback_data="buy_stars_manual"
                )
            ],
            [
                InlineKeyboardButton(
                    t["btn_back"],
                    callback_data="main_shop"
                )
            ]
        ]

        await query.message.edit_text(
            t["stars_desc"].format(
                price=PRICE_PER_STAR
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return

    # PREMIUM
    if query.data == "shop_premium":

        keyboard = [
            [
                InlineKeyboardButton(
                    "🚀 3 месяца — 165 000 сум",
                    callback_data="buy_prem_fixed_3"
                )
            ],
            [
                InlineKeyboardButton(
                    "🚀 6 месяцев — 222 000 сум",
                    callback_data="buy_prem_fixed_6"
                )
            ],
            [
                InlineKeyboardButton(
                    "🚀 12 месяцев — 406 000 сум",
                    callback_data="buy_prem_fixed_12"
                )
            ],
            [
                InlineKeyboardButton(
                    t["btn_back"],
                    callback_data="main_shop"
                )
            ]
        ]

        await query.message.edit_text(
            t["premium_desc"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return

    # ПОДАРКИ
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
                    t["btn_back"],
                    callback_data="main_shop"
                )
            ]
        )

        await query.message.edit_text(
            t["gifts_desc"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return

    # АККАУНТЫ
    if query.data == "shop_accounts":

        keyboard = [
            [
                InlineKeyboardButton(
                    "🇺🇿 Страна: Узбекистан — 13 000 сум",
                    callback_data="account_uz"
                )
            ],
            [
                InlineKeyboardButton(
                    "🇨🇴 Страна: Колумбия — 6 500 сум",
                    callback_data="account_co"
                )
            ],
            [
                InlineKeyboardButton(
                    "🇬🇧 Страна: Великобритания — 9 000 сум",
                    callback_data="account_uk"
                )
            ],
            [
                InlineKeyboardButton(
                    "🇺🇸 Страна: Америка — 8 000 сум",
                    callback_data="account_us"
                )
            ],
            [
                InlineKeyboardButton(
                    t["btn_back"],
                    callback_data="main_shop"
                )
            ]
        ]

        await query.message.edit_text(
            t["accounts_desc"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return

    # ПОКУПКА АККАУНТА
    if query.data.startswith("account_"):

        country_codes = {
            "account_uz": "Узбекистан",
            "account_co": "Колумбия",
            "account_uk": "Великобритания",
            "account_us": "Америка"
        }

        country = country_codes.get(
            query.data,
            "Неизвестная страна"
        )

        await context.bot.send_message(
            ADMIN_ID,
            (
                "📱 <b>Новый заказ аккаунта</b>\n\n"
                f"🌍 Страна: <b>{country}</b>\n"
                f"👤 Заказал: @{user.username or 'нет username'}\n"
                f"🆔 ID: <code>{user.id}</code>"
            ),
            parse_mode="HTML"
        )

        await query.message.edit_text(
            "✅ Заявка принята!\n\n"
            "Ожидайте выдачу аккаунта.",
            parse_mode="HTML"
        )

        return


# =========================================================
# ПОПОЛНЕНИЕ
# =========================================================

async def refill_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if await is_user_banned(update):
        return ConversationHandler.END

    query = update.callback_query

    await query.answer()

    await query.message.edit_text(
        TEXTS["ru"]["refill_start"],
        parse_mode="HTML"
    )

    return REFILL_AMOUNT


async def refill_amount(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_data = get_user_data(
        update.effective_user.id
    )

    text = update.message.text.replace(
        " ",
        ""
    )

    if not text.isdigit():

        await update.message.reply_text(
            TEXTS["ru"]["refill_bad_num"]
        )

        return REFILL_AMOUNT

    amount = int(text)

    if amount <= 0:

        await update.message.reply_text(
            TEXTS["ru"]["refill_bad_num"]
        )

        return REFILL_AMOUNT

    context.user_data["refill_amount"] = amount

    await update.message.reply_text(
        TEXTS["ru"]["refill_invoice"].format(
            amount=amount,
            card=CARD_NUMBER
        ),
        parse_mode="HTML"
    )

    return REFILL_CHECK


async def refill_check(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if await is_user_banned(update):
        return ConversationHandler.END

    user = update.effective_user

    amount = context.user_data.get(
        "refill_amount",
        0
    )

    if update.message.photo:

        file_id = update.message.photo[-1].file_id

        media_type = "photo"

    elif (
        update.message.document
        and update.message.document.mime_type
        and update.message.document.mime_type.startswith("image/")
    ):

        file_id = update.message.document.file_id

        media_type = "document"

    else:

        await update.message.reply_text(
            TEXTS["ru"]["refill_bad_photo"]
        )

        return REFILL_CHECK

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Одобрить",
                callback_data=f"adm_pay_yes_{user.id}_{amount}"
            ),
            InlineKeyboardButton(
                "❌ Отклонить",
                callback_data=f"adm_pay_no_{user.id}"
            )
        ]
    ]

    caption = (
        "💰 <b>Пополнение баланса</b>\n\n"
        f"👤 Username: @{user.username or 'нет'}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"💵 Сумма: <b>{amount:,} сум</b>"
    )

    if media_type == "photo":

        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=file_id,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    else:

        await context.bot.send_document(
            chat_id=ADMIN_ID,
            document=file_id,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    await update.message.reply_text(
        TEXTS["ru"]["refill_done"]
    )

    context.user_data.clear()

    return ConversationHandler.END


# =========================================================
# ПОКУПКА STARS / PREMIUM
# =========================================================

async def buy_product_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    data = query.data

    user = query.from_user

    user_data = get_user_data(
        user.id,
        user.username,
        user.first_name
    )

    # РУЧНОЙ ВВОД STARS
    if data == "buy_stars_manual":

        context.user_data["buy_type"] = "stars"

        await query.message.edit_text(
            TEXTS["ru"]["buy_stars_enter"],
            parse_mode="HTML"
        )

        return BUY_AMOUNT

    # FIXED STARS
    if data.startswith("buy_stars_fixed_"):

        value = int(
            data.split("_")[-1]
        )

        product_type = "stars"

        price = value * PRICE_PER_STAR

    # FIXED PREMIUM
    elif data.startswith("buy_prem_fixed_"):

        value = int(
            data.split("_")[-1]
        )

        product_type = "premium"

        price = PREMIUM_PRICES[value]

    else:

        return ConversationHandler.END

    if user_data["balance"] < price:

        await query.message.edit_text(
            TEXTS["ru"]["not_enough"].format(
                price=price,
                balance=user_data["balance"]
            )
        )

        return ConversationHandler.END

    context.user_data["buy_type"] = product_type

    context.user_data["buy_value"] = value

    context.user_data["buy_price"] = price

    await query.message.edit_text(
        TEXTS["ru"]["buy_username_enter"],
        parse_mode="HTML"
    )

    return BUY_USERNAME


async def buy_amount(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_data = get_user_data(
        update.effective_user.id
    )

    text = update.message.text.strip()

    if not text.isdigit():

        await update.message.reply_text(
            "❌ Введите число."
        )

        return BUY_AMOUNT

    value = int(text)

    if value < 50 or value > 10000:

        await update.message.reply_text(
            "❌ Можно купить от 50 до 10 000 Stars."
        )

        return BUY_AMOUNT

    price = value * PRICE_PER_STAR

    if user_data["balance"] < price:

        await update.message.reply_text(
            TEXTS["ru"]["not_enough"].format(
                price=price,
                balance=user_data["balance"]
            )
        )

        return ConversationHandler.END

    context.user_data["buy_type"] = "stars"

    context.user_data["buy_value"] = value

    context.user_data["buy_price"] = price

    await update.message.reply_text(
        TEXTS["ru"]["buy_username_enter"],
        parse_mode="HTML"
    )

    return BUY_USERNAME


async def buy_username(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    username = update.message.text.strip()

    username = username.replace(
        "@",
        ""
    )

    if not username:

        await update.message.reply_text(
            "❌ Введите юзернейм."
        )

        return BUY_USERNAME

    if " " in username:

        await update.message.reply_text(
            "❌ Юзернейм не должен содержать пробелы."
        )

        return BUY_USERNAME

    context.user_data["target_username"] = username

    product_type = context.user_data["buy_type"]

    value = context.user_data["buy_value"]

    price = context.user_data["buy_price"]

    if product_type == "stars":

        product = f"{value} Telegram Stars"

    else:

        product = f"Telegram Premium на {value} месяцев"

    text = TEXTS["ru"]["buy_confirm"].format(
        product=product,
        target=username,
        price=price
    )

    keyboard = [
        [
            InlineKeyboardButton(
                TEXTS["ru"]["buy_confirm_btn"],
                callback_data="confirm_final_buy"
            )
        ],
        [
            InlineKeyboardButton(
                TEXTS["ru"]["btn_cancel"],
                callback_data="cancel_buy"
            )
        ]
    ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

    return BUY_CONFIRM


async def buy_confirm(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    if query.data == "cancel_buy":

        await query.message.edit_text(
            "❌ Покупка отменена."
        )

        context.user_data.clear()

        return ConversationHandler.END

    user = query.from_user

    user_data = get_user_data(
        user.id,
        user.username,
        user.first_name
    )

    product_type = context.user_data["buy_type"]

    value = context.user_data["buy_value"]

    price = context.user_data["buy_price"]

    target = context.user_data["target_username"]

    if user_data["balance"] < price:

        await query.message.edit_text(
            TEXTS["ru"]["not_enough"].format(
                price=price,
                balance=user_data["balance"]
            )
        )

        context.user_data.clear()

        return ConversationHandler.END

    if product_type == "stars":

        product = f"{value} Telegram Stars"

    else:

        product = f"Telegram Premium на {value} месяцев"

    await query.message.edit_text(
        "🔄 Обрабатываем заказ..."
    )

    client_order_id = (
        f"{user.id}_{int(time.time() * 1000)}"
    )

    success = await send_order_to_api(
        product_type=product_type,
        value=value,
        username=target,
        client_order_id=client_order_id
    )

    if not success:

        await query.message.edit_text(
            TEXTS["ru"]["api_error"]
        )

        context.user_data.clear()

        return ConversationHandler.END

    update_user_balance(
        user.id,
        -price
    )

    await query.message.edit_text(
        TEXTS["ru"]["order_success"].format(
            product=product,
            target=target
        ),
        parse_mode="HTML"
    )

    await context.bot.send_message(
        ADMIN_ID,
        (
            "🚀 <b>Новый автоматический заказ</b>\n\n"
            f"👤 Username: @{user.username or 'нет'}\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"📦 Товар: {product}\n"
            f"🎯 Получатель: @{target}\n"
            f"💰 Сумма: {price:,} сум"
        ),
        parse_mode="HTML"
    )

    context.user_data.clear()

    return ConversationHandler.END


# =========================================================
# ПОКУПКА ПОДАРКОВ
# =========================================================

async def gift_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if await is_user_banned(update):
        return ConversationHandler.END

    query = update.callback_query

    await query.answer()

    gift_id = int(
        query.data.split("_")[1]
    )

    gift = GIFTS.get(gift_id)

    if not gift:

        return ConversationHandler.END

    user_data = get_user_data(
        query.from_user.id
    )

    if user_data["balance"] < gift["price"]:

        await query.message.edit_text(
            TEXTS["ru"]["not_enough"].format(
                price=gift["price"],
                balance=user_data["balance"]
            )
        )

        return ConversationHandler.END

    context.user_data["gift_id"] = gift_id

    await query.message.edit_text(
        TEXTS["ru"]["gift_username"],
        parse_mode="HTML"
    )

    return GIFT_USERNAME


async def gift_username(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    username = update.message.text.strip()

    username = username.replace(
        "@",
        ""
    )

    if not username:

        await update.message.reply_text(
            "❌ Введите юзернейм."
        )

        return GIFT_USERNAME

    if " " in username:

        await update.message.reply_text(
            "❌ Юзернейм не должен содержать пробелы."
        )

        return GIFT_USERNAME

    user = update.effective_user

    user_data = get_user_data(
        user.id,
        user.username,
        user.first_name
    )

    gift_id = context.user_data["gift_id"]

    gift = GIFTS[gift_id]

    if user_data["balance"] < gift["price"]:

        await update.message.reply_text(
            TEXTS["ru"]["not_enough"].format(
                price=gift["price"],
                balance=user_data["balance"]
            )
        )

        context.user_data.clear()

        return ConversationHandler.END

    update_user_balance(
        user.id,
        -gift["price"]
    )

    gift_text = (
        f"{gift['emoji']} "
        "🎁 <b>Новый заказ подарка</b>\n\n"
        f"👤 Заказал: @{user.username or 'нет'}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"🎯 Получатель: @{username}\n"
        f"💰 Цена: {gift['price']:,} сум\n"
        f"🆔 Custom Emoji ID: <code>{gift['emoji_id']}</code>"
    )

    entities = [
        MessageEntity(
            type="custom_emoji",
            offset=0,
            length=2,
            custom_emoji_id=gift["emoji_id"]
        )
    ]

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=gift_text,
        entities=entities
    )

    await update.message.reply_text(
        TEXTS["ru"]["gift_success"],
        parse_mode="HTML"
    )

    context.user_data.clear()

    return ConversationHandler.END


# =========================================================
# АДМИНКА
# =========================================================

def admin_only(func):

    async def wrapper(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        *args,
        **kwargs
    ):

        if update.effective_user.id != ADMIN_ID:

            if update.callback_query:

                await update.callback_query.answer(
                    "⛔ Только для администратора!",
                    show_alert=True
                )

            return

        return await func(
            update,
            context,
            *args,
            **kwargs
        )

    return wrapper


@admin_only
async def admin_panel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    keyboard = [
        [
            InlineKeyboardButton(
                "👥 Список пользователей",
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
            "Команды:\n\n"
            "/setbal ID СУММА\n"
            "/ban ID\n"
            "/unban ID\n"
            "/msg ID ТЕКСТ"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )


@admin_only
async def admin_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    if query.data == "admin_close":

        await query.message.delete()

        return

    if query.data.startswith("admin_users_"):

        page = int(
            query.data.split("_")[-1]
        )

        users = get_all_users()

        if not users:

            await query.message.edit_text(
                "⚠️ Пользователей пока нет."
            )

            return

        per_page = 10

        start_index = page * per_page

        end_index = start_index + per_page

        page_users = users[
            start_index:end_index
        ]

        total_pages = (
            len(users) + per_page - 1
        ) // per_page

        text = (
            f"👥 <b>Пользователи</b>\n"
            f"📄 Страница {page + 1}/{total_pages}\n"
            f"👤 Всего: {len(users)}\n\n"
        )

        for (
            user_id,
            username,
            name,
            balance,
            is_banned
        ) in page_users:

            username_text = (
                f"@{username}"
                if username
                else "❌ Нет username"
            )

            ban_text = (
                "⛔ Заблокирован"
                if is_banned
                else "🟢 Не заблокирован"
            )

            text += (
                "━━━━━━━━━━━━━━\n"
                f"👤 <b>Username:</b> {username_text}\n"
                f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
                f"💰 <b>Баланс:</b> {balance:,} сум\n"
                f"🚫 <b>Бан:</b> {ban_text}\n"
            )

        keyboard = []

        navigation = []

        if page > 0:

            navigation.append(
                InlineKeyboardButton(
                    "⬅️ Назад",
                    callback_data=f"admin_users_{page - 1}"
                )
            )

        if end_index < len(users):

            navigation.append(
                InlineKeyboardButton(
                    "Вперёд ➡️",
                    callback_data=f"admin_users_{page + 1}"
                )
            )

        if navigation:

            keyboard.append(navigation)

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


@admin_only
async def cmd_setbal(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if len(context.args) < 2:

        await update.message.reply_text(
            "❌ Использование: /setbal ID СУММА"
        )

        return

    user_id = context.args[0]

    amount = context.args[1]

    if not user_id.isdigit():

        await update.message.reply_text(
            "❌ Неверный ID."
        )

        return

    try:

        amount = int(amount)

    except ValueError:

        await update.message.reply_text(
            "❌ Неверная сумма."
        )

        return

    user_id = int(user_id)

    update_user_balance(
        user_id,
        amount
    )

    user_data = get_user_data(
        user_id
    )

    await update.message.reply_text(
        (
            f"✅ Баланс изменён.\n\n"
            f"🆔 ID: {user_id}\n"
            f"💰 Текущий баланс: "
            f"{user_data['balance']:,} сум"
        )
    )


@admin_only
async def cmd_ban(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.args:

        return

    user_id = context.args[0]

    if user_id.isdigit():

        update_user_ban(
            int(user_id),
            True
        )

        await update.message.reply_text(
            "⛔ Пользователь заблокирован."
        )


@admin_only
async def cmd_unban(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.args:

        return

    user_id = context.args[0]

    if user_id.isdigit():

        update_user_ban(
            int(user_id),
            False
        )

        await update.message.reply_text(
            "🟢 Пользователь разблокирован."
        )


@admin_only
async def cmd_msg(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if len(context.args) < 2:

        return

    user_id = context.args[0]

    message = " ".join(
        context.args[1:]
    )

    if not user_id.isdigit():

        return

    try:

        await context.bot.send_message(
            int(user_id),
            message
        )

        await update.message.reply_text(
            "✅ Сообщение отправлено."
        )

    except Exception as e:

        await update.message.reply_text(
            f"❌ Ошибка: {e}"
        )


# =========================================================
# ОДОБРЕНИЕ ПОПОЛНЕНИЯ
# =========================================================

@admin_only
async def admin_payment_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    if query.data.startswith("adm_pay_yes_"):

        parts = query.data.split("_")

        user_id = int(parts[3])

        amount = int(parts[4])

        update_user_balance(
            user_id,
            amount
        )

        await query.message.edit_caption(
            "🟢 Пополнение одобрено."
        )

        try:

            await context.bot.send_message(
                user_id,
                "🎉 Ваш баланс пополнен!"
            )

        except Exception:

            pass

    elif query.data.startswith("adm_pay_no_"):

        await query.message.edit_caption(
            "🔴 Пополнение отклонено."
        )


# =========================================================
# ЗАПУСК
# =========================================================

def main():

    init_db()

    web_thread = threading.Thread(
        target=run_web_server,
        daemon=True
    )

    web_thread.start()

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # ПОПОЛНЕНИЕ
    app.add_handler(
        ConversationHandler(
            entry_points=[
                CallbackQueryHandler(
                    refill_start,
                    pattern="^main_refill$"
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
                        filters.PHOTO | filters.Document.IMAGE,
                        refill_check
                    )
                ]
            },
            fallbacks=[
                CommandHandler(
                    "start",
                    start
                )
            ],
            allow_reentry=True
        )
    )

    # ПОКУПКА STARS / PREMIUM
    app.add_handler(
        ConversationHandler(
            entry_points=[
                CallbackQueryHandler(
                    buy_product_start,
                    pattern=(
                        "^buy_stars_manual$|"
                        "^buy_stars_fixed_[0-9]+$|"
                        "^buy_prem_fixed_[0-9]+$"
                    )
                )
            ],
            states={
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
                        pattern="^confirm_final_buy$|^cancel_buy$"
                    )
                ]
            },
            fallbacks=[
                CommandHandler(
                    "start",
                    start
                )
            ],
            allow_reentry=True
        )
    )

    # ПОДАРКИ
    app.add_handler(
        ConversationHandler(
            entry_points=[
                CallbackQueryHandler(
                    gift_start,
                    pattern="^gift_[0-9]+$"
                )
            ],
            states={
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
                )
            ],
            allow_reentry=True
        )
    )

    # АДМИНКА
    app.add_handler(
        CommandHandler(
            "admin",
            admin_panel
        )
    )

    app.add_handler(
        CommandHandler(
            "setbal",
            cmd_setbal
        )
    )

    app.add_handler(
        CommandHandler(
            "ban",
            cmd_ban
        )
    )

    app.add_handler(
        CommandHandler(
            "unban",
            cmd_unban
        )
    )

    app.add_handler(
        CommandHandler(
            "msg",
            cmd_msg
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            admin_callback,
            pattern="^admin_"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            admin_payment_callback,
            pattern="^adm_pay_"
        )
    )

    # START
    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    # ГЛАВНЫЕ КНОПКИ
    app.add_handler(
        CallbackQueryHandler(
            menu_callback,
            pattern=(
                "^main_shop$|"
                "^main_profile$|"
                "^back_to_main$|"
                "^shop_stars$|"
                "^shop_premium$|"
                "^shop_gifts$|"
                "^shop_accounts$|"
                "^setlang_.*$|"
                "^account_.*$"
            )
        )
    )

    logger.info(
        "BOT STARTED SUCCESSFULLY"
    )

    app.run_polling()


if __name__ == "__main__":

    main()