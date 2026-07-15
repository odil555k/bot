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


# ============================================================
# ЛОГИРОВАНИЕ
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)


# ============================================================
# НАСТРОЙКИ
# ============================================================

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])

ELDER_API_KEY = os.environ["ELDER_API_KEY"]
ELDER_API_URL = "https://asosiy.elder.uz/api"

CARD_NUMBER = "5614 6835 8985 1641"

DB_FILE = "bot_database.db"

DEFAULT_LANG = "ru"

PRICE_PER_STAR = 210

PREMIUM_PRICES = {
    3: 165000,
    6: 222000,
    12: 406000,
}


# ============================================================
# СОСТОЯНИЯ ДИАЛОГОВ
# ============================================================

REFILL_AMOUNT, REFILL_CHECK = range(2)

BUY_USERNAME, BUY_CONFIRM = range(2, 4)


# ============================================================
# ТЕКСТЫ
# ============================================================

TEXTS = {
    "ru": {
        "welcome":
            "👋 Привет, {name}!\n\n"
            "Добро пожаловать в магазин Telegram Stars & Premium.\n\n"
            "💰 Ваш баланс: {balance:,} сум",

        "btn_shop": "🛍 Купить услуги",
        "btn_refill": "💳 Пополнить баланс",
        "btn_profile": "👤 Мой кабинет",
        "btn_back": "⬅️ Назад",
        "btn_cancel": "❌ Отмена",

        "profile_text":
            "👤 <b>Личный кабинет</b>\n\n"
            "🆔 Ваш ID: <code>{user_id}</code>\n"
            "💰 Баланс: {balance:,} сум\n\n"
            "🌐 Сменить язык / Tilni o'zgartirish:",

        "shop_main": "🛍 <b>Выберите категорию товара:</b>",

        "shop_stars_cat": "💎 Telegram Stars",
        "shop_prem_cat": "🌟 Telegram Premium",
        "shop_acc_cat": "📱 Купить Telegram аккаунт",

        "stars_desc":
            "💎 <b>Telegram Stars</b>\n\n"
            "💵 Цена: {price} сум за 1 ⭐",

        "stars_manual": "✏️ Ввести количество вручную",

        "prem_desc":
            "🌟 <b>Цены на Telegram Premium:</b>\n\n"
            "🔹 3 месяца — 165,000 сум\n"
            "🔹 6 месяцев — 222,000 сум\n"
            "🔹 12 месяцев — 406,000 сум",

        "refill_start":
            "💳 Введите сумму пополнения в сумах\n\n"
            "Например: <code>50000</code>",

        "refill_bad_num":
            "❌ Введите корректную сумму числом.",

        "refill_invoice":
            "💳 <b>Заявка на пополнение</b>\n\n"
            "💰 Сумма: <b>{amount:,} сум</b>\n\n"
            "Переведите ровно эту сумму на карту:\n"
            "<code>{card}</code>\n\n"
            "После оплаты отправьте фото или скриншот чека.",

        "refill_bad_photo":
            "❌ Отправьте именно фото или скриншот чека.",

        "refill_done":
            "⏳ Чек отправлен администратору на проверку.",

        "buy_username_enter":
            "✏️ Введите Telegram username получателя\n\n"
            "Без знака @\n"
            "Например: <code>durov</code>",

        "buy_confirm_title":
            "📝 <b>Подтверждение покупки</b>\n\n"
            "📦 Товар: {product}\n"
            "👤 Получатель: @{username}\n"
            "💰 Стоимость: <b>{price:,} сум</b>\n\n"
            "Подтвердить покупку?",

        "buy_confirm_btn": "✅ Купить",

        "not_enough":
            "❌ Недостаточно средств.\n\n"
            "Стоимость: {price:,} сум\n"
            "Ваш баланс: {balance:,} сум",

        "banned_msg":
            "❌ Вы заблокированы в этом боте.",

        "acc_desc":
            "📱 <b>Выберите страну номера:</b>",

        "acc_uz":
            "🇺🇿 Страна: Узбекистан — 13,000 сум",

        "acc_co":
            "🇨🇴 Страна: Колумбия — 6,500 сум",

        "acc_uk":
            "🇬🇧 Страна: Великобритания — 9,000 сум",

        "acc_us":
            "🇺🇸 Страна: Америка — 8,000 сум",
    },

    "uz": {
        "welcome":
            "👋 Salom, {name}!\n\n"
            "Telegram Stars & Premium do'koniga xush kelibsiz.\n\n"
            "💰 Balansingiz: {balance:,} so'm",

        "btn_shop": "🛍 Xizmatlarni sotib olish",
        "btn_refill": "💳 Balansni to'ldirish",
        "btn_profile": "👤 Shaxsiy kabinet",
        "btn_back": "⬅️ Ortga",
        "btn_cancel": "❌ Bekor qilish",

        "profile_text":
            "👤 <b>Shaxsiy kabinet</b>\n\n"
            "🆔 Sizning ID: <code>{user_id}</code>\n"
            "💰 Balans: {balance:,} so'm\n\n"
            "🌐 Tilni o'zgartirish / Сменить язык:",

        "shop_main": "🛍 <b>Kategoriyani tanlang:</b>",

        "shop_stars_cat": "💎 Telegram Stars",
        "shop_prem_cat": "🌟 Telegram Premium",
        "shop_acc_cat": "📱 Telegram akkaunt sotib olish",

        "stars_desc":
            "💎 <b>Telegram Stars</b>\n\n"
            "💵 Narx: 1 ⭐ uchun {price} so'm",

        "stars_manual": "✏️ Miqdorni qo'lda kiritish",

        "prem_desc":
            "🌟 <b>Telegram Premium narxlari:</b>\n\n"
            "🔹 3 oy — 165,000 so'm\n"
            "🔹 6 oy — 222,000 so'm\n"
            "🔹 12 oy — 406,000 so'm",

        "refill_start":
            "💳 To'ldirish summasini so'mda kiriting\n\n"
            "Masalan: <code>50000</code>",

        "refill_bad_num":
            "❌ To'g'ri summani kiriting.",

        "refill_invoice":
            "💳 <b>Balans to'ldirish</b>\n\n"
            "💰 Summa: <b>{amount:,} so'm</b>\n\n"
            "Ushbu summani kartaga o'tkazing:\n"
            "<code>{card}</code>\n\n"
            "To'lovdan keyin chek rasmini yuboring.",

        "refill_bad_photo":
            "❌ Chek rasmini yuboring.",

        "refill_done":
            "⏳ Chek administratorga tekshirish uchun yuborildi.",

        "buy_username_enter":
            "✏️ Qabul qiluvchining Telegram username'ini kiriting\n\n"
            "@ belgisiz\n"
            "Masalan: <code>durov</code>",

        "buy_confirm_title":
            "📝 <b>Xaridni tasdiqlash</b>\n\n"
            "📦 Mahsulot: {product}\n"
            "👤 Qabul qiluvchi: @{username}\n"
            "💰 Narxi: <b>{price:,} so'm</b>\n\n"
            "Xaridni tasdiqlaysizmi?",

        "buy_confirm_btn": "✅ Sotib olish",

        "not_enough":
            "❌ Mablag' yetarli emas.\n\n"
            "Narxi: {price:,} so'm\n"
            "Balansingiz: {balance:,} so'm",

        "banned_msg":
            "❌ Siz ushbu botda bloklangansiz.",

        "acc_desc":
            "📱 <b>Raqam davlatini tanlang:</b>",

        "acc_uz":
            "🇺🇿 Davlat: O'zbekiston — 13,000 so'm",

        "acc_co":
            "🇨🇴 Davlat: Kolumbiya — 6,500 so'm",

        "acc_uk":
            "🇬🇧 Davlat: Buyuk Britaniya — 9,000 so'm",

        "acc_us":
            "🇺🇸 Davlat: Amerika — 8,000 so'm",
    }
}


