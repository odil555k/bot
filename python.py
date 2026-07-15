import threading
import logging
import os
import sqlite3
import uuid
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

DEFAULT_LANG = "ru"

# ЦЕНА ДЛЯ ТВОИХ КЛИЕНТОВ
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

BUY_AMOUNT, BUY_USERNAME, BUY_CONFIRM = range(2, 5)

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

        "btn_shop": "🛍 Купить услуги",
        "btn_refill": "💳 Пополнить баланс",
        "btn_profile": "👤 Мой кабинет",
        "btn_back": "⬅️ Назад",
        "btn_cancel": "❌ Отмена",

        "profile": (
            "👤 <b>Личный кабинет</b>\n\n"
            "🆔 ID: <code>{user_id}</code>\n"
            "💰 Баланс: <b>{balance:,} сум</b>\n\n"
            "🌐 Сменить язык:"
        ),

        "shop": "🛍 <b>Выберите категорию:</b>",

        "stars_category": "💎 Telegram Stars",
        "premium_category": "🌟 Telegram Premium",
        "accounts_category": "📱 Telegram аккаунты",

        "stars_text": (
            "💎 <b>Telegram Stars</b>\n\n"
            "💵 Цена: <b>{price} сум за 1 ⭐</b>"
        ),

        "manual_stars": "✏️ Ввести количество",

        "premium_text": (
            "🌟 <b>Telegram Premium</b>\n\n"
            "🔹 3 месяца — 165 000 сум\n"
            "🔹 6 месяцев — 222 000 сум\n"
            "🔹 12 месяцев — 406 000 сум"
        ),

        "refill_amount": (
            "💳 Введите сумму пополнения в сумах.\n\n"
            "Например: <code>50000</code>"
        ),

        "bad_number": "❌ Введите корректное число.",

        "refill_invoice": (
            "💳 <b>Заявка на пополнение</b>\n\n"
            "💰 Сумма: <b>{amount:,} сум</b>\n\n"
            "Переведите ровно эту сумму на карту:\n"
            "<code>{card}</code>\n\n"
            "После оплаты отправьте фото или скриншот чека."
        ),

        "bad_check": "❌ Отправьте именно фото или скриншот чека.",

        "check_sent": (
            "⏳ Чек отправлен администратору.\n"
            "Ожидайте проверки."
        ),

        "stars_amount": (
            "✏️ Введите количество Telegram Stars.\n\n"
            "Минимум: 50 ⭐\n"
            "Максимум: 10 000 ⭐"
        ),

        "stars_invalid": (
            "❌ Количество Stars должно быть от 50 до 10 000."
        ),

        "username": (
            "✏️ Введите Telegram username получателя.\n\n"
            "Без символа @\n"
            "Например: <code>durov</code>"
        ),

        "not_enough": (
            "❌ Недостаточно средств.\n\n"
            "💰 Стоимость: {price:,} сум\n"
            "💳 Ваш баланс: {balance:,} сум"
        ),

        "confirm": (
            "📝 <b>Подтверждение покупки</b>\n\n"
            "📦 Товар: <b>{product}</b>\n"
            "👤 Получатель: <code>{username}</code>\n"
            "💰 Стоимость: <b>{price:,} сум</b>\n\n"
            "Подтвердить покупку?"
        ),

        "confirm_button": "✅ Купить",

        "processing": "🔄 Обрабатываем заказ...",

        "order_success": (
            "✅ <b>Заказ успешно выполнен!</b>\n\n"
            "📦 {product}\n"
            "👤 Получатель: @{username}\n\n"
            "🎉 Спасибо за покупку!"
        ),

        "order_error": (
            "❌ Не удалось выполнить заказ.\n\n"
            "💰 Деньги с вашего баланса НЕ списаны.\n"
            "Попробуйте ещё раз позже."
        ),

        "banned": "❌ Вы заблокированы в этом боте.",

        "account_text": (
            "📱 <b>Telegram аккаунты</b>\n\n"
            "Выберите страну номера:"
        ),

        "account_order": (
            "✅ Заявка принята!\n\n"
            "Администратор скоро свяжется с вами."
        ),
    },

    "uz": {
        "welcome": (
            "👋 Salom, {name}!\n\n"
            "Telegram Stars & Premium do'koniga xush kelibsiz.\n\n"
            "💰 Balansingiz: {balance:,} so'm"
        ),

        "btn_shop": "🛍 Xizmatlarni sotib olish",
        "btn_refill": "💳 Balansni to'ldirish",
        "btn_profile": "👤 Shaxsiy kabinet",
        "btn_back": "⬅️ Ortga",
        "btn_cancel": "❌ Bekor qilish",

        "profile": (
            "👤 <b>Shaxsiy kabinet</b>\n\n"
            "🆔 ID: <code>{user_id}</code>\n"
            "💰 Balans: <b>{balance:,} so'm</b>\n\n"
            "🌐 Tilni tanlang:"
        ),

        "shop": "🛍 <b>Kategoriyani tanlang:</b>",

        "stars_category": "💎 Telegram Stars",
        "premium_category": "🌟 Telegram Premium",
        "accounts_category": "📱 Telegram akkauntlar",

        "stars_text": (
            "💎 <b>Telegram Stars</b>\n\n"
            "💵 Narx: <b>1 ⭐ — {price} so'm</b>"
        ),

        "manual_stars": "✏️ Miqdorni kiritish",

        "premium_text": (
            "🌟 <b>Telegram Premium</b>\n\n"
            "🔹 3 oy — 165 000 so'm\n"
            "🔹 6 oy — 222 000 so'm\n"
            "🔹 12 oy — 406 000 so'm"
        ),

        "refill_amount": (
            "💳 To'ldirish summasini kiriting.\n\n"
            "Masalan: <code>50000</code>"
        ),

        "bad_number": "❌ To'g'ri son kiriting.",

        "refill_invoice": (
            "💳 <b>Balans to'ldirish</b>\n\n"
            "💰 Summa: <b>{amount:,} so'm</b>\n\n"
            "Ushbu summani kartaga o'tkazing:\n"
            "<code>{card}</code>\n\n"
            "To'lovdan keyin chek rasmini yuboring."
        ),

        "bad_check": "❌ Chek rasmini yuboring.",

        "check_sent": (
            "⏳ Chek administratorga yuborildi.\n"
            "Tekshiruvni kuting."
        ),

        "stars_amount": (
            "✏️ Telegram Stars sonini kiriting.\n\n"
            "Minimum: 50 ⭐\n"
            "Maksimum: 10 000 ⭐"
        ),

        "stars_invalid": "❌ Stars soni 50 dan 10 000 gacha bo'lishi kerak.",

        "username": (
            "✏️ Qabul qiluvchining Telegram username'ini kiriting.\n\n"
            "@ belgisiz\n"
            "Masalan: <code>durov</code>"
        ),

        "not_enough": (
            "❌ Mablag' yetarli emas.\n\n"
            "💰 Narx: {price:,} so'm\n"
            "💳 Balansingiz: {balance:,} so'm"
        ),

        "confirm": (
            "📝 <b>Xaridni tasdiqlash</b>\n\n"
            "📦 Mahsulot: <b>{product}</b>\n"
            "👤 Qabul qiluvchi: <code>{username}</code>\n"
            "💰 Narxi: <b>{price:,} so'm</b>\n\n"
            "Xaridni tasdiqlaysizmi?"
        ),

        "confirm_button": "✅ Sotib olish",

        "processing": "🔄 Buyurtma bajarilmoqda...",

        "order_success": (
            "✅ <b>Buyurtma muvaffaqiyatli bajarildi!</b>\n\n"
            "📦 {product}\n"
            "👤 Qabul qiluvchi: @{username}\n\n"
            "🎉 Xaridingiz uchun rahmat!"
        ),

        "order_error": (
            "❌ Buyurtmani bajarib bo'lmadi.\n\n"
            "💰 Balansingizdan pul yechilmadi."
        ),

        "banned": "❌ Siz ushbu botda bloklangansiz.",

        "account_text": (
            "📱 <b>Telegram akkauntlar</b>\n\n"
            "Davlatni tanlang:"
        ),

        "account_order": (
            "✅ Ariza qabul qilindi!\n\n"
            "Administrator tez orada bog'lanadi."
        ),
    }
}

