import asyncio
import html
import logging
import os
import sqlite3
import threading
from functools import wraps
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
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
# НАСТРОЙКИ
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])

ELDER_API_KEY = os.environ["ELDER_API_KEY"]
ELDER_API_URL = "https://asosiy.elder.uz/api"

CARD_NUMBER = "5614 6835 8985 1641"

DB_FILE = "bot_database.db"

PRICE_PER_STAR = 210

PREMIUM_PRICES = {
    3: 165000,
    6: 222000,
    12: 406000,
}

# =========================================================
# СОСТОЯНИЯ
# =========================================================

REFILL_AMOUNT, REFILL_CHECK = range(2)
BUY_USERNAME, BUY_CONFIRM = range(2, 4)
GIFT_USERNAME, GIFT_CONFIRM = range(4, 6)

# =========================================================
# ПОДАРКИ
# =========================================================

GIFTS = {
    "1": {
        "emoji": "🧸",
        "emoji_id": "5280598054901145762",
        "price": 3500,
    },
    "2": {
        "emoji": "💝",
        "emoji_id": "5283228279988309088",
        "price": 3500,
    },
    "3": {
        "emoji": "🎁",
        "emoji_id": "5280615440928758599",
        "price": 5000,
    },
    "4": {
        "emoji": "🌹",
        "emoji_id": "5280947338821524402",
        "price": 5000,
    },
    "5": {
        "emoji": "🎂",
        "emoji_id": "5280659198055572187",
        "price": 10000,
    },
    "6": {
        "emoji": "💐",
        "emoji_id": "5280774333243873175",
        "price": 10000,
    },
    "7": {
        "emoji": "🚀",
        "emoji_id": "5283080528818360566",
        "price": 10000,
    },
    "8": {
        "emoji": "🏆",
        "emoji_id": "5280769763398671636",
        "price": 20500,
    },
    "9": {
        "emoji": "💍",
        "emoji_id": "5280651583078556009",
        "price": 20500,
    },
    "10": {
        "emoji": "💎",
        "emoji_id": "5280922999241859582",
        "price": 20500,
    },
    "11": {
        "emoji": "🍾",
        "emoji_id": "5451905784734574339",
        "price": 10000,
    },
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
        "shop": "🛍 <b>Выберите категорию:</b>",
        "stars": "💎 <b>Telegram Stars</b>\n\n💵 Цена: {price} сум за 1 Stars.",
        "premium": (
            "🌟 <b>Telegram Premium</b>\n\n"
            "Выберите срок подписки:"
        ),
        "gifts": "🎁 <b>Выберите подарок:</b>\n\nНажмите на нужный подарок:",
        "profile": (
            "👤 <b>Мой профиль</b>\n\n"
            "🆔 ID: <code>{user_id}</code>\n"
            "💰 Баланс: <b>{balance:,} сум</b>\n\n"
            "🌐 Выберите язык:"
        ),
        "refill_amount": (
            "💳 Введите сумму пополнения в сумах.\n\n"
            "Например: <code>50000</code>"
        ),
        "bad_number": "❌ Введите корректное число.",
        "refill_invoice": (
            "💳 <b>Пополнение баланса</b>\n\n"
            "💰 Сумма: <b>{amount:,} сум</b>\n\n"
            "Переведите ровно эту сумму на карту:\n"
            "<code>{card}</code>\n\n"
            "После оплаты отправьте сюда фото или скриншот чека."
        ),
        "bad_check": "❌ Отправьте именно фото или скриншот чека.",
        "check_sent": "⏳ Чек отправлен администратору на проверку.",
        "username": (
            "👤 Введите Telegram username получателя.\n\n"
            "Без символа <code>@</code>\n"
            "Например: <code>durov</code>"
        ),
        "bad_balance": (
            "❌ Недостаточно средств.\n\n"
            "💰 Нужно: {price:,} сум\n"
            "💳 Ваш баланс: {balance:,} сум"
        ),
        "confirm": (
            "📝 <b>Подтверждение заказа</b>\n\n"
            "📦 Товар: {product}\n"
            "👤 Получатель: @{username}\n"
            "💰 Стоимость: <b>{price:,} сум</b>\n\n"
            "Подтвердить покупку?"
        ),
        "success": "✅ Заказ успешно оформлен!",
        "api_error": "❌ Не удалось оформить заказ. Попробуйте позже.",
        "banned": "❌ Вы заблокированы в этом боте.",
    },
    "uz": {
        "welcome": (
            "👋 Salom, {name}!\n\n"
            "Telegram Stars & Premium do'koniga xush kelibsiz.\n\n"
            "💰 Balansingiz: {balance:,} so'm"
        ),
        "shop": "🛍 <b>Kategoriyani tanlang:</b>",
        "stars": "💎 <b>Telegram Stars</b>\n\n💵 Narx: 1 Stars — {price} so'm.",
        "premium": (
            "🌟 <b>Telegram Premium</b>\n\n"
            "Obuna muddatini tanlang:"
        ),
        "gifts": "🎁 <b>Sovg'ani tanlang:</b>",
        "profile": (
            "👤 <b>Mening profilim</b>\n\n"
            "🆔 ID: <code>{user_id}</code>\n"
            "💰 Balans: <b>{balance:,} so'm</b>\n\n"
            "🌐 Tilni tanlang:"
        ),
        "refill_amount": (
            "💳 Balansni to'ldirish summasini kiriting.\n\n"
            "Masalan: <code>50000</code>"
        ),
        "bad_number": "❌ To'g'ri son kiriting.",
        "refill_invoice": (
            "💳 <b>Balansni to'ldirish</b>\n\n"
            "💰 Summa: <b>{amount:,} so'm</b>\n\n"
            "Ushbu summani kartaga o'tkazing:\n"
            "<code>{card}</code>\n\n"
            "To'lovdan so'ng chek rasmini yuboring."
        ),
        "bad_check": "❌ Chek rasmini yuboring.",
        "check_sent": "⏳ Chek administratorga yuborildi.",
        "username": (
            "👤 Qabul qiluvchining Telegram username'ini kiriting.\n\n"
            "<code>@</code> belgisiz.\n"
            "Masalan: <code>durov</code>"
        ),
        "bad_balance": (
            "❌ Mablag' yetarli emas.\n\n"
            "💰 Kerak: {price:,} so'm\n"
            "💳 Balansingiz: {balance:,} so'm"
        ),
        "confirm": (
            "📝 <b>Buyurtmani tasdiqlash</b>\n\n"
            "📦 Mahsulot: {product}\n"
            "👤 Qabul qiluvchi: @{username}\n"
            "💰 Narxi: <b>{price:,} so'm</b>\n\n"
            "Xaridni tasdiqlaysizmi?"
        ),
        "success": "✅ Buyurtma muvaffaqiyatli rasmiylashtirildi!",
        "api_error": "❌ Buyurtmani rasmiylashtirib bo'lmadi.",
        "banned": "❌ Siz ushbu botda bloklangansiz.",
    },
}