# ============================================================
# БАЗА ДАННЫХ
# ============================================================

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
        """
    )

    rows = cursor.fetchall()

    conn.close()

    return rows


# ============================================================
# ПРОВЕРКА БАНА
# ============================================================

async def is_user_banned(update: Update):
    user = update.effective_user

    if not user:
        return False

    data = get_user_data(user.id)

    if not data["is_banned"]:
        return False

    lang = data["lang"]

    if lang not in TEXTS:
        lang = "ru"

    text = TEXTS[lang]["banned_msg"]

    if update.message:
        await update.message.reply_text(text)

    elif update.callback_query:
        await update.callback_query.answer(
            text,
            show_alert=True
        )

    return True


# ============================================================
# ADMIN DECORATOR
# ============================================================

def admin_required(func):
    @wraps(func)
    async def wrapped(update, context, *args, **kwargs):

        if update.effective_user.id != ADMIN_ID:

            if update.callback_query:
                await update.callback_query.answer(
                    "⛔ Только для администратора!",
                    show_alert=True
                )

            return

        return await func(update, context, *args, **kwargs)

    return wrapped


# ============================================================
# ELDER API
# ============================================================

async def send_order_to_elder(
        product_type: str,
        value: int,
        username: str,
        client_order_id: str
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

            logger.info(
                f"ELDER REQUEST: {url} | {payload}"
            )

            response = await client.post(
                url,
                headers=headers,
                json=payload,
                timeout=30
            )

            logger.info(
                f"ELDER RESPONSE: "
                f"{response.status_code} | {response.text}"
            )

            try:
                result = response.json()
            except Exception:
                return False, "Некорректный ответ API"

            if response.status_code == 200 and result.get("success") is True:
                return True, result

            error_code = result.get("error_code", "UNKNOWN_ERROR")

            return False, error_code

    except Exception as e:

        logger.error(
            f"ELDER API ERROR: {e}"
        )

        return False, str(e)


# ============================================================
# МЕНЮ
# ============================================================

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

    return ConversationHandler.END


# ============================================================
# ПРОФИЛЬ
# ============================================================

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    if await is_user_banned(update):
        return

    data = get_user_data(query.from_user.id)

    t = TEXTS[data["lang"]]

    text = t["profile_text"].format(
        user_id=query.from_user.id,
        balance=data["balance"]
    )

    keyboard = [
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
                t["btn_back"],
                callback_data="back_to_main"
            )
        ]
    ]

    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )


# ============================================================
# ПОПОЛНЕНИЕ БАЛАНСА
# ============================================================

async def refill_start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    data = get_user_data(query.from_user.id)

    t = TEXTS[data["lang"]]

    await query.message.edit_text(
        t["refill_start"],
        parse_mode="HTML"
    )

    return REFILL_AMOUNT


async def refill_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):

    data = get_user_data(update.effective_user.id)

    t = TEXTS[data["lang"]]

    text = update.message.text.replace(" ", "")

    if not text.isdigit():

        await update.message.reply_text(
            t["refill_bad_num"]
        )

        return REFILL_AMOUNT

    amount = int(text)

    if amount <= 0:

        await update.message.reply_text(
            t["refill_bad_num"]
        )

        return REFILL_AMOUNT

    context.user_data["refill_amount"] = amount

    await update.message.reply_text(
        t["refill_invoice"].format(
            amount=amount,
            card=CARD_NUMBER
        ),
        parse_mode="HTML"
    )

    return REFILL_CHECK


async def refill_check(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if await is_user_banned(update):
        return ConversationHandler.END

    data = get_user_data(update.effective_user.id)

    t = TEXTS[data["lang"]]

    if not update.message:

        return REFILL_CHECK

    if not update.message.photo and not update.message.document:

        await update.message.reply_text(
            t["refill_bad_photo"]
        )

        return REFILL_CHECK

    if update.message.document:

        if not update.message.document.mime_type:
            await update.message.reply_text(
                t["refill_bad_photo"]
            )
            return REFILL_CHECK

        if not update.message.document.mime_type.startswith("image/"):

            await update.message.reply_text(
                t["refill_bad_photo"]
            )

            return REFILL_CHECK

    amount = context.user_data.get("refill_amount", 0)

    user = update.effective_user

    if update.message.photo:

        file_id = update.message.photo[-1].file_id

    else:

        file_id = update.message.document.file_id

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
        "💰 <b>Новое пополнение</b>\n\n"
        f"👤 Пользователь: @{user.username or 'нет username'}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"💵 Сумма: <b>{amount:,} сум</b>"
    )

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=file_id,
        caption=caption,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

    await update.message.reply_text(
        t["refill_done"]
    )

    context.user_data.clear()

    return ConversationHandler.END


# ============================================================
# ПОКУПКА ТОВАРОВ
# ============================================================

async def buy_product_start(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    data = get_user_data(query.from_user.id)

    t = TEXTS[data["lang"]]

    callback = query.data

    # --------------------------------------------------------
    # РУЧНОЙ ВВОД STARS
    # --------------------------------------------------------

    if callback == "buy_stars_manual":

        context.user_data["product_type"] = "stars"

        await query.message.edit_text(
            "✏️ Введите количество Stars\n\n"
            "Минимум: 50\n"
            "Максимум: 10000"
        )

        return BUY_USERNAME

    # --------------------------------------------------------
    # STARS
    # --------------------------------------------------------

    if callback.startswith("buy_stars_fixed_"):

        amount = int(
            callback.split("_")[-1]
        )

        price = amount * PRICE_PER_STAR

        context.user_data["product_type"] = "stars"
        context.user_data["product_value"] = amount
        context.user_data["product_price"] = price

        if data["balance"] < price:

            await query.message.edit_text(
                t["not_enough"].format(
                    price=price,
                    balance=data["balance"]
                )
            )

            return ConversationHandler.END

        await query.message.edit_text(
            t["buy_username_enter"],
            parse_mode="HTML"
        )

        return BUY_USERNAME

    # --------------------------------------------------------
    # PREMIUM
    # --------------------------------------------------------

    if callback.startswith("buy_prem_fixed_"):

        months = int(
            callback.split("_")[-1]
        )

        price = PREMIUM_PRICES[months]

        context.user_data["product_type"] = "premium"
        context.user_data["product_value"] = months
        context.user_data["product_price"] = price

        if data["balance"] < price:

            await query.message.edit_text(
                t["not_enough"].format(
                    price=price,
                    balance=data["balance"]
                )
            )

            return ConversationHandler.END

        await query.message.edit_text(
            t["buy_username_enter"],
            parse_mode="HTML"
        )

        return BUY_USERNAME

    return ConversationHandler.END


async def buy_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):

    data = get_user_data(update.effective_user.id)

    t = TEXTS[data["lang"]]

    text = update.message.text.strip()

    if not text.isdigit():

        await update.message.reply_text(
            "❌ Введите количество Stars числом."
        )

        return BUY_USERNAME

    amount = int(text)

    if amount < 50 or amount > 10000:

        await update.message.reply_text(
            "❌ Stars можно купить от 50 до 10000."
        )

        return BUY_USERNAME

    price = amount * PRICE_PER_STAR

    if data["balance"] < price:

        await update.message.reply_text(
            t["not_enough"].format(
                price=price,
                balance=data["balance"]
            )
        )

        return ConversationHandler.END

    context.user_data["product_type"] = "stars"
    context.user_data["product_value"] = amount
    context.user_data["product_price"] = price

    await update.message.reply_text(
        t["buy_username_enter"],
        parse_mode="HTML"
    )

    return BUY_CONFIRM


async def buy_username(update: Update, context: ContextTypes.DEFAULT_TYPE):

    data = get_user_data(update.effective_user.id)

    t = TEXTS[data["lang"]]

    username = update.message.text.strip().replace("@", "")

    if not username:

        await update.message.reply_text(
            "❌ Введите username."
        )

        return BUY_USERNAME

    context.user_data["target_username"] = username

    product_type = context.user_data["product_type"]
    value = context.user_data["product_value"]
    price = context.user_data["product_price"]

    if product_type == "stars":

        product_name = f"{value} Telegram Stars"

    else:

        product_name = f"Telegram Premium — {value} месяцев"

    text = t["buy_confirm_title"].format(
        product=product_name,
        username=username,
        price=price
    )

    keyboard = [
        [
            InlineKeyboardButton(
                t["buy_confirm_btn"],
                callback_data="confirm_final_buy"
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

    data = get_user_data(query.from_user.id)

    product_type = context.user_data.get("product_type")
    value = context.user_data.get("product_value")
    price = context.user_data.get("product_price")
    username = context.user_data.get("target_username")

    if not product_type or not value or not price or not username:

        await query.message.edit_text(
            "❌ Ошибка заказа. Начните покупку заново."
        )

        context.user_data.clear()

        return ConversationHandler.END

    if data["balance"] < price:

        await query.message.edit_text(
            "❌ Недостаточно средств."
        )

        context.user_data.clear()

        return ConversationHandler.END

    await query.message.edit_text(
        "🔄 <b>Обрабатываем заказ...</b>\n\n"
        "Пожалуйста, подождите.",
        parse_mode="HTML"
    )

    client_order_id = (
        f"{query.from_user.id}_"
        f"{uuid.uuid4().hex[:12]}"
    )

    success, result = await send_order_to_elder(
        product_type=product_type,
        value=value,
        username=username,
        client_order_id=client_order_id
    )

    if success:

        update_user_balance(
            query.from_user.id,
            -price
        )

        if product_type == "stars":

            product_name = f"{value} Stars"

        else:

            product_name = f"Premium {value} месяцев"

        await query.message.edit_text(
            "✅ <b>Заказ успешно выполнен!</b>\n\n"
            f"📦 Товар: {product_name}\n"
            f"👤 Получатель: @{username}\n\n"
            "🚀 Товар автоматически отправлен.",
            parse_mode="HTML"
        )

        try:

            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "🚀 <b>Автоматический заказ Elder API</b>\n\n"
                    f"👤 Клиент ID: <code>{query.from_user.id}</code>\n"
                    f"📦 Товар: {product_name}\n"
                    f"👤 Получатель: @{username}\n"
                    f"🆔 Order ID: {client_order_id}"
                ),
                parse_mode="HTML"
            )

        except Exception as e:

            logger.error(
                f"Ошибка уведомления админа: {e}"
            )

    else:

        await query.message.edit_text(
            "❌ <b>Не удалось выполнить заказ.</b>\n\n"
            f"Причина: <code>{result}</code>\n\n"
            "💰 Деньги НЕ списаны.",
            parse_mode="HTML"
        )

    context.user_data.clear()

    return ConversationHandler.END


# ============================================================
# АККАУНТЫ
# ============================================================

async def account_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    data = get_user_data(query.from_user.id)

    t = TEXTS[data["lang"]]

    keyboard = [
        [
            InlineKeyboardButton(
                t["acc_uz"],
                callback_data="buy_acc_uz_13000"
            )
        ],
        [
            InlineKeyboardButton(
                t["acc_co"],
                callback_data="buy_acc_co_6500"
            )
        ],
        [
            InlineKeyboardButton(
                t["acc_uk"],
                callback_data="buy_acc_uk_9000"
            )
        ],
        [
            InlineKeyboardButton(
                t["acc_us"],
                callback_data="buy_acc_us_8000"
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
        t["acc_desc"],
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )


async def buy_account(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    data = get_user_data(query.from_user.id)

    callback = query.data

    parts = callback.split("_")

    country_code = parts[2]
    price = int(parts[3])

    countries = {
        "uz": "Узбекистан",
        "co": "Колумбия",
        "uk": "Великобритания",
        "us": "Америка",
    }

    country_name = countries.get(
        country_code,
        country_code.upper()
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

    await query.message.edit_text(
        "✅ <b>Заявка принята!</b>\n\n"
        f"🌍 Страна: {country_name}\n"
        f"💰 Цена: {price:,} сум\n\n"
        "📩 Данные аккаунта будут отправлены вам в личные сообщения.",
        parse_mode="HTML"
    )

    try:

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "📱 <b>Новый заказ аккаунта</b>\n\n"
                f"🌍 Страна: {country_name}\n"
                f"💰 Цена: {price:,} сум\n"
                f"👤 Клиент: @{query.from_user.username or 'нет username'}\n"
                f"🆔 ID: <code>{query.from_user.id}</code>"
            ),
            parse_mode="HTML"
        )

    except Exception as e:

        logger.error(
            f"Ошибка отправки заказа аккаунта админу: {e}"
        )


# ============================================================
# ГЛАВНЫЙ CALLBACK HANDLER
# ============================================================

async def main_callback_handler(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
):

    if await is_user_banned(update):

        return

    query = update.callback_query

    await query.answer()

    data = get_user_data(query.from_user.id)

    t = TEXTS[data["lang"]]

    callback = query.data

    # --------------------------------------------------------
    # НАЗАД
    # --------------------------------------------------------

    if callback == "back_to_main":

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

    # --------------------------------------------------------
    # ПРОФИЛЬ
    # --------------------------------------------------------

    if callback == "main_profile":

        await show_profile(update, context)

        return

    # --------------------------------------------------------
    # ЯЗЫК
    # --------------------------------------------------------

    if callback.startswith("setlang_"):

        lang = callback.split("_")[1]

        update_user_lang(
            query.from_user.id,
            lang
        )

        await show_profile(update, context)

        return

    # --------------------------------------------------------
    # МАГАЗИН
    # --------------------------------------------------------

    if callback == "main_shop":

        keyboard = [
            [
                InlineKeyboardButton(
                    t["shop_stars_cat"],
                    callback_data="shop_stars"
                )
            ],
            [
                InlineKeyboardButton(
                    t["shop_prem_cat"],
                    callback_data="shop_premium"
                )
            ],
            [
                InlineKeyboardButton(
                    t["shop_acc_cat"],
                    callback_data="shop_acc"
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

    # --------------------------------------------------------
    # STARS
    # --------------------------------------------------------

    if callback == "shop_stars":

        keyboard = [
            [
                InlineKeyboardButton(
                    "⭐ 50 Stars (10,500 сум)",
                    callback_data="buy_stars_fixed_50"
                )
            ],
            [
                InlineKeyboardButton(
                    "⭐ 100 Stars (21,000 сум)",
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

    # --------------------------------------------------------
    # PREMIUM
    # --------------------------------------------------------

    if callback == "shop_premium":

        keyboard = [
            [
                InlineKeyboardButton(
                    "🚀 3 мес / oy (165k)",
                    callback_data="buy_prem_fixed_3"
                )
            ],
            [
                InlineKeyboardButton(
                    "🚀 6 мес / oy (222k)",
                    callback_data="buy_prem_fixed_6"
                )
            ],
            [
                InlineKeyboardButton(
                    "🚀 12 мес / oy (406k)",
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
            t["prem_desc"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

        return

    # --------------------------------------------------------
    # АККАУНТЫ
    # --------------------------------------------------------

    if callback == "shop_acc":

        await account_menu(update, context)

        return


# ============================================================
# АДМИНКА
# ============================================================

@admin_required
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [
            InlineKeyboardButton(
                "👥 Список пользователей",
                callback_data="admin_list_0"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Закрыть",
                callback_data="admin_close"
            )
        ]
    ]

    text = (
        "🛠 <b>Панель администратора</b>\n\n"
        "Команды:\n\n"
        "👉 <code>/setbal ID СУММА</code>\n"
        "👉 <code>/ban ID</code>\n"
        "👉 <code>/unban ID</code>\n"
        "👉 <code>/msg ID ТЕКСТ</code>"
    )

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )


@admin_required
async def admin_callback_handler(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    if query.data == "admin_close":

        await query.message.delete()

        return

    if query.data.startswith("admin_list_"):

        page = int(
            query.data.split("_")[-1]
        )

        users = get_all_users()

        per_page = 15

        start = page * per_page
        end = start + per_page

        users_page = users[start:end]

        total_pages = (
            len(users) + per_page - 1
        ) // per_page

        text = (
            f"👥 <b>Пользователи</b>\n"
            f"Страница {page + 1}/{total_pages}\n\n"
        )

        for user_id, username, name, balance, banned in users_page:

            text += (
                f"🆔 <code>{user_id}</code>\n"
                f"👤 @{username or 'нет'}\n"
                f"💰 {balance:,} сум\n"
                f"🚫 {'Да' if banned else 'Нет'}\n"
                "──────────────\n"
            )

        buttons = []

        if page > 0:

            buttons.append(
                InlineKeyboardButton(
                    "⬅️ Назад",
                    callback_data=f"admin_list_{page - 1}"
                )
            )

        if end < len(users):

            buttons.append(
                InlineKeyboardButton(
                    "Вперёд ➡️",
                    callback_data=f"admin_list_{page + 1}"
                )
            )

        keyboard = []

        if buttons:

            keyboard.append(buttons)

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


@admin_required
async def cmd_setbal(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
):

    if len(context.args) < 2:

        await update.message.reply_text(
            "❌ Использование:\n/setbal ID СУММА"
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

    data = get_user_data(user_id)

    await update.message.reply_text(
        f"✅ Баланс изменён.\n\n"
        f"🆔 ID: {user_id}\n"
        f"💰 Текущий баланс: {data['balance']:,} сум"
    )

    try:

        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"🔔 Баланс изменён администратором.\n\n"
                f"💰 Текущий баланс: {data['balance']:,} сум"
            )
        )

    except Exception:

        pass


@admin_required
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


@admin_required
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


@admin_required
async def cmd_msg(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
):

    if len(context.args) < 2:

        return

    user_id = context.args[0]

    if not user_id.isdigit():

        return

    text = " ".join(
        context.args[1:]
    )

    try:

        await context.bot.send_message(
            chat_id=int(user_id),
            text=(
                "✉️ <b>Сообщение от администратора:</b>\n\n"
                f"{text}"
            ),
            parse_mode="HTML"
        )

        await update.message.reply_text(
            "✅ Сообщение отправлено."
        )

    except Exception as e:

        await update.message.reply_text(
            f"❌ Ошибка: {e}"
        )


@admin_required
async def admin_pay_buttons(
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
                chat_id=user_id,
                text=(
                    "🎉 <b>Баланс пополнен!</b>\n\n"
                    f"💰 Сумма: {amount:,} сум"
                ),
                parse_mode="HTML"
            )

        except Exception:

            pass

    elif query.data.startswith("adm_pay_no_"):

        await query.message.edit_caption(
            "🔴 Пополнение отклонено."
        )


# ============================================================
# ВЕБ-СЕРВЕР ДЛЯ RENDER
# ============================================================

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


# ============================================================
# ЗАПУСК
# ============================================================

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

    # --------------------------------------------------------
    # ПОПОЛНЕНИЕ
    # --------------------------------------------------------

    app.add_handler(
        ConversationHandler(
            entry_points=[
                CallbackQueryHandler(
                    refill_start,
                    pattern=r"^main_refill$"
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
            ]
        )
    )

    # --------------------------------------------------------
    # ПОКУПКА
    # --------------------------------------------------------

    app.add_handler(
        ConversationHandler(
            entry_points=[
                CallbackQueryHandler(
                    buy_product_start,
                    pattern=r"^buy_(stars_fixed_|stars_manual|prem_fixed_)"
                )
            ],
            states={
                BUY_USERNAME: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        buy_username
                    )
                ],
                BUY_CONFIRM: [
                    CallbackQueryHandler(
                        buy_confirm,
                        pattern=r"^(confirm_final_buy|cancel_buy)$"
                    )
                ]
            },
            fallbacks=[
                CommandHandler(
                    "start",
                    start
                )
            ]
        )
    )

    # --------------------------------------------------------
    # АДМИНКА
    # --------------------------------------------------------

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
            admin_callback_handler,
            pattern=r"^admin_"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            admin_pay_buttons,
            pattern=r"^adm_pay_"
        )
    )

    # --------------------------------------------------------
    # АККАУНТЫ
    # --------------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            buy_account,
            pattern=r"^buy_acc_"
        )
    )

    # --------------------------------------------------------
    # СТАРТ
    # --------------------------------------------------------

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    # --------------------------------------------------------
    # ОСНОВНЫЕ КНОПКИ
    # --------------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            main_callback_handler,
            pattern=r"^(main_|shop_|setlang_|back_to_main)$"
        )
    )

    logger.info(
        "BOT STARTED SUCCESSFULLY"
    )

    app.run_polling()


if __name__ == "__main__":

    main()