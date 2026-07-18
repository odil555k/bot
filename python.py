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

CARD_NUMBER = "5614 6835 8985 1641"

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

GIFT_USERNAME = 6


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
    }
}

# =========================================================
# ТЕКСТЫ
# =========================================================

T = {
    "welcome": (
        "👋 Привет, {name}!\n\n"
        "Добро пожаловать в магазин Telegram Stars & Premium.\n\n"
        "💰 Баланс: {balance:,} сум"
    ),

    "shop": "🛍 <b>Выберите услугу:</b>",

    "profile": (
        "👤 <b>Мой профиль</b>\n\n"
        "🆔 ID: <code>{user_id}</code>\n"
        "💰 Баланс: <b>{balance:,} сум</b>"
    ),

    "stars": (
        "💎 <b>Telegram Stars</b>\n\n"
        "💰 Цена: {price} сум за 1 Stars"
    ),

    "premium": (
        "🌟 <b>Telegram Premium</b>\n\n"
        "🔹 3 месяца — 165 000 сум\n"
        "🔹 6 месяцев — 222 000 сум\n"
        "🔹 12 месяцев — 406 000 сум"
    ),

    "gifts": (
        "🎁 <b>Выберите подарок:</b>\n\n"
        "После выбора введите юзернейм получателя."
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

    "confirm": (
        "📝 <b>Подтверждение покупки</b>\n\n"
        "📦 Товар: {product}\n"
        "👤 Получатель: @{username}\n"
        "💰 Стоимость: <b>{price:,} сум</b>\n\n"
        "Подтвердить?"
    ),

    "not_enough": (
        "❌ Недостаточно средств.\n\n"
        "💰 Нужно: {price:,} сум\n"
        "💳 Баланс: {balance:,} сум"
    ),

    "api_error": (
        "❌ Не удалось выполнить заказ.\n\n"
        "Попробуйте ещё раз позже."
    ),

    "success": (
        "✅ <b>Заказ успешно выполнен!</b>\n\n"
        "📦 {product}\n"
        "👤 Получатель: @{username}"
    ),

    "gift_username": (
        "✏️ Введите юзернейм получателя подарка.\n\n"
        "Без символа @"
    ),

    "gift_success": (
        "✅ <b>Заявка на подарок принята!</b>\n\n"
        "Подарок будет отправлен получателю."
    )
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
            is_banned INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


def get_user(user_id, username="", name=""):

    conn = sqlite3.connect(DB_FILE)

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT username, name, balance, is_banned
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
            (user_id, username, name, balance, is_banned)
            VALUES (?, ?, ?, 0, 0)
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
            "is_banned": False
        }

    else:

        old_username, old_name, balance, is_banned = row

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
            "is_banned": bool(is_banned)
        }

    conn.close()

    return result


def change_balance(user_id, amount):

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