# =========================================================
# БАЗА ДАННЫХ
# =========================================================

def db_connect():
    return sqlite3.connect(DB_FILE)


def init_db():
    conn = db_connect()
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
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT balance, username, name, lang, is_banned "
        "FROM users WHERE user_id = ?",
        (user_id,)
    )

    row = cursor.fetchone()

    if row is None:
        cursor.execute("""
            INSERT INTO users
            (user_id, username, name, balance, lang, is_banned)
            VALUES (?, ?, ?, 0, 'ru', 0)
        """, (
            user_id,
            username or "",
            name or ""
        ))

        conn.commit()

        result = {
            "balance": 0,
            "username": username or "",
            "name": name or "",
            "lang": "ru",
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


def update_balance(user_id, amount):
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (amount, user_id)
    )

    conn.commit()
    conn.close()


def set_language(user_id, lang):
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET lang = ? WHERE user_id = ?",
        (lang, user_id)
    )

    conn.commit()
    conn.close()


def set_ban(user_id, banned):
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET is_banned = ? WHERE user_id = ?",
        (1 if banned else 0, user_id)
    )

    conn.commit()
    conn.close()


def get_all_users():
    conn = db_connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT user_id, username, name, balance, is_banned FROM users"
    )

    rows = cursor.fetchall()

    conn.close()

    return rows