# =========================================================
# БАЗА ДАННЫХ
# =========================================================

def db():
    return sqlite3.connect(DB_FILE, check_same_thread=False)


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
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


def get_user(user_id, username="", name=""):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT balance, username, name, lang, is_banned "
        "FROM users WHERE user_id = ?",
        (user_id,),
    )

    row = cur.fetchone()

    if row is None:
        cur.execute(
            """
            INSERT INTO users
            (user_id, username, name, balance, lang, is_banned)
            VALUES (?, ?, ?, 0, 'ru', 0)
            """,
            (user_id, username or "", name or ""),
        )
        conn.commit()

        result = {
            "balance": 0,
            "username": username or "",
            "name": name or "",
            "lang": "ru",
            "is_banned": False,
        }
    else:
        result = {
            "balance": row[0],
            "username": row[1],
            "name": row[2],
            "lang": row[3],
            "is_banned": bool(row[4]),
        }

    conn.close()
    return result


def update_balance(user_id, amount):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (amount, user_id),
    )

    conn.commit()
    conn.close()


def set_lang(user_id, lang):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "UPDATE users SET lang = ? WHERE user_id = ?",
        (lang, user_id),
    )

    conn.commit()
    conn.close()


def set_ban(user_id, status):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "UPDATE users SET is_banned = ? WHERE user_id = ?",
        (1 if status else 0, user_id),
    )

    conn.commit()
    conn.close()