def set_ban(user_id, value):

    conn = sqlite3.connect(DB_FILE)

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE users
        SET is_banned = ?
        WHERE user_id = ?
        """,
        (1 if value else 0, user_id)
    )

    conn.commit()
    conn.close()


def get_users():

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

async def check_ban(update: Update):

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

    def log_message(self, format, *args):

        return


def run_web():

    port = int(
        os.environ.get(
            "PORT",
            8080
        )
    )

    server = HTTPServer(
        ("0.0.0.0", port),
        Handler
    )

    server.serve_forever()


# =========================================================
# ELDER API
# =========================================================

async def api_buy(
    product_type,
    value,
    username,
    order_id
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
            "client_order_id": order_id
        }

    else:

        url = f"{ELDER_API_URL}/premium/buy"

        payload = {
            "username": username,
            "months": value,
            "client_order_id": order_id
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

    except Exception as e:

        logger.error(e)

        return False


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
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
                "🛍 Услуги",
                callback_data="main_shop"
            )
        ],
        [
            InlineKeyboardButton(
                "💳 Пополнить баланс",
                callback_data="main_refill"
            ),
            InlineKeyboardButton(
                "👤 Мой профиль",
                callback_data="main_profile"
            )
        ]
    ]

    await update.message.reply_text(
        T["welcome"].format(
            name=user.first_name,
            balance=data["balance"]
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )


# =========================================================
# ОСНОВНЫЕ КНОПКИ
# =========================================================

async def main_buttons(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
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
                    "🛍 Услуги",
                    callback_data="main_shop"
                )
            ],
            [
                InlineKeyboardButton(
                    "💳 Пополнить баланс",
                    callback_data="main_refill"
                ),
                InlineKeyboardButton(
                    "👤 Мой профиль",
                    callback_data="main_profile"
                )
            ]
        ]

        await query.message.edit_text(
            T["welcome"].format(
                name=user.first_name,
                balance=data["balance"]
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
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
                    "⬅️ Назад",
                    callback_data="back_main"
                )
            ]
        ]

        await query.message.edit_text(
            T["shop"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return

    if query.data == "main_profile":

        keyboard = [
            [
                InlineKeyboardButton(
                    "⬅️ Назад",
                    callback_data="back_main"
                )
            ]
        ]

        await query.message.edit_text(
            T["profile"].format(
                user_id=user.id,
                balance=data["balance"]
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return

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
                    "⬅️ Назад",
                    callback_data="main_shop"
                )
            ]
        ]

        await query.message.edit_text(
            T["stars"].format(
                price=PRICE_PER_STAR
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
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
                    "⬅️ Назад",
                    callback_data="main_shop"
                )
            ]
        ]

        await query.message.edit_text(
            T["premium"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return

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
                    "⬅️ Назад",
                    callback_data="main_shop"
                )
            ]
        )

        await query.message.edit_text(
            T["gifts"],
            reply_markup=InlineKeyboardMarkup(keyboard),
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
                    "⬅️ Назад",
                    callback_data="main_shop"
                )
            ]
        ]

        await query.message.edit_text(
            T["accounts"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return

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
                f"👤 Username: @{user.username or 'нет'}\n"
                f"🆔 ID: {user.id}"
            )
        )

        await query.message.edit_text(
            "✅ Заявка принята!"
        )


# =========================================================
# ПОПОЛНЕНИЕ
# =========================================================

async def refill_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    context.user_data.clear()

    await query.message.edit_text(
        "💳 Введите сумму пополнения в сумах.\n\n"
        "Например: 50000"
    )

    return REFILL_AMOUNT


async def refill_amount(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
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
        (
            "💳 Пополнение баланса\n\n"
            f"💰 Сумма: {amount:,} сум\n\n"
            f"Переведите сумму на карту:\n"
            f"{CARD_NUMBER}\n\n"
            "После оплаты отправьте чек."
        )
    )

    return REFILL_CHECK


async def refill_check(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
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
                f"👤 Username: @{user.username or 'нет'}\n"
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
            "❌ Отправьте фото чека."
        )

        return REFILL_CHECK

    await update.message.reply_text(
        "⏳ Чек отправлен администратору."
    )

    context.user_data.clear()

    return ConversationHandler.END


# =========================================================
# ПОКУПКА STARS / PREMIUM
# =========================================================

async def buy_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    context.user_data.clear()

    data = query.data

    if data == "buy_stars_manual":

        context.user_data["buy_type"] = "stars"

        await query.message.edit_text(
            T["enter_stars"]
        )

        return BUY_AMOUNT

    if data.startswith("buy_stars_"):

        value = int(
            data.split("_")[-1]
        )

        context.user_data["buy_type"] = "stars"
        context.user_data["buy_value"] = value
        context.user_data["buy_price"] = value * PRICE_PER_STAR

    elif data.startswith("buy_premium_"):

        value = int(
            data.split("_")[-1]
        )

        context.user_data["buy_type"] = "premium"
        context.user_data["buy_value"] = value
        context.user_data["buy_price"] = PREMIUM_PRICES[value]

    await query.message.edit_text(
        T["enter_username"]
    )

    return BUY_USERNAME


async def buy_amount(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
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
            "❌ Минимум 50 Stars."
        )

        return BUY_AMOUNT

    context.user_data["buy_type"] = "stars"
    context.user_data["buy_value"] = value
    context.user_data["buy_price"] = value * PRICE_PER_STAR

    await update.message.reply_text(
        T["enter_username"]
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
        T["confirm"].format(
            product=product,
            username=username,
            price=price
        ),
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

        context.user_data.clear()

        await query.message.edit_text(
            "❌ Покупка отменена."
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
            T["not_enough"].format(
                price=price,
                balance=data["balance"]
            )
        )

        context.user_data.clear()

        return ConversationHandler.END

    await query.message.edit_text(
        "🔄 Обрабатываем заказ..."
    )

    order_id = (
        f"{user.id}_{int(time.time() * 1000)}"
    )

    success = await api_buy(
        product_type,
        value,
        target,
        order_id
    )

    if not success:

        await query.message.edit_text(
            T["api_error"]
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
        T["success"].format(
            product=product,
            username=target
        ),
        parse_mode="HTML"
    )

    await context.bot.send_message(
        ADMIN_ID,
        (
            "🚀 Новый заказ\n\n"
            f"👤 Username: @{user.username or 'нет'}\n"
            f"🆔 ID: {user.id}\n"
            f"📦 Товар: {product}\n"
            f"🎯 Получатель: @{target}\n"
            f"💰 Сумма: {price:,} сум"
        )
    )

    context.user_data.clear()

    return ConversationHandler.END


# =========================================================
# ПОДАРКИ
# =========================================================

async def gift_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
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
            T["not_enough"].format(
                price=gift["price"],
                balance=data["balance"]
            )
        )

        return ConversationHandler.END

    context.user_data["gift_id"] = gift_id

    await query.message.edit_text(
        T["gift_username"]
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
            "❌ Введите корректный юзернейм."
        )

        return GIFT_USERNAME

    if " " in username:

        await update.message.reply_text(
            "❌ Юзернейм не должен содержать пробелы."
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
            T["not_enough"].format(
                price=gift["price"],
                balance=data["balance"]
            )
        )

        context.user_data.clear()

        return ConversationHandler.END

    change_balance(
        user.id,
        -gift["price"]
    )

    # ============================================
    # НАСТОЯЩИЙ CUSTOM EMOJI БЕЗ HTML
    # ============================================

    emoji = gift["emoji"]

    text = (
        f"{emoji} 🎁 Новый заказ подарка\n\n"
        f"🎁 Подарок: {gift['name']}\n"
        f"👤 Заказал: @{user.username or 'нет'}\n"
        f"🆔 ID: {user.id}\n"
        f"🎯 Получатель: @{username}\n"
        f"💰 Цена: {gift['price']:,} сум\n"
        f"🆔 Emoji ID: {gift['emoji_id']}"
    )

    entities = [
        MessageEntity(
            type="custom_emoji",
            offset=0,
            length=len(emoji.encode("utf-16-le")) // 2,
            custom_emoji_id=gift["emoji_id"]
        )
    ]

    await context.bot.send_message(
        ADMIN_ID,
        text,
        entities=entities
    )

    await update.message.reply_text(
        T["gift_success"],
        parse_mode="HTML"
    )

    context.user_data.clear()

    return ConversationHandler.END


# =========================================================
# АДМИН-ПАНЕЛЬ
# =========================================================

async def admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
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
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
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

        start = page * per_page

        end = start + per_page

        page_users = users[start:end]

        total_pages = max(
            1,
            (len(users) + per_page - 1) // per_page
        )

        text = (
            f"👥 Пользователи\n"
            f"📄 Страница {page + 1}/{total_pages}\n\n"
        )

        for (
            user_id,
            username,
            name,
            balance,
            banned
        ) in page_users:

            username_text = (
                f"@{username}"
                if username
                else "❌ Нет username"
            )

            ban_text = (
                "⛔ БАН"
                if banned
                else "🟢 Активен"
            )

            text += (
                "━━━━━━━━━━━━━━\n"
                f"👤 {username_text}\n"
                f"🆔 ID: {user_id}\n"
                f"💰 {balance:,} сум\n"
                f"🚫 {ban_text}\n"
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

        if end < len(users):

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
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def setbal(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
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
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
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
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
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
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
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
        "✅ Отправлено."
    )


# =========================================================
# ОПЛАТЫ
# =========================================================

async def payment_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
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

    logger.info("BOT STARTED")

    app.run_polling()


if __name__ == "__main__":

    main()