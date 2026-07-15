import threading
import asyncio
import json
import logging
import os
import sqlite3
import uuid

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

API_KEY = os.environ["ELDER_API_KEY"]
API_URL = "https://asosiy.elder.uz/api"

CARD_NUMBER = "5614 6835 8985 1641"

DB_FILE = "bot_database.db"

DEFAULT_LANG = "ru"

PRICE_PER_STAR = 210

PREMIUM_PRICES = {
    3: 165000,
    6: 222000,
    12: 406000
}


# =========================================================
# СОСТОЯНИЯ
# =========================================================

REFILL_AMOUNT = 1
REFILL_CHECK = 2

BUY_AMOUNT = 3
BUY_USERNAME = 4
BUY_CONFIRM = 5


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

        "profile": (
            "👤 <b>Мой профиль</b>\n\n"
            "🆔 ID: <code>{user_id}</code>\n"
            "💰 Баланс: <b>{balance:,} сум</b>\n\n"
            "🌐 Выберите язык:"
        ),

        "shop": "🛍 <b>Выберите услугу:</b>",

        "stars": (
            "💎 <b>Telegram Stars</b>\n\n"
            "💵 Цена: {price} сум за 1 ⭐"
        ),

        "premium": (
            "🌟 <b>Telegram Premium</b>\n\n"
            "🔹 3 месяца — 165 000 сум\n"
            "🔹 6 месяцев — 222 000 сум\n"
            "🔹 12 месяцев — 406 000 сум"
        ),

        "manual_stars": "✏️ Ввести количество Stars",

        "enter_stars": (
            "✏️ Введите количество Telegram Stars:\n\n"
            "Минимум: 50 ⭐"
        ),

        "enter_username": (
            "✏️ Введите Telegram username получателя.\n\n"
            "Без символа @\n"
            "Например: durov"
        ),

        "confirm": (
            "📝 <b>Подтверждение покупки</b>\n\n"
            "📦 Товар: {product}\n"
            "👤 Получатель: @{username}\n"
            "💰 Цена: <b>{price:,} сум</b>\n\n"
            "Подтвердить покупку?"
        ),

        "confirm_btn": "✅ Купить",

        "not_enough": (
            "❌ Недостаточно средств.\n\n"
            "💰 Цена: {price:,} сум\n"
            "💳 Ваш баланс: {balance:,} сум"
        ),

        "refill_start": (
            "💳 Введите сумму пополнения в сумах.\n\n"
            "Например: 50000"
        ),

        "refill_bad": "❌ Введите корректную сумму.",

        "refill_invoice": (
            "💳 <b>Пополнение баланса</b>\n\n"
            "💰 Сумма: <b>{amount:,} сум</b>\n\n"
            "Переведите ровно эту сумму на карту:\n"
            "<code>{card}</code>\n\n"
            "После оплаты отправьте фото или скриншот чека."
        ),

        "refill_bad_photo": "❌ Отправьте именно фото или скриншот чека.",

        "refill_sent": (
            "⏳ Чек отправлен администратору.\n\n"
            "Ожидайте проверки."
        ),

        "order_processing": "🔄 Обрабатываем заказ...",

        "order_success": (
            "✅ <b>Заказ успешно выполнен!</b>\n\n"
            "📦 Товар: {product}\n"
            "👤 Получатель: @{username}"
        ),

        "order_error": (
            "❌ Не удалось выполнить заказ.\n\n"
            "Попробуйте немного позже или обратитесь в поддержку."
        ),

        "banned": "❌ Вы заблокированы в этом боте.",

        "accounts": "📱 <b>Выберите страну номера:</b>",

        "account_uz": "🇺🇿 Страна: Узбекистан — 13 000 сум",
        "account_co": "🇨🇴 Страна: Колумбия — 6 500 сум",
        "account_uk": "🇬🇧 Страна: Великобритания — 9 000 сум",
        "account_us": "🇺🇸 Страна: Америка — 8 000 сум",
    },

    "uz": {
        "welcome": (
            "👋 Salom, {name}!\n\n"
            "Telegram Stars & Premium do'koniga xush kelibsiz.\n\n"
            "💰 Balansingiz: {balance:,} so'm"
        ),

        "btn_shop": "🛍 Xizmatlar",
        "btn_refill": "💳 Balansni to'ldirish",
        "btn_profile": "👤 Profilim",
        "btn_back": "⬅️ Ortga",
        "btn_cancel": "❌ Bekor qilish",

        "profile": (
            "👤 <b>Profilim</b>\n\n"
            "🆔 ID: <code>{user_id}</code>\n"
            "💰 Balans: <b>{balance:,} so'm</b>\n\n"
            "🌐 Tilni tanlang:"
        ),

        "shop": "🛍 <b>Xizmatni tanlang:</b>",

        "stars": (
            "💎 <b>Telegram Stars</b>\n\n"
            "💵 Narx: 1 ⭐ uchun {price} so'm"
        ),

        "premium": (
            "🌟 <b>Telegram Premium</b>\n\n"
            "🔹 3 oy — 165 000 so'm\n"
            "🔹 6 oy — 222 000 so'm\n"
            "🔹 12 oy — 406 000 so'm"
        ),

        "manual_stars": "✏️ Stars miqdorini kiritish",

        "enter_stars": (
            "✏️ Telegram Stars miqdorini kiriting:\n\n"
            "Minimum: 50 ⭐"
        ),

        "enter_username": (
            "✏️ Qabul qiluvchining Telegram username'ini kiriting.\n\n"
            "@ belgisiz\n"
            "Masalan: durov"
        ),

        "confirm": (
            "📝 <b>Xaridni tasdiqlash</b>\n\n"
            "📦 Mahsulot: {product}\n"
            "👤 Qabul qiluvchi: @{username}\n"
            "💰 Narx: <b>{price:,} so'm</b>\n\n"
            "Xaridni tasdiqlaysizmi?"
        ),

        "confirm_btn": "✅ Sotib olish",

        "not_enough": (
            "❌ Mablag' yetarli emas.\n\n"
            "💰 Narx: {price:,} so'm\n"
            "💳 Balans: {balance:,} so'm"
        ),

        "refill_start": (
            "💳 Balansni to'ldirish summasini kiriting.\n\n"
            "Masalan: 50000"
        ),

        "refill_bad": "❌ To'g'ri summa kiriting.",

        "refill_invoice": (
            "💳 <b>Balansni to'ldirish</b>\n\n"
            "💰 Summa: <b>{amount:,} so'm</b>\n\n"
            "Ushbu summani kartaga o'tkazing:\n"
            "<code>{card}</code>\n\n"
            "To'lovdan so'ng chek rasmini yuboring."
        ),

        "refill_bad_photo": "❌ Chek rasmini yuboring.",

        "refill_sent": (
            "⏳ Chek administratorga yuborildi.\n\n"
            "Tekshiruvni kuting."
        ),

        "order_processing": "🔄 Buyurtma qayta ishlanmoqda...",

        "order_success": (
            "✅ <b>Buyurtma muvaffaqiyatli bajarildi!</b>\n\n"
            "📦 Mahsulot: {product}\n"
            "👤 Qabul qiluvchi: @{username}"
        ),

        "order_error": (
            "❌ Buyurtmani bajarib bo'lmadi.\n\n"
            "Keyinroq qayta urinib ko'ring yoki qo'llab-quvvatlash xizmatiga murojaat qiling."
        ),

        "banned": "❌ Siz ushbu botda bloklangansiz.",

        "accounts": "📱 <b>Telefon raqami davlatini tanlang:</b>",

        "account_uz": "🇺🇿 Davlat: O'zbekiston — 13 000 so'm",
        "account_co": "🇨🇴 Davlat: Kolumbiya — 6 500 so'm",
        "account_uk": "🇬🇧 Davlat: Buyuk Britaniya — 9 000 so'm",
        "account_us": "🇺🇸 Davlat: Amerika — 8 000 so'm",
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
        result = {
            "balance": row[0],
            "username": row[1],
            "name": row[2],
            "lang": row[3],
            "is_banned": bool(row[4])
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


def update_user_ban(user_id, status):
    conn = sqlite3.connect(DB_FILE)

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE users
        SET is_banned = ?
        WHERE user_id = ?
        """,
        (1 if status else 0, user_id)
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

    data = get_user_data(user.id)

    if data["is_banned"]:
        lang = data.get("lang", "ru")

        if update.message:
            await update.message.reply_text(
                TEXTS[lang]["banned"]
            )

        elif update.callback_query:
            await update.callback_query.answer(
                TEXTS[lang]["banned"],
                show_alert=True
            )

        return True

    return False


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
            b"Bot is running"
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
# API ПОСТАВЩИКА
# =========================================================

async def send_order_to_provider(
    product_type,
    value,
    username
):
    username = username.replace("@", "").strip()

    client_order_id = str(
        uuid.uuid4()
    )

    headers = {
        "X-Api-Key": API_KEY,
        "Content-Type": "application/json"
    }

    if product_type == "stars":
        endpoint = "/stars/buy"

        payload = {
            "username": username,
            "amount": value,
            "client_order_id": client_order_id
        }

    else:
        endpoint = "/premium/buy"

        payload = {
            "username": username,
            "months": value,
            "client_order_id": client_order_id
        }

    try:
        async with httpx.AsyncClient() as client:

            response = await client.post(
                API_URL + endpoint,
                headers=headers,
                json=payload,
                timeout=30
            )

            logger.info(
                f"Provider response: {response.status_code}"
            )

            if response.status_code != 200:
                return False

            data = response.json()

            if data.get("success") is True:
                return True

            return False

    except Exception as e:
        logger.error(
            f"Order error: {e}"
        )

        return False


# =========================================================
# ГЛАВНОЕ МЕНЮ
# =========================================================

def main_keyboard(lang):
    t = TEXTS[lang]

    return InlineKeyboardMarkup([
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
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_user_banned(update):
        return ConversationHandler.END

    context.user_data.clear()

    user = update.effective_user

    data = get_user_data(
        user.id,
        user.username,
        user.first_name
    )

    lang = data["lang"]

    text = TEXTS[lang]["welcome"].format(
        name=user.first_name,
        balance=data["balance"]
    )

    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=main_keyboard(lang)
        )

    return ConversationHandler.END


# =========================================================
# ПРОФИЛЬ
# =========================================================

async def show_profile(update, context):
    if await is_user_banned(update):
        return

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    data = get_user_data(user_id)

    lang = data["lang"]

    text = TEXTS[lang]["profile"].format(
        user_id=user_id,
        balance=data["balance"]
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🇺🇿 O'zbekcha",
                callback_data="setlang_uz"
            ),
            InlineKeyboardButton(
                "🇷🇺 Русский",
                callback_data="setlang_ru"
            )
        ],
        [
            InlineKeyboardButton(
                TEXTS[lang]["btn_back"],
                callback_data="back_to_main"
            )
        ]
    ])

    await query.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# =========================================================
# МАГАЗИН
# =========================================================

async def show_shop(update, context):
    query = update.callback_query

    await query.answer()

    data = get_user_data(
        query.from_user.id
    )

    lang = data["lang"]

    t = TEXTS[lang]

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "💎 Telegram Stars",
                callback_data="shop_stars"
            )
        ],
        [
            InlineKeyboardButton(
                "🌟 Telegram Premium",
                callback_data="shop_premium"
            )
        ],
        [
            InlineKeyboardButton(
                "📱 Telegram аккаунты",
                callback_data="shop_accounts"
            )
        ],
        [
            InlineKeyboardButton(
                t["btn_back"],
                callback_data="back_to_main"
            )
        ]
    ])

    await query.message.edit_text(
        t["shop"],
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def show_stars(update, context):
    query = update.callback_query

    await query.answer()

    data = get_user_data(
        query.from_user.id
    )

    lang = data["lang"]

    t = TEXTS[lang]

    keyboard = InlineKeyboardMarkup([
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
                t["manual_stars"],
                callback_data="buy_stars_manual"
            )
        ],
        [
            InlineKeyboardButton(
                t["btn_back"],
                callback_data="main_shop"
            )
        ]
    ])

    await query.message.edit_text(
        t["stars"].format(
            price=PRICE_PER_STAR
        ),
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def show_premium(update, context):
    query = update.callback_query

    await query.answer()

    data = get_user_data(
        query.from_user.id
    )

    lang = data["lang"]

    t = TEXTS[lang]

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🚀 3 месяца — 165 000 сум",
                callback_data="buy_premium_3"
            )
        ],
        [
            InlineKeyboardButton(
                "🚀 6 месяцев — 222 000 сум",
                callback_data="buy_premium_6"
            )
        ],
        [
            InlineKeyboardButton(
                "🚀 12 месяцев — 406 000 сум",
                callback_data="buy_premium_12"
            )
        ],
        [
            InlineKeyboardButton(
                t["btn_back"],
                callback_data="main_shop"
            )
        ]
    ])

    await query.message.edit_text(
        t["premium"],
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# =========================================================
# АККАУНТЫ
# =========================================================

async def show_accounts(update, context):
    query = update.callback_query

    await query.answer()

    data = get_user_data(
        query.from_user.id
    )

    lang = data["lang"]

    t = TEXTS[lang]

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                t["account_uz"],
                callback_data="account_uz_13000"
            )
        ],
        [
            InlineKeyboardButton(
                t["account_co"],
                callback_data="account_co_6500"
            )
        ],
        [
            InlineKeyboardButton(
                t["account_uk"],
                callback_data="account_uk_9000"
            )
        ],
        [
            InlineKeyboardButton(
                t["account_us"],
                callback_data="account_us_8000"
            )
        ],
        [
            InlineKeyboardButton(
                t["btn_back"],
                callback_data="main_shop"
            )
        ]
    ])

    await query.message.edit_text(
        t["accounts"],
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def buy_account(update, context):
    query = update.callback_query

    await query.answer()

    parts = query.data.split("_")

    country = parts[1]

    price = int(parts[2])

    data = get_user_data(
        query.from_user.id
    )

    if data["balance"] < price:
        await query.answer(
            "❌ Недостаточно средств!",
            show_alert=True
        )

        return

    update_user_balance(
        query.from_user.id,
        -price
    )

    country_names = {
        "uz": "Узбекистан",
        "co": "Колумбия",
        "uk": "Великобритания",
        "us": "Америка"
    }

    country_name = country_names.get(
        country,
        country
    )

    await context.bot.send_message(
        ADMIN_ID,
        (
            "📱 <b>Новый заказ аккаунта</b>\n\n"
            f"🌍 Страна: {country_name}\n"
            f"👤 ID: <code>{query.from_user.id}</code>\n"
            f"💰 Цена: {price:,} сум"
        ),
        parse_mode="HTML"
    )

    await query.message.edit_text(
        "✅ Заявка принята!\n\n"
        "📩 Ожидайте выдачу аккаунта."
    )


# =========================================================
# ПОПОЛНЕНИЕ
# =========================================================

async def start_refill(update, context):
    query = update.callback_query

    await query.answer()

    data = get_user_data(
        query.from_user.id
    )

    lang = data["lang"]

    await query.message.edit_text(
        TEXTS[lang]["refill_start"]
    )

    return REFILL_AMOUNT


async def receive_refill_amount(update, context):
    data = get_user_data(
        update.effective_user.id
    )

    lang = data["lang"]

    amount_text = update.message.text.replace(
        " ",
        ""
    )

    if not amount_text.isdigit():
        await update.message.reply_text(
            TEXTS[lang]["refill_bad"]
        )

        return REFILL_AMOUNT

    amount = int(amount_text)

    if amount <= 0:
        await update.message.reply_text(
            TEXTS[lang]["refill_bad"]
        )

        return REFILL_AMOUNT

    context.user_data["refill_amount"] = amount

    await update.message.reply_text(
        TEXTS[lang]["refill_invoice"].format(
            amount=amount,
            card=CARD_NUMBER
        ),
        parse_mode="HTML"
    )

    return REFILL_CHECK


async def receive_refill_check(update, context):
    if await is_user_banned(update):
        return ConversationHandler.END

    user = update.effective_user

    data = get_user_data(user.id)

    lang = data["lang"]

    amount = context.user_data.get(
        "refill_amount",
        0
    )

    if update.message.photo:
        file_id = update.message.photo[-1].file_id

        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=file_id,
            caption=(
                "💰 <b>Пополнение баланса</b>\n\n"
                f"👤 ID: <code>{user.id}</code>\n"
                f"👤 Username: @{user.username or 'нет'}\n"
                f"💰 Сумма: {amount:,} сум"
            ),
            reply_markup=InlineKeyboardMarkup([
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
            ]),
            parse_mode="HTML"
        )

    elif update.message.document:

        if not update.message.document.mime_type.startswith("image/"):
            await update.message.reply_text(
                TEXTS[lang]["refill_bad_photo"]
            )

            return REFILL_CHECK

        file_id = update.message.document.file_id

        await context.bot.send_document(
            chat_id=ADMIN_ID,
            document=file_id,
            caption=(
                "💰 <b>Пополнение баланса</b>\n\n"
                f"👤 ID: <code>{user.id}</code>\n"
                f"👤 Username: @{user.username or 'нет'}\n"
                f"💰 Сумма: {amount:,} сум"
            ),
            reply_markup=InlineKeyboardMarkup([
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
            ]),
            parse_mode="HTML"
        )

    else:
        await update.message.reply_text(
            TEXTS[lang]["refill_bad_photo"]
        )

        return REFILL_CHECK

    await update.message.reply_text(
        TEXTS[lang]["refill_sent"]
    )

    context.user_data.clear()

    return ConversationHandler.END


# =========================================================
# ПОКУПКА STARS / PREMIUM
# =========================================================

async def start_product_buy(update, context):
    query = update.callback_query

    await query.answer()

    data = get_user_data(
        query.from_user.id
    )

    lang = data["lang"]

    t = TEXTS[lang]

    callback = query.data

    if callback == "buy_stars_manual":

        context.user_data["product_type"] = "stars"

        await query.message.edit_text(
            t["enter_stars"]
        )

        return BUY_AMOUNT

    if callback.startswith("buy_stars_fixed_"):

        value = int(
            callback.split("_")[-1]
        )

        context.user_data["product_type"] = "stars"
        context.user_data["product_value"] = value

        price = value * PRICE_PER_STAR

    elif callback.startswith("buy_premium_"):

        value = int(
            callback.split("_")[-1]
        )

        context.user_data["product_type"] = "premium"
        context.user_data["product_value"] = value

        price = PREMIUM_PRICES[value]

    else:
        return ConversationHandler.END

    if data["balance"] < price:

        await query.answer(
            t["not_enough"].format(
                price=price,
                balance=data["balance"]
            ),
            show_alert=True
        )

        return ConversationHandler.END

    context.user_data["product_price"] = price

    await query.message.edit_text(
        t["enter_username"]
    )

    return BUY_USERNAME


async def receive_stars_amount(update, context):
    data = get_user_data(
        update.effective_user.id
    )

    lang = data["lang"]

    if not update.message.text.isdigit():

        await update.message.reply_text(
            TEXTS[lang]["enter_stars"]
        )

        return BUY_AMOUNT

    amount = int(
        update.message.text
    )

    if amount < 50:

        await update.message.reply_text(
            "❌ Минимальное количество — 50 Stars."
        )

        return BUY_AMOUNT

    if amount > 10000:

        await update.message.reply_text(
            "❌ Максимальное количество — 10 000 Stars."
        )

        return BUY_AMOUNT

    price = amount * PRICE_PER_STAR

    if data["balance"] < price:

        await update.message.reply_text(
            TEXTS[lang]["not_enough"].format(
                price=price,
                balance=data["balance"]
            )
        )

        return ConversationHandler.END

    context.user_data["product_value"] = amount
    context.user_data["product_price"] = price

    await update.message.reply_text(
        TEXTS[lang]["enter_username"]
    )

    return BUY_USERNAME


async def receive_username(update, context):
    data = get_user_data(
        update.effective_user.id
    )

    lang = data["lang"]

    username = update.message.text.strip()

    username = username.replace(
        "@",
        ""
    )

    if not username:

        await update.message.reply_text(
            TEXTS[lang]["enter_username"]
        )

        return BUY_USERNAME

    context.user_data["username"] = username

    product_type = context.user_data["product_type"]
    value = context.user_data["product_value"]
    price = context.user_data["product_price"]

    if product_type == "stars":
        product = f"{value} Stars"

    else:
        product = f"Telegram Premium на {value} месяцев"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                TEXTS[lang]["confirm_btn"],
                callback_data="confirm_purchase"
            )
        ],
        [
            InlineKeyboardButton(
                TEXTS[lang]["btn_cancel"],
                callback_data="cancel_purchase"
            )
        ]
    ])

    await update.message.reply_text(
        TEXTS[lang]["confirm"].format(
            product=product,
            username=username,
            price=price
        ),
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    return BUY_CONFIRM


async def confirm_purchase(update, context):
    query = update.callback_query

    await query.answer()

    if query.data == "cancel_purchase":

        await query.message.edit_text(
            "❌ Покупка отменена."
        )

        context.user_data.clear()

        return ConversationHandler.END

    data = get_user_data(
        query.from_user.id
    )

    product_type = context.user_data["product_type"]
    value = context.user_data["product_value"]
    price = context.user_data["product_price"]
    username = context.user_data["username"]

    if data["balance"] < price:

        await query.message.edit_text(
            "❌ Недостаточно средств."
        )

        context.user_data.clear()

        return ConversationHandler.END

    await query.message.edit_text(
        TEXTS[data["lang"]]["order_processing"]
    )

    success = await send_order_to_provider(
        product_type,
        value,
        username
    )

    if not success:

        await query.message.edit_text(
            TEXTS[data["lang"]]["order_error"]
        )

        context.user_data.clear()

        return ConversationHandler.END

    update_user_balance(
        query.from_user.id,
        -price
    )

    if product_type == "stars":
        product = f"{value} Stars"

    else:
        product = f"Premium {value} месяцев"

    await query.message.edit_text(
        TEXTS[data["lang"]]["order_success"].format(
            product=product,
            username=username
        ),
        parse_mode="HTML"
    )

    await context.bot.send_message(
        ADMIN_ID,
        (
            "🚀 <b>Новый автоматический заказ</b>\n\n"
            f"👤 ID: <code>{query.from_user.id}</code>\n"
            f"📦 Товар: {product}\n"
            f"👤 Получатель: @{username}\n"
            f"💰 Цена: {price:,} сум"
        ),
        parse_mode="HTML"
    )

    context.user_data.clear()

    return ConversationHandler.END


# =========================================================
# АДМИНКА
# =========================================================

def admin_only(func):

    async def wrapper(update, context):

        if update.effective_user.id != ADMIN_ID:

            if update.callback_query:

                await update.callback_query.answer(
                    "⛔ Доступ запрещён.",
                    show_alert=True
                )

            return

        return await func(update, context)

    return wrapper


@admin_only
async def admin_panel(update, context):

    keyboard = InlineKeyboardMarkup([
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
    ])

    await update.message.reply_text(
        (
            "🛠 <b>Панель администратора</b>\n\n"
            "/setbal ID сумма — изменить баланс\n"
            "/ban ID — заблокировать\n"
            "/unban ID — разблокировать\n"
            "/msg ID текст — отправить сообщение"
        ),
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@admin_only
async def admin_callbacks(update, context):

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

        per_page = 15

        start = page * per_page

        end = start + per_page

        users_page = users[start:end]

        total_pages = max(
            1,
            (len(users) + per_page - 1) // per_page
        )

        text = (
            f"👥 <b>Пользователи</b>\n"
            f"Страница {page + 1}/{total_pages}\n\n"
        )

        for user_id, username, name, balance, banned in users_page:

            text += (
                f"🆔 <code>{user_id}</code>\n"
                f"👤 @{username or 'нет'}\n"
                f"💰 {balance:,} сум\n"
                f"{'⛔ Заблокирован' if banned else '🟢 Активен'}\n"
                "────────────\n"
            )

        buttons = []

        if page > 0:

            buttons.append(
                InlineKeyboardButton(
                    "⬅️ Назад",
                    callback_data=f"admin_users_{page - 1}"
                )
            )

        if end < len(users):

            buttons.append(
                InlineKeyboardButton(
                    "Вперёд ➡️",
                    callback_data=f"admin_users_{page + 1}"
                )
            )

        keyboard = []

        if buttons:
            keyboard.append(buttons)

        keyboard.append([
            InlineKeyboardButton(
                "❌ Закрыть",
                callback_data="admin_close"
            )
        ])

        await query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )


@admin_only
async def cmd_setbal(update, context):

    if len(context.args) < 2:

        await update.message.reply_text(
            "❌ Использование: /setbal ID сумма"
        )

        return

    user_id = int(
        context.args[0]
    )

    amount = int(
        context.args[1]
    )

    update_user_balance(
        user_id,
        amount
    )

    data = get_user_data(user_id)

    await update.message.reply_text(
        (
            f"✅ Баланс изменён.\n\n"
            f"🆔 ID: {user_id}\n"
            f"💰 Новый баланс: {data['balance']:,} сум"
        )
    )


@admin_only
async def cmd_ban(update, context):

    if not context.args:
        return

    user_id = int(
        context.args[0]
    )

    update_user_ban(
        user_id,
        True
    )

    await update.message.reply_text(
        "⛔ Пользователь заблокирован."
    )


@admin_only
async def cmd_unban(update, context):

    if not context.args:
        return

    user_id = int(
        context.args[0]
    )

    update_user_ban(
        user_id,
        False
    )

    await update.message.reply_text(
        "🟢 Пользователь разблокирован."
    )


@admin_only
async def cmd_msg(update, context):

    if len(context.args) < 2:
        return

    user_id = int(
        context.args[0]
    )

    text = " ".join(
        context.args[1:]
    )

    try:

        await context.bot.send_message(
            user_id,
            text
        )

        await update.message.reply_text(
            "✅ Сообщение отправлено."
        )

    except Exception:

        await update.message.reply_text(
            "❌ Не удалось отправить сообщение."
        )


# =========================================================
# ПОПОЛНЕНИЕ — АДМИН
# =========================================================

@admin_only
async def payment_callbacks(update, context):

    query = update.callback_query

    await query.answer()

    if query.data.startswith("pay_yes_"):

        parts = query.data.split("_")

        user_id = int(parts[2])

        amount = int(parts[3])

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
                (
                    "🎉 <b>Баланс пополнен!</b>\n\n"
                    f"💰 Сумма: {amount:,} сум"
                ),
                parse_mode="HTML"
            )

        except Exception:
            pass

    elif query.data.startswith("pay_no_"):

        await query.message.edit_caption(
            "🔴 Пополнение отклонено."
        )


# =========================================================
# ОБЩИЙ CALLBACK HANDLER
# =========================================================

async def callback_handler(update, context):

    if await is_user_banned(update):
        return

    query = update.callback_query

    data = query.data

    if data == "main_shop":

        await show_shop(
            update,
            context
        )

    elif data == "main_profile":

        await show_profile(
            update,
            context
        )

    elif data == "back_to_main":

        user_data = get_user_data(
            query.from_user.id
        )

        lang = user_data["lang"]

        await query.answer()

        await query.message.edit_text(
            TEXTS[lang]["welcome"].format(
                name=query.from_user.first_name,
                balance=user_data["balance"]
            ),
            reply_markup=main_keyboard(lang)
        )

    elif data == "shop_stars":

        await show_stars(
            update,
            context
        )

    elif data == "shop_premium":

        await show_premium(
            update,
            context
        )

    elif data == "shop_accounts":

        await show_accounts(
            update,
            context
        )

    elif data.startswith("account_"):

        await buy_account(
            update,
            context
        )

    elif data.startswith("setlang_"):

        lang = data.split("_")[1]

        update_user_lang(
            query.from_user.id,
            lang
        )

        await show_profile(
            update,
            context
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
                    start_refill,
                    pattern="^main_refill$"
                )
            ],
            states={
                REFILL_AMOUNT: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        receive_refill_amount
                    )
                ],

                REFILL_CHECK: [
                    MessageHandler(
                        filters.PHOTO | filters.Document.IMAGE,
                        receive_refill_check
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

    # ПОКУПКИ

    app.add_handler(
        ConversationHandler(
            entry_points=[
                CallbackQueryHandler(
                    start_product_buy,
                    pattern=(
                        "^buy_stars_manual$|"
                        "^buy_stars_fixed_|"
                        "^buy_premium_"
                    )
                )
            ],
            states={
                BUY_AMOUNT: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        receive_stars_amount
                    )
                ],

                BUY_USERNAME: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        receive_username
                    )
                ],

                BUY_CONFIRM: [
                    CallbackQueryHandler(
                        confirm_purchase,
                        pattern="^confirm_purchase$|^cancel_purchase$"
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

    # АДМИН

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
            admin_callbacks,
            pattern="^admin_"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            payment_callbacks,
            pattern="^pay_yes_|^pay_no_"
        )
    )

    # КНОПКИ

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            callback_handler,
            pattern=(
                "^main_shop$|"
                "^main_profile$|"
                "^main_refill$|"
                "^back_to_main$|"
                "^shop_stars$|"
                "^shop_premium$|"
                "^shop_accounts$|"
                "^account_|"
                "^setlang_"
            )
        )
    )

    logger.info(
        "BOT STARTED"
    )

    app.run_polling()


if __name__ == "__main__":

    main()