def get_all_users():
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT user_id, username, name, balance, is_banned FROM users"
    )

    rows = cur.fetchall()
    conn.close()

    return rows


# =========================================================
# ПРОВЕРКА БАНА
# =========================================================

async def is_banned(update: Update):
    user = update.effective_user

    if not user:
        return False

    data = get_user(user.id)

    if not data["is_banned"]:
        return False

    lang = data["lang"]
    text = TEXTS[lang]["banned"]

    if update.message:
        await update.message.reply_text(text)

    elif update.callback_query:
        await update.callback_query.answer(
            text,
            show_alert=True,
        )

    return True


# =========================================================
# ADMIN DECORATOR
# =========================================================

def admin_only(func):
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        if update.effective_user.id != ADMIN_ID:
            if update.callback_query:
                await update.callback_query.answer(
                    "⛔ Доступ запрещён!",
                    show_alert=True,
                )
            return

        return await func(update, context, *args, **kwargs)

    return wrapper


# =========================================================
# WEB SERVER ДЛЯ RENDER
# =========================================================

class WebHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
        return


def run_web_server():
    port = int(os.environ.get("PORT", 8080))

    server = HTTPServer(
        ("0.0.0.0", port),
        WebHandler,
    )

    logger.info(f"Web server started on port {port}")
    server.serve_forever()


# =========================================================
# ELDER API
# =========================================================

async def send_order_to_api(prod_type, value, username):
    username = username.replace("@", "").strip()

    headers = {
        "X-Api-Key": ELDER_API_KEY,
        "Content-Type": "application/json",
    }

    if prod_type == "stars":
        url = f"{ELDER_API_URL}/stars/buy"
        payload = {
            "username": username,
            "amount": value,
        }

    else:
        url = f"{ELDER_API_URL}/premium/buy"
        payload = {
            "username": username,
            "months": value,
        }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
                timeout=30,
            )

        data = response.json()

        if response.status_code == 200 and data.get("success") is True:
            return True

        logger.error(
            "API error: status=%s data=%s",
            response.status_code,
            data,
        )

    except Exception as e:
        logger.error("API request error: %s", e)

    return False


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_banned(update):
        return ConversationHandler.END

    context.user_data.clear()

    user = update.effective_user

    data = get_user(
        user.id,
        user.username,
        user.first_name,
    )

    lang = data["lang"]
    t = TEXTS[lang]

    keyboard = [
        [
            InlineKeyboardButton(
                "🛍 Услуги" if lang == "ru" else "🛍 Xizmatlar",
                callback_data="main_shop",
            )
        ],
        [
            InlineKeyboardButton(
                "💳 Пополнить баланс"
                if lang == "ru"
                else "💳 Balansni to'ldirish",
                callback_data="main_refill",
            ),
            InlineKeyboardButton(
                "👤 Мой профиль"
                if lang == "ru"
                else "👤 Profilim",
                callback_data="main_profile",
            ),
        ],
    ]

    text = t["welcome"].format(
        name=html.escape(user.first_name),
        balance=data["balance"],
    )

    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )

    return ConversationHandler.END


# =========================================================
# ГЛАВНОЕ МЕНЮ
# =========================================================

async def main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_banned(update):
        return

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = get_user(user_id)
    lang = data["lang"]
    t = TEXTS[lang]

    # НАЗАД
    if query.data == "back_main":
        keyboard = [
            [
                InlineKeyboardButton(
                    "🛍 Услуги" if lang == "ru" else "🛍 Xizmatlar",
                    callback_data="main_shop",
                )
            ],
            [
                InlineKeyboardButton(
                    "💳 Пополнить баланс"
                    if lang == "ru"
                    else "💳 Balansni to'ldirish",
                    callback_data="main_refill",
                ),
                InlineKeyboardButton(
                    "👤 Мой профиль"
                    if lang == "ru"
                    else "👤 Profilim",
                    callback_data="main_profile",
                ),
            ],
        ]

        text = t["welcome"].format(
            name=html.escape(query.from_user.first_name),
            balance=data["balance"],
        )

        await query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )

    # УСЛУГИ
    elif query.data == "main_shop":
        keyboard = [
            [
                InlineKeyboardButton(
                    "💎 Telegram Stars",
                    callback_data="shop_stars",
                )
            ],
            [
                InlineKeyboardButton(
                    "🌟 Telegram Premium",
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
                    "📱 Telegram аккаунты",
                    callback_data="shop_accounts",
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ Назад",
                    callback_data="back_main",
                )
            ],
        ]

        await query.message.edit_text(
            t["shop"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )

    # STARS
    elif query.data == "shop_stars":
        keyboard = [
            [
                InlineKeyboardButton(
                    "⭐ 50 — 10 500 сум",
                    callback_data="buy_stars_50",
                )
            ],
            [
                InlineKeyboardButton(
                    "⭐ 100 — 21 000 сум",
                    callback_data="buy_stars_100",
                )
            ],
            [
                InlineKeyboardButton(
                    "✏️ Ввести количество",
                    callback_data="buy_stars_manual",
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ Назад",
                    callback_data="main_shop",
                )
            ],
        ]

        await query.message.edit_text(
            t["stars"].format(price=PRICE_PER_STAR),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )

    # PREMIUM
    elif query.data == "shop_premium":
        keyboard = [
            [
                InlineKeyboardButton(
                    "🚀 3 месяца — 165 000 сум",
                    callback_data="buy_premium_3",
                )
            ],
            [
                InlineKeyboardButton(
                    "🚀 6 месяцев — 222 000 сум",
                    callback_data="buy_premium_6",
                )
            ],
            [
                InlineKeyboardButton(
                    "🚀 12 месяцев — 406 000 сум",
                    callback_data="buy_premium_12",
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ Назад",
                    callback_data="main_shop",
                )
            ],
        ]

        await query.message.edit_text(
            t["premium"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )

    # ПОДАРКИ
    elif query.data == "shop_gifts":
        keyboard = []

        for gift_id, gift in GIFTS.items():
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{gift['emoji']} — {gift['price']:,} сум",
                        callback_data=f"gift_{gift_id}",
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "⬅️ Назад",
                    callback_data="main_shop",
                )
            ]
        )

        await query.message.edit_text(
            t["gifts"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )

    # ПРОФИЛЬ
    elif query.data == "main_profile":
        keyboard = [
            [
                InlineKeyboardButton(
                    "🇺🇿 O'zbekcha",
                    callback_data="lang_uz",
                ),
                InlineKeyboardButton(
                    "🇷🇺 Русский",
                    callback_data="lang_ru",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⬅️ Назад",
                    callback_data="back_main",
                )
            ],
        ]

        text = t["profile"].format(
            user_id=user_id,
            balance=data["balance"],
        )

        await query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )

    # ЯЗЫК
    elif query.data.startswith("lang_"):
        new_lang = query.data.split("_")[1]

        set_lang(user_id, new_lang)

        data = get_user(user_id)
        t = TEXTS[new_lang]

        keyboard = [
            [
                InlineKeyboardButton(
                    "🇺🇿 O'zbekcha",
                    callback_data="lang_uz",
                ),
                InlineKeyboardButton(
                    "🇷🇺 Русский",
                    callback_data="lang_ru",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⬅️ Назад",
                    callback_data="back_main",
                )
            ],
        ]

        text = t["profile"].format(
            user_id=user_id,
            balance=data["balance"],
        )

        await query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )

    # АККАУНТЫ
    elif query.data == "shop_accounts":
        keyboard = [
            [
                InlineKeyboardButton(
                    "🇺🇿 Узбекистан — 13 000 сум",
                    callback_data="account_uz_13000",
                )
            ],
            [
                InlineKeyboardButton(
                    "🇨🇴 Колумбия — 6 500 сум",
                    callback_data="account_co_6500",
                )
            ],
            [
                InlineKeyboardButton(
                    "🇬🇧 Великобритания — 9 000 сум",
                    callback_data="account_uk_9000",
                )
            ],
            [
                InlineKeyboardButton(
                    "🇺🇸 Америка — 8 000 сум",
                    callback_data="account_us_8000",
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ Назад",
                    callback_data="main_shop",
                )
            ],
        ]

        await query.message.edit_text(
            "📱 <b>Выберите страну аккаунта:</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )

    # АККАУНТ
    elif query.data.startswith("account_"):
        parts = query.data.split("_")

        country_code = parts[1]
        price = int(parts[2])

        countries = {
            "uz": "Узбекистан",
            "co": "Колумбия",
            "uk": "Великобритания",
            "us": "Америка",
        }

        country = countries.get(
            country_code,
            country_code.upper(),
        )

        if data["balance"] < price:
            await query.answer(
                "❌ Недостаточно средств!",
                show_alert=True,
            )
            return

        update_balance(user_id, -price)

        await context.bot.send_message(
            ADMIN_ID,
            (
                "📱 <b>Новый заказ аккаунта</b>\n\n"
                f"🌍 <b>Страна:</b> {country}\n"
                f"💰 <b>Цена:</b> {price:,} сум\n"
                f"👤 <b>Покупатель:</b> "
                f"@{html.escape(query.from_user.username or 'без username')}\n"
                f"🆔 <b>ID:</b> <code>{user_id}</code>"
            ),
            parse_mode="HTML",
        )

        await query.message.edit_text(
            "✅ <b>Заказ принят!</b>\n\n"
            "📩 Ожидайте отправку данных.",
            parse_mode="HTML",
        )


# =========================================================
# ПОПОЛНЕНИЕ
# =========================================================

async def refill_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = get_user(query.from_user.id)
    t = TEXTS[data["lang"]]

    await query.message.edit_text(t["refill_amount"])

    return REFILL_AMOUNT


async def refill_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_user(update.effective_user.id)
    t = TEXTS[data["lang"]]

    text = update.message.text.replace(" ", "")

    if not text.isdigit():
        await update.message.reply_text(t["bad_number"])
        return REFILL_AMOUNT

    amount = int(text)

    if amount <= 0:
        await update.message.reply_text(t["bad_number"])
        return REFILL_AMOUNT

    context.user_data["refill_amount"] = amount

    await update.message.reply_text(
        t["refill_invoice"].format(
            amount=amount,
            card=CARD_NUMBER,
        ),
        parse_mode="HTML",
    )

    return REFILL_CHECK


async def refill_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        data = get_user(update.effective_user.id)
        t = TEXTS[data["lang"]]

        await update.message.reply_text(t["bad_check"])
        return REFILL_CHECK

    user = update.effective_user
    amount = context.user_data["refill_amount"]

    photo_id = update.message.photo[-1].file_id

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Одобрить",
                callback_data=f"pay_yes_{user.id}_{amount}",
            ),
            InlineKeyboardButton(
                "❌ Отклонить",
                callback_data=f"pay_no_{user.id}",
            ),
        ]
    ]

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo_id,
        caption=(
            "💳 <b>Пополнение баланса</b>\n\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"👤 @{html.escape(user.username or 'без username')}\n"
            f"💰 Сумма: <b>{amount:,} сум</b>"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )

    data = get_user(user.id)
    t = TEXTS[data["lang"]]

    await update.message.reply_text(t["check_sent"])

    return ConversationHandler.END


# =========================================================
# ПОКУПКА STARS / PREMIUM
# =========================================================

async def buy_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = get_user(query.from_user.id)
    t = TEXTS[data["lang"]]

    callback = query.data

    if callback == "buy_stars_manual":
        context.user_data["buy_type"] = "stars"

        await query.message.edit_text(
            "✏️ Введите количество Stars:"
        )

        return BUY_USERNAME

    if callback.startswith("buy_stars_"):
        amount = int(callback.split("_")[2])

        context.user_data["buy_type"] = "stars"
        context.user_data["buy_value"] = amount
        context.user_data["buy_price"] = amount * PRICE_PER_STAR

    elif callback.startswith("buy_premium_"):
        months = int(callback.split("_")[2])

        context.user_data["buy_type"] = "premium"
        context.user_data["buy_value"] = months
        context.user_data["buy_price"] = PREMIUM_PRICES[months]

    await query.message.edit_text(t["username"])

    return BUY_CONFIRM


async def buy_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_user(update.effective_user.id)
    t = TEXTS[data["lang"]]

    username = update.message.text.strip().replace("@", "")

    if not username:
        await update.message.reply_text(t["username"])
        return BUY_CONFIRM

    if context.user_data.get("buy_type") == "stars":
        if "buy_value" not in context.user_data:
            if not username.isdigit():
                await update.message.reply_text(
                    "❌ Введите количество Stars числом."
                )
                return BUY_USERNAME

            amount = int(username)

            if amount < 50 or amount > 10000:
                await update.message.reply_text(
                    "❌ Количество Stars должно быть от 50 до 10000."
                )
                return BUY_USERNAME

            context.user_data["buy_value"] = amount
            context.user_data["buy_price"] = amount * PRICE_PER_STAR

            await update.message.reply_text(t["username"])
            return BUY_CONFIRM

    price = context.user_data["buy_price"]

    if data["balance"] < price:
        await update.message.reply_text(
            t["bad_balance"].format(
                price=price,
                balance=data["balance"],
            )
        )

        return ConversationHandler.END

    context.user_data["target"] = username

    if context.user_data["buy_type"] == "stars":
        product = f"{context.user_data['buy_value']} Stars"

    else:
        product = f"Premium {context.user_data['buy_value']} месяцев"

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Да, купить",
                callback_data="buy_confirm",
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Отмена",
                callback_data="buy_cancel",
            )
        ],
    ]

    await update.message.reply_text(
        t["confirm"].format(
            product=product,
            username=html.escape(username),
            price=price,
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )

    return BUY_CONFIRM


async def buy_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "buy_cancel":
        await query.message.edit_text("❌ Покупка отменена.")
        context.user_data.clear()
        return ConversationHandler.END

    data = get_user(query.from_user.id)
    t = TEXTS[data["lang"]]

    prod_type = context.user_data["buy_type"]
    value = context.user_data["buy_value"]
    price = context.user_data["buy_price"]
    target = context.user_data["target"]

    if data["balance"] < price:
        await query.message.edit_text(
            t["bad_balance"].format(
                price=price,
                balance=data["balance"],
            )
        )

        return ConversationHandler.END

    await query.message.edit_text("🔄 Обработка заказа...")

    success = await send_order_to_api(
        prod_type,
        value,
        target,
    )

    if not success:
        await query.message.edit_text(
            t["api_error"]
        )

        context.user_data.clear()
        return ConversationHandler.END

    update_balance(
        query.from_user.id,
        -price,
    )

    await query.message.edit_text(
        t["success"]
    )

    await context.bot.send_message(
        ADMIN_ID,
        (
            "🚀 <b>Новый автоматический заказ</b>\n\n"
            f"📦 Товар: {value} "
            f"{'Stars' if prod_type == 'stars' else 'месяцев Premium'}\n"
            f"👤 Получатель: @{html.escape(target)}\n"
            f"🆔 Покупатель ID: <code>{query.from_user.id}</code>\n"
            f"💰 Сумма: {price:,} сум"
        ),
        parse_mode="HTML",
    )

    context.user_data.clear()

    return ConversationHandler.END


# =========================================================
# ПОКУПКА ПОДАРКОВ
# =========================================================

async def gift_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    gift_id = query.data.split("_")[1]
    gift = GIFTS[gift_id]

    data = get_user(query.from_user.id)
    t = TEXTS[data["lang"]]

    if data["balance"] < gift["price"]:
        await query.answer(
            t["bad_balance"].format(
                price=gift["price"],
                balance=data["balance"],
            ),
            show_alert=True,
        )

        return ConversationHandler.END

    context.user_data["gift_id"] = gift_id
    context.user_data["gift_price"] = gift["price"]

    await query.message.edit_text(
        t["username"]
    )

    return GIFT_USERNAME


async def gift_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_user(update.effective_user.id)
    t = TEXTS[data["lang"]]

    username = update.message.text.strip().replace("@", "")

    if not username:
        await update.message.reply_text(t["username"])
        return GIFT_USERNAME

    gift = GIFTS[context.user_data["gift_id"]]

    if data["balance"] < gift["price"]:
        await update.message.reply_text(
            t["bad_balance"].format(
                price=gift["price"],
                balance=data["balance"],
            )
        )

        return ConversationHandler.END

    context.user_data["gift_username"] = username

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Да, заказать",
                callback_data="gift_confirm",
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Отмена",
                callback_data="gift_cancel",
            )
        ],
    ]

    await update.message.reply_text(
        (
            "📝 <b>Подтверждение заказа</b>\n\n"
            f"🎁 Подарок: {gift['emoji']}\n"
            f"👤 Получатель: @{html.escape(username)}\n"
            f"💰 Стоимость: <b>{gift['price']:,} сум</b>\n\n"
            "Подтвердить заказ?"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )

    return GIFT_CONFIRM


async def gift_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "gift_cancel":
        await query.message.edit_text("❌ Заказ отменён.")
        context.user_data.clear()
        return ConversationHandler.END

    data = get_user(query.from_user.id)

    gift = GIFTS[context.user_data["gift_id"]]
    username = context.user_data["gift_username"]

    if data["balance"] < gift["price"]:
        await query.message.edit_text(
            "❌ Недостаточно средств."
        )

        return ConversationHandler.END

    update_balance(
        query.from_user.id,
        -gift["price"],
    )

    emoji_html = (
        f'<tg-emoji emoji-id="{gift["emoji_id"]}">'
        f'{gift["emoji"]}'
        f'</tg-emoji>'
    )

    await context.bot.send_message(
        ADMIN_ID,
        (
            "🎁 <b>Новый заказ подарка</b>\n\n"
            f"🎁 Подарок: {emoji_html}\n"
            f"👤 <b>Кому отправить:</b> @{html.escape(username)}\n"
            f"💰 Цена: <b>{gift['price']:,} сум</b>\n\n"
            f"👤 Покупатель: "
            f"@{html.escape(query.from_user.username or 'без username')}\n"
            f"🆔 ID: <code>{query.from_user.id}</code>"
        ),
        parse_mode="HTML",
    )

    await query.message.edit_text(
        "✅ <b>Заказ подарка принят!</b>\n\n"
        "📩 Ожидайте отправку.",
        parse_mode="HTML",
    )

    context.user_data.clear()

    return ConversationHandler.END


# =========================================================
# АДМИНКА
# =========================================================

@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(
                "👥 Пользователи",
                callback_data="admin_users",
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Закрыть",
                callback_data="admin_close",
            )
        ],
    ]

    await update.message.reply_text(
        (
            "🛠 <b>Панель администратора</b>\n\n"
            "/setbal ID сумма — изменить баланс\n"
            "/ban ID — заблокировать\n"
            "/unban ID — разблокировать\n"
            "/msg ID текст — сообщение"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


@admin_only
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "admin_close":
        await query.message.delete()
        return

    if query.data == "admin_users":
        users = get_all_users()

        text = (
            f"👥 <b>Пользователи: {len(users)}</b>\n\n"
        )

        for user_id, username, name, balance, banned in users[:30]:
            text += (
                f"🆔 <code>{user_id}</code>\n"
                f"👤 @{html.escape(username or 'нет')}\n"
                f"💰 {balance:,} сум\n"
                f"{'⛔ Заблокирован' if banned else '🟢 Активен'}\n"
                "────────────\n"
            )

        await query.message.edit_text(
            text,
            parse_mode="HTML",
        )


@admin_only
async def admin_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")

    if parts[1] == "yes":
        user_id = int(parts[2])
        amount = int(parts[3])

        update_balance(user_id, amount)

        await query.message.edit_caption(
            "🟢 Пополнение одобрено!"
        )

        try:
            await context.bot.send_message(
                user_id,
                f"🎉 Баланс пополнен на {amount:,} сум!",
            )
        except Exception:
            pass

    elif parts[1] == "no":
        user_id = int(parts[2])

        await query.message.edit_caption(
            "🔴 Пополнение отклонено."
        )

        try:
            await context.bot.send_message(
                user_id,
                "❌ Пополнение отклонено.",
            )
        except Exception:
            pass


@admin_only
async def cmd_setbal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "Формат: /setbal ID сумма"
        )
        return

    user_id = int(context.args[0])
    amount = int(context.args[1])

    update_balance(user_id, amount)

    data = get_user(user_id)

    await update.message.reply_text(
        f"✅ Баланс изменён.\n"
        f"💰 Сейчас: {data['balance']:,} сум"
    )


@admin_only
async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return

    user_id = int(context.args[0])

    set_ban(user_id, True)

    await update.message.reply_text(
        "⛔ Пользователь заблокирован."
    )


@admin_only
async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return

    user_id = int(context.args[0])

    set_ban(user_id, False)

    await update.message.reply_text(
        "🟢 Пользователь разблокирован."
    )


@admin_only
async def cmd_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        return

    user_id = int(context.args[0])
    text = " ".join(context.args[1:])

    try:
        await context.bot.send_message(
            user_id,
            f"✉️ Сообщение от администратора:\n\n{text}",
        )

        await update.message.reply_text(
            "✅ Сообщение отправлено."
        )

    except Exception:
        await update.message.reply_text(
            "❌ Не удалось отправить сообщение."
        )


# =========================================================
# ЗАПУСК
# =========================================================

def main():
    init_db()

    web_thread = threading.Thread(
        target=run_web_server,
        daemon=True,
    )

    web_thread.start()

    app = Application.builder().token(BOT_TOKEN).build()

    # ПОПОЛНЕНИЕ
    app.add_handler(
        ConversationHandler(
            entry_points=[
                CallbackQueryHandler(
                    refill_start,
                    pattern="^main_refill$",
                )
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
                    )
                ],
            },
            fallbacks=[
                CommandHandler("start", start),
            ],
        )
    )

    # ПОКУПКА STARS / PREMIUM
    app.add_handler(
        ConversationHandler(
            entry_points=[
                CallbackQueryHandler(
                    buy_start,
                    pattern="^buy_stars_|^buy_premium_",
                )
            ],
            states={
                BUY_USERNAME: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        buy_username,
                    )
                ],
                BUY_CONFIRM: [
                    CallbackQueryHandler(
                        buy_confirm,
                        pattern="^buy_confirm$|^buy_cancel$",
                    )
                ],
            },
            fallbacks=[
                CommandHandler("start", start),
            ],
        )
    )

    # ПОДАРКИ
    app.add_handler(
        ConversationHandler(
            entry_points=[
                CallbackQueryHandler(
                    gift_start,
                    pattern="^gift_",
                )
            ],
            states={
                GIFT_USERNAME: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        gift_username,
                    )
                ],
                GIFT_CONFIRM: [
                    CallbackQueryHandler(
                        gift_confirm,
                        pattern="^gift_confirm$|^gift_cancel$",
                    )
                ],
            },
            fallbacks=[
                CommandHandler("start", start),
            ],
        )
    )

    # АДМИНКА
    app.add_handler(
        CommandHandler("admin", admin_panel)
    )

    app.add_handler(
        CommandHandler("setbal", cmd_setbal)
    )

    app.add_handler(
        CommandHandler("ban", cmd_ban)
    )

    app.add_handler(
        CommandHandler("unban", cmd_unban)
    )

    app.add_handler(
        CommandHandler("msg", cmd_msg)
    )

    app.add_handler(
        CallbackQueryHandler(
            admin_callback,
            pattern="^admin_",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            admin_payment,
            pattern="^pay_",
        )
    )

    # START
    app.add_handler(
        CommandHandler("start", start)
    )

    # ГЛАВНЫЕ КНОПКИ
    app.add_handler(
        CallbackQueryHandler(
            main_callback,
            pattern=(
                "^main_shop$|"
                "^main_profile$|"
                "^shop_stars$|"
                "^shop_premium$|"
                "^shop_gifts$|"
                "^shop_accounts$|"
                "^back_main$|"
                "^lang_"
            ),
        )
    )

    logger.info("BOT STARTED")

    app.run_polling()


if __name__ == "__main__":
    main()