# =========================================================
# ПРОВЕРКА БАНА
# =========================================================

async def is_banned(update: Update):
    user = update.effective_user

    if not user:
        return False

    data = get_user_data(user.id)

    if not data["is_banned"]:
        return False

    lang = data["lang"]

    if update.message:
        await update.message.reply_text(TEXTS[lang]["banned"])

    elif update.callback_query:
        await update.callback_query.answer(
            TEXTS[lang]["banned"],
            show_alert=True
        )

    return True

# =========================================================
# ELDER API
# =========================================================

async def elder_buy_stars(username, amount):
    client_order_id = f"stars_{uuid.uuid4().hex}"

    headers = {
        "X-Api-Key": ELDER_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "username": username.replace("@", "").strip(),
        "amount": amount,
        "client_order_id": client_order_id,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{ELDER_API_URL}/stars/buy",
                headers=headers,
                json=payload
            )

        logger.info(
            f"ELDER STARS: {response.status_code} {response.text}"
        )

        data = response.json()

        if data.get("success") is True:
            return True, data

        return False, data

    except Exception as e:
        logger.error(f" Ошибка подождите 10 секунд и повторите еще раз: {e}")
        return False, None


async def elder_buy_premium(username, months):
    client_order_id = f"premium_{uuid.uuid4().hex}"

    headers = {
        "X-Api-Key": ELDER_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "username": username.replace("@", "").strip(),
        "months": months,
        "client_order_id": client_order_id,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{ELDER_API_URL}/premium/buy",
                headers=headers,
                json=payload
            )

        logger.info(
            f"ELDER PREMIUM: {response.status_code} {response.text}"
        )

        data = response.json()

        if data.get("success") is True:
            return True, data

        return False, data

    except Exception as e:
        logger.error(f"Ошибка подождите 10 секунд и повторите еще раз : {e}")
        return False, None

# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_banned(update):
        return ConversationHandler.END

    context.user_data.clear()

    user = update.effective_user

    data = get_user_data(
        user.id,
        user.username,
        user.first_name
    )

    lang = data["lang"]
    t = TEXTS[lang]

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
        balance=data["balance"]
    )

    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif update.callback_query:
        await update.callback_query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# =========================================================
# ПОПОЛНЕНИЕ
# =========================================================

async def refill_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_banned(update):
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()

    data = get_user_data(query.from_user.id)
    lang = data["lang"]

    await query.message.edit_text(
        TEXTS[lang]["refill_amount"],
        parse_mode="HTML"
    )

    return REFILL_AMOUNT


async def refill_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_user_data(update.effective_user.id)
    lang = data["lang"]

    text = update.message.text.replace(" ", "")

    if not text.isdigit():
        await update.message.reply_text(
            TEXTS[lang]["bad_number"]
        )
        return REFILL_AMOUNT

    amount = int(text)

    if amount < 1000:
        await update.message.reply_text(
            "❌ Минимальная сумма пополнения: 1 000 сум"
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


async def refill_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_banned(update):
        return ConversationHandler.END

    data = get_user_data(update.effective_user.id)
    lang = data["lang"]

    if not update.message.photo:
        await update.message.reply_text(
            TEXTS[lang]["bad_check"]
        )
        return REFILL_CHECK

    amount = context.user_data.get("refill_amount", 0)

    photo_id = update.message.photo[-1].file_id

    user = update.effective_user

    keyboard = [
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

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo_id,
        caption=(
            "💰 <b>Пополнение баланса</b>\n\n"
            f"👤 Пользователь: @{user.username or 'нет'}\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"💵 Сумма: <b>{amount:,} сум</b>"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

    await update.message.reply_text(
        TEXTS[lang]["check_sent"]
    )

    context.user_data.clear()

    return ConversationHandler.END

# =========================================================
# ПОКУПКА
# =========================================================

async def buy_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_banned(update):
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()

    data = get_user_data(query.from_user.id)
    lang = data["lang"]
    t = TEXTS[lang]

    callback = query.data

    if callback == "buy_stars_manual":
        context.user_data["buy_type"] = "stars"

        await query.message.edit_text(
            t["stars_amount"],
            parse_mode="HTML"
        )

        return BUY_AMOUNT

    if callback.startswith("buy_stars_fixed_"):
        amount = int(callback.split("_")[-1])

        context.user_data["buy_type"] = "stars"
        context.user_data["buy_value"] = amount
        context.user_data["buy_price"] = amount * PRICE_PER_STAR

        await query.message.edit_text(
            t["username"],
            parse_mode="HTML"
        )

        return BUY_USERNAME

    if callback.startswith("buy_premium_fixed_"):
        months = int(callback.split("_")[-1])

        context.user_data["buy_type"] = "premium"
        context.user_data["buy_value"] = months
        context.user_data["buy_price"] = PREMIUM_PRICES[months]

        await query.message.edit_text(
            t["username"],
            parse_mode="HTML"
        )

        return BUY_USERNAME

    return ConversationHandler.END


async def buy_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_user_data(update.effective_user.id)
    lang = data["lang"]
    t = TEXTS[lang]

    text = update.message.text.strip()

    if not text.isdigit():
        await update.message.reply_text(
            t["stars_invalid"]
        )
        return BUY_AMOUNT

    amount = int(text)

    if amount < 50 or amount > 10000:
        await update.message.reply_text(
            t["stars_invalid"]
        )
        return BUY_AMOUNT

    price = amount * PRICE_PER_STAR

    if data["balance"] < price:
        await update.message.reply_text(
            t["not_enough"].format(
                price=price,
                balance=data["balance"]
            )
        )

        return ConversationHandler.END

    context.user_data["buy_value"] = amount
    context.user_data["buy_price"] = price

    await update.message.reply_text(
        t["username"],
        parse_mode="HTML"
    )

    return BUY_USERNAME


async def buy_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_user_data(update.effective_user.id)
    lang = data["lang"]
    t = TEXTS[lang]

    username = update.message.text.strip().replace("@", "")

    if not username:
        await update.message.reply_text(
            "❌ Username указан неправильно."
        )
        return BUY_USERNAME

    price = context.user_data["buy_price"]

    if data["balance"] < price:
        await update.message.reply_text(
            t["not_enough"].format(
                price=price,
                balance=data["balance"]
            )
        )

        return ConversationHandler.END

    context.user_data["username"] = username

    buy_type = context.user_data["buy_type"]
    value = context.user_data["buy_value"]

    if buy_type == "stars":
        product = f"{value} Telegram Stars"
    else:
        product = f"Telegram Premium на {value} месяцев"

    keyboard = [
        [
            InlineKeyboardButton(
                t["confirm_button"],
                callback_data="confirm_buy"
            )
        ],
        [
            InlineKeyboardButton(
                t["btn_cancel"],
                callback_data="cancel_buy"
            )
        ]
    ]

    await update.message.reply_text(
        t["confirm"].format(
            product=product,
            username=username,
            price=price
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

    return BUY_CONFIRM


async def buy_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_banned(update):
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()

    if query.data == "cancel_buy":
        await query.message.edit_text("❌ Покупка отменена.")
        context.user_data.clear()
        return ConversationHandler.END

    data = get_user_data(query.from_user.id)
    lang = data["lang"]
    t = TEXTS[lang]

    buy_type = context.user_data["buy_type"]
    value = context.user_data["buy_value"]
    username = context.user_data["username"]
    price = context.user_data["buy_price"]

    if data["balance"] < price:
        await query.message.edit_text(
            t["not_enough"].format(
                price=price,
                balance=data["balance"]
            )
        )

        context.user_data.clear()

        return ConversationHandler.END

    await query.message.edit_text(
        t["processing"]
    )

    # =====================================================
    # АВТОМАТИЧЕСКИЙ ЗАКАЗ В ELDER
    # =====================================================

    if buy_type == "stars":
        success, response = await elder_buy_stars(
            username,
            value
        )

        product = f"{value} Telegram Stars"

    else:
        success, response = await elder_buy_premium(
            username,
            value
        )

        product = f"Telegram Premium {value} месяцев"

    # =====================================================
    # ЕСЛИ ELDER УСПЕШНО ВЫПОЛНИЛ
    # =====================================================

    if success:
        update_balance(
            query.from_user.id,
            -price
        )

        await query.message.edit_text(
            t["order_success"].format(
                product=product,
                username=username
            ),
            parse_mode="HTML"
        )

        order_id = ""

        if response:
            order_data = response.get("data", {})
            order_id = order_data.get("order_id", "")

        await context.bot.send_message(
            ADMIN_ID,
            "🚀 <b>АВТОМАТИЧЕСКИЙ ЗАКАЗ ELDER</b>\n\n"
            f"👤 ID: <code>{query.from_user.id}</code>\n"
            f"📦 {product}\n"
            f"👤 Получатель: @{username}\n"
            f"💰 Цена: {price:,} сум\n"
            f"🧾 Elder Order ID: <code>{order_id}</code>",
            parse_mode="HTML"
        )

    else:
        await query.message.edit_text(
            t["order_error"]
        )

        logger.error(
            f"Заказ не выполнен: {response}"
        )

    context.user_data.clear()

    return ConversationHandler.END

# =========================================================
# МЕНЮ
# =========================================================

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_banned(update):
        return

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = get_user_data(user_id)

    lang = data["lang"]
    t = TEXTS[lang]

    callback = query.data

    # -------------------------
    # НАЗАД
    # -------------------------

    if callback == "back_main":
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

        await query.message.edit_text(
            t["welcome"].format(
                name=query.from_user.first_name,
                balance=data["balance"]
            ),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # -------------------------
    # МАГАЗИН
    # -------------------------

    if callback == "main_shop":
        keyboard = [
            [
                InlineKeyboardButton(
                    t["stars_category"],
                    callback_data="shop_stars"
                )
            ],
            [
                InlineKeyboardButton(
                    t["premium_category"],
                    callback_data="shop_premium"
                )
            ],
            [
                InlineKeyboardButton(
                    t["accounts_category"],
                    callback_data="shop_accounts"
                )
            ],
            [
                InlineKeyboardButton(
                    t["btn_back"],
                    callback_data="back_main"
                )
            ]
        ]

        await query.message.edit_text(
            t["shop"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return

    # -------------------------
    # STARS
    # -------------------------

    if callback == "shop_stars":
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
                    "⭐ 200 Stars — 42 000 сум",
                    callback_data="buy_stars_fixed_200"
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
        ]

        await query.message.edit_text(
            t["stars_text"].format(
                price=PRICE_PER_STAR
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return

    # -------------------------
    # PREMIUM
    # -------------------------

    if callback == "shop_premium":
        keyboard = [
            [
                InlineKeyboardButton(
                    "🚀 3 месяца — 165 000 сум",
                    callback_data="buy_premium_fixed_3"
                )
            ],
            [
                InlineKeyboardButton(
                    "🚀 6 месяцев — 222 000 сум",
                    callback_data="buy_premium_fixed_6"
                )
            ],
            [
                InlineKeyboardButton(
                    "🚀 12 месяцев — 406 000 сум",
                    callback_data="buy_premium_fixed_12"
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
            t["premium_text"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return

    # -------------------------
    # АККАУНТЫ
    # -------------------------

    if callback == "shop_accounts":
        keyboard = [
            [
                InlineKeyboardButton(
                    "🇺🇿 Узбекистан — 13 000 сум",
                    callback_data="account_uz"
                )
            ],
            [
                InlineKeyboardButton(
                    "🇨🇴 Колумбия — 6 500 сум",
                    callback_data="account_co"
                )
            ],
            [
                InlineKeyboardButton(
                    "🇬🇧 Великобритания — 9 000 сум",
                    callback_data="account_uk"
                )
            ],
            [
                InlineKeyboardButton(
                    "🇺🇸 Америка — 8 000 сум",
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
            t["account_text"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return

    # -------------------------
    # АККАУНТ
    # -------------------------

    if callback.startswith("account_"):
        country = callback.replace("account_", "")

        await context.bot.send_message(
            ADMIN_ID,
            "📱 <b>ЗАКАЗ АККАУНТА</b>\n\n"
            f"👤 ID: <code>{user_id}</code>\n"
            f"🌍 Страна: {country.upper()}\n"
            f"👤 Username: @{query.from_user.username or 'нет'}",
            parse_mode="HTML"
        )

        await query.message.edit_text(
            t["account_order"]
        )

        return

    # -------------------------
    # ПРОФИЛЬ
    # -------------------------

    if callback == "main_profile":
        keyboard = [
            [
                InlineKeyboardButton(
                    "🇺🇿 O'zbekcha",
                    callback_data="lang_uz"
                ),
                InlineKeyboardButton(
                    "🇷🇺 Русский",
                    callback_data="lang_ru"
                )
            ],
            [
                InlineKeyboardButton(
                    t["btn_back"],
                    callback_data="back_main"
                )
            ]
        ]

        await query.message.edit_text(
            t["profile"].format(
                user_id=user_id,
                balance=data["balance"]
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return

    # -------------------------
    # ЯЗЫК
    # -------------------------

    if callback.startswith("lang_"):
        new_lang = callback.replace("lang_", "")

        set_language(user_id, new_lang)

        data = get_user_data(user_id)
        t = TEXTS[new_lang]

        keyboard = [
            [
                InlineKeyboardButton(
                    "🇺🇿 O'zbekcha",
                    callback_data="lang_uz"
                ),
                InlineKeyboardButton(
                    "🇷🇺 Русский",
                    callback_data="lang_ru"
                )
            ],
            [
                InlineKeyboardButton(
                    t["btn_back"],
                    callback_data="back_main"
                )
            ]
        ]

        await query.message.edit_text(
            t["profile"].format(
                user_id=user_id,
                balance=data["balance"]
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

# =========================================================
# АДМИНКА
# =========================================================

def admin_only(func):
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        if update.effective_user.id != ADMIN_ID:
            if update.callback_query:
                await update.callback_query.answer(
                    "⛔ Только для администратора!",
                    show_alert=True
                )
            return

        return await func(update, context, *args, **kwargs)

    return wrapper


@admin_only
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(
                "👥 Пользователи",
                callback_data="admin_users"
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
        "🛠 <b>Панель администратора</b>\n\n"
        "/setbal ID СУММА — изменить баланс\n"
        "/ban ID — заблокировать\n"
        "/unban ID — разблокировать\n"
        "/msg ID ТЕКСТ — написать пользователю",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
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

        text = f"👥 <b>Пользователи: {len(users)}</b>\n\n"

        for user_id, username, name, balance, banned in users[:30]:
            text += (
                f"🆔 <code>{user_id}</code>\n"
                f"👤 @{username or 'нет'}\n"
                f"💰 {balance:,} сум\n"
                f"{'⛔ Забанен' if banned else '🟢 Активен'}\n"
                "────────────\n"
            )

        await query.message.edit_text(
            text,
            parse_mode="HTML"
        )


@admin_only
async def setbal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Использование: /setbal ID СУММА"
        )
        return

    user_id = int(context.args[0])
    amount = int(context.args[1])

    update_balance(user_id, amount)

    data = get_user_data(user_id)

    await update.message.reply_text(
        f"✅ Баланс изменён.\n\n"
        f"🆔 ID: {user_id}\n"
        f"💰 Новый баланс: {data['balance']:,} сум"
    )

    try:
        await context.bot.send_message(
            user_id,
            f"🔔 Баланс изменён администратором.\n"
            f"💰 Текущий баланс: {data['balance']:,} сум"
        )
    except Exception:
        pass


@admin_only
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return

    user_id = int(context.args[0])

    set_ban(user_id, True)

    await update.message.reply_text(
        f"⛔ Пользователь {user_id} заблокирован."
    )


@admin_only
async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return

    user_id = int(context.args[0])

    set_ban(user_id, False)

    await update.message.reply_text(
        f"🟢 Пользователь {user_id} разблокирован."
    )


@admin_only
async def msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        return

    user_id = int(context.args[0])
    text = " ".join(context.args[1:])

    try:
        await context.bot.send_message(
            user_id,
            f"✉️ <b>Сообщение от администратора:</b>\n\n{text}",
            parse_mode="HTML"
        )

        await update.message.reply_text(
            "✅ Сообщение отправлено."
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка: {e}"
        )

# =========================================================
# ПОПОЛНЕНИЕ АДМИН
# =========================================================

@admin_only
async def payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("pay_yes_"):
        parts = data.split("_")

        user_id = int(parts[2])
        amount = int(parts[3])

        update_balance(user_id, amount)

        await query.message.edit_caption(
            "🟢 <b>Пополнение одобрено</b>",
            parse_mode="HTML"
        )

        try:
            await context.bot.send_message(
                user_id,
                f"🎉 Баланс пополнен!\n"
                f"💰 Сумма: {amount:,} сум"
            )
        except Exception:
            pass

    elif data.startswith("pay_no_"):
        await query.message.edit_caption(
            "🔴 <b>Пополнение отклонено</b>",
            parse_mode="HTML"
        )

# =========================================================
# WEB SERVER ДЛЯ RENDER
# =========================================================

class WebHandler(BaseHTTPRequestHandler):

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
        WebHandler
    )

    logger.info(
        f"Web server started on port {port}"
    )

    server.serve_forever()

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

    # -------------------------
    # ПОПОЛНЕНИЕ
    # -------------------------

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
                        filters.PHOTO,
                        refill_check
                    )
                ],
            },
            fallbacks=[
                CommandHandler(
                    "start",
                    start
                )
            ],
        )
    )

    # -------------------------
    # ПОКУПКА
    # -------------------------

    app.add_handler(
        ConversationHandler(
            entry_points=[
                CallbackQueryHandler(
                    buy_start,
                    pattern=(
                        "^buy_stars_manual$|"
                        "^buy_stars_fixed_[0-9]+$|"
                        "^buy_premium_fixed_(3|6|12)$"
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
                        pattern="^confirm_buy$|^cancel_buy$"
                    )
                ],
            },
            fallbacks=[
                CommandHandler(
                    "start",
                    start
                )
            ],
        )
    )

    # -------------------------
    # АДМИН
    # -------------------------

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
            pattern="^admin_"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            payment_callback,
            pattern="^pay_"
        )
    )

    # -------------------------
    # START
    # -------------------------

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    # -------------------------
    # МЕНЮ
    # -------------------------

    app.add_handler(
        CallbackQueryHandler(
            menu_callback,
            pattern=(
                "^main_shop$|"
                "^main_profile$|"
                "^shop_stars$|"
                "^shop_premium$|"
                "^shop_accounts$|"
                "^lang_(ru|uz)$|"
                "^account_.*$|"
                "^back_main$"
            )
        )
    )

    logger.info("🚀 БОТ ЗАПУЩЕН!")

    app.run_polling()


if __name__ == "__main__":
    main()