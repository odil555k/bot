import logging
import json
import aiohttp
import threading
import os
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

# Включаем логирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- НАСТРОЙКИ ---
BOT_TOKEN = "8844899781:AAEjbqNXXf8R1hSPjutPkIyKXEv2mInzux4"
ADMIN_ID = 6636620529
CARD_NUMBER = "5614 6835 8985 1641"
ELDER_API_KEY = "e2e4d97e848f59429355d52148c6163a"

ELDER_API_URL = "https://asosiy.elder.uz/api"
PRICE_PER_STAR = 210

# Имитация базы данных
USERS_DB = {}  # {user_id: {"balance": 0, "username": "...", "lang": "ru"/"uz"}}

# Стейты для диалогов
REFILL_AMOUNT, CONFIRM_REFILL = range(2)
BUY_AMOUNT, BUY_USERNAME, BUY_CONFIRM = range(2, 5)

# --- СЛОВАРЬ ЛОКАЛИЗАЦИИ (РУССКИЙ И УЗБЕКСКИЙ НА ЛАТИНИЦЕ) ---
TEXTS = {
    "ru": {
        "welcome": "👋 Привет, {name}!\nДобро пожаловать в магазин Telegram Stars & Premium.\n\n💰 Ваш баланс: {balance:,} сумов",
        "btn_shop": "🛍 Купить услуги",
        "btn_refill": "💳 Пополнить баланс",
        "btn_profile": "👤 Мой кабинет",
        "btn_back": "⬅️ Назад",
        "btn_cancel": "❌ Отмена",
        "profile_text": "👤 <b>Личный кабинет</b>\n\n🆔 Ваш ID: <code>{user_id}</code>\n💰 Баланс: {balance:,} сумов\n\n🌐 Сменить язык / Tilni o'zgartirish:",
        "shop_main": "🛍 <b>Выберите категорию товара:</b>",
        "shop_stars_cat": "💎 Telegram Stars (Звёзды)",
        "shop_prem_cat": "🌟 Telegram Premium (Подписка)",
        "stars_desc": "💎 <b>Telegram Stars (Звёзды)</b>\n\n💵 Наш тариф: {price} сумов за 1 звезду.",
        "stars_manual": "✏️ Ввести количество вручную",
        "prem_desc": "🌟 <b>Цены на Telegram Premium:</b>\n\n🔹 3 месяца — 75,000 сумов\n🔹 6 месяцев — 130,000 сумов\n🔹 12 месяцев — 240,000 сумов",
        "refill_start": "💳 Введите сумму пополнения в сумах (например: 50000):",
        "refill_bad_num": "❌ Пожалуйста, введите корректное число.",
        "refill_invoice": "Заявка на пополнение: <b>{amount:,} сумов</b>\n\nПереведите ровно эту сумму на карту:\n<code>{card}</code>\n\nПосле оплаты отправьте фото/скриншот чека в этот чат.",
        "refill_bad_photo": "❌ Пожалуйста, отправьте именно картинку или скриншот чека.",
        "refill_done": "⏳ Ваш чек отправлен администратору на проверку. Баланс обновится сразу после подтверждения.",
        "refill_err": "❌ Ошибка отправки чека. Убедитесь, что ADMIN_ID указан верно.",
        "buy_stars_enter": "✏️ Сколько Telegram Stars (звёзд) вы хотите купить? Введите число:",
        "buy_stars_bad": "❌ Введите правильное целое число звёзд:",
        "buy_no_money": "❌ Недостаточно средств. Заказ стоит {price:,} сумов, у вас {balance:,} сумов.",
        "buy_username_enter": "✏️ Введите Telegram Юзернейм (@username) или ID получателя:",
        "buy_confirm_title": "📝 <b>Подтверждение покупки</b>\n\n📦 Товар: {prod_name}\n👤 Получатель: {target}\n💵 Стоимость: <b>{price:,} сумов</b>\n\nСписать деньги с баланса и отправить товар?",
        "buy_confirm_btn": "✅ Да, купить",
        "buy_api_sending": "⏳ Запрос отправляется провайдеру...",
        "buy_api_success": "✅ <b>Успешно отправлено!</b>\n\nТовар отправлен на аккаунт {target}.\nСписано: {price:,} сумов. Остаток: {balance:,} сумов.",
        "buy_api_fail": "⏳ <b>Заказ принят в обработку</b>\n\nТовар будет доставлен оператором в течение нескольких минут.",
        "cancel_msg": "Действие отменено.",
        "prem_months": "{value} мес."
    },
    "uz": {
        "welcome": "👋 Salom, {name}!\nTelegram Stars & Premium do'koniga xush kelibsiz.\n\n💰 Sizning balansingiz: {balance:,} so'm",
        "btn_shop": "🛍 Xizmatlarni sotib olish",
        "btn_refill": "💳 Balansni to'ldirish",
        "btn_profile": "👤 Shaxsiy kabinet",
        "btn_back": "⬅️ Ortga",
        "btn_cancel": "❌ Bekor qilish",
        "profile_text": "👤 <b>Shaxsiy kabinet</b>\n\n🆔 Sizning ID: <code>{user_id}</code>\n💰 Balans: {balance:,} so'm\n\n🌐 Tilni o'zgartirish / Сменить язык:",
        "shop_main": "🛍 <b>Kategoriyani tanlang:</b>",
        "shop_stars_cat": "💎 Telegram Stars (Yulduzlar)",
        "shop_prem_cat": "🌟 Telegram Premium (Obuna)",
        "stars_desc": "💎 <b>Telegram Stars (Yulduzlar)</b>\n\n💵 Bizning tarif: 1 ta yulduz uchun {price} so'm.",
        "stars_manual": "✏️ Miqdorni qo'lda kiritish",
        "prem_desc": "🌟 <b>Telegram Premium narxlari:</b>\n\n🔹 3 oy — 75,000 so'm\n🔹 6 oy — 130,000 so'm\n🔹 12 oy — 240,000 so'm",
        "refill_start": "💳 To'ldirish summasini so'mda kiriting (masalan: 50000):",
        "refill_bad_num": "❌ Iltimos, to'g'ri son kiriting.",
        "refill_invoice": "To'ldirish uchun ariza: <b>{amount:,} so'm</b>\n\nUshbu summani aynan mana shu kartaga o'tkazing:\n<code>{card}</code>\n\nTarixiy to'lovdan so'ng chekning rasmi yoki skrinshotini shu chatga yuboring.",
        "refill_bad_photo": "❌ Iltimos, aynan rasm yoki chek skrinshotini yuboring.",
        "refill_done": "⏳ Sizning chekingiz administratorga tekshirish uchun yuborildi. Balans tasdiqlangandan so'ng yangilanadi.",
        "refill_err": "❌ Chek yuborishda xatolik. ADMIN_ID to'g'ri sozlanganiga ishonch hosil qiling.",
        "buy_stars_enter": "✏️ Qancha Telegram Stars (yulduz) sotib olmoqchisiz? Son kiriting:",
        "buy_stars_bad": "❌ Iltimos, yulduzlar sonini to'g'ri kiriting:",
        "buy_no_money": "❌ Mablag' yetarli emas. Buyurtma {price:,} so'm turadi, sizda esa {balance:,} so'm bor.",
        "buy_username_enter": "✏️ Qabul qiluvchining Telegram Yuzerneymini (@username) yoki ID raqamini kiriting:",
        "buy_confirm_title": "📝 <b>Xaridni tasdiqlash</b>\n\n📦 Mahsulot: {prod_name}\n👤 Qabul qiluvchi: {target}\n💵 Qiymati: <b>{price:,} so'm</b>\n\nMablag' balansdan yechilsin va mahsulot yuborilsinmi?",
        "buy_confirm_btn": "✅ Ha, sotib olish",
        "buy_api_sending": "⏳ Provayderga so'rov yuborilmoqda...",
        "buy_api_success": "✅ <b>Muvaffaqiyatli yuborildi!</b>\n\nMahsulot {target} akkauntiga taqdim etildi.\nYechildi: {price:,} so'm. Qoldiq: {balance:,} so'm.",
        "buy_api_fail": "⏳ <b>Buyurtma ishlov berishga qabul qilindi</b>\n\nMahsulot bir necha daqiqa ichida operator tomonidan yetkazib beriladi.",
        "cancel_msg": "Jarayon bekor qilindi.",
        "prem_months": "{value} oylik"
    }
}


# --- МИКРО-СЕРВЕР ДЛЯ RENDER.COM ---

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot is running successfully!")

    def log_message(self, format, *args):
        return


def run_health_check():
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logging.info(f"Fonli veb-server {port} portida ishga tushdi")
    server.serve_forever()


# --- VSПОМОГАТЕЛЬНЫЕ ФУНКЦИИ API (Elder Stars) ---

async def buy_stars_via_api(username: str, amount: int) -> bool:
    url = f"{ELDER_API_URL}/stars/buy"
    headers = {"X-Api-Key": ELDER_API_KEY, "Content-Type": "application/json"}
    payload = {"username": username.replace("@", ""), "amount": amount}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                result = await response.json()
                return response.status == 200 and result.get("success")
    except Exception as e:
        logging.error(f"API Stars tarmog'ida xatolik: {e}")
        return False


async def buy_premium_via_api(username: str, months: int) -> bool:
    url = f"{ELDER_API_URL}/premium/buy"
    headers = {"X-Api-Key": ELDER_API_KEY, "Content-Type": "application/json"}
    payload = {"username": username.replace("@", ""), "months": months}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                result = await response.json()
                return response.status == 200 and result.get("success")
    except Exception as e:
        logging.error(f"API Premium tarmog'ida xatolik: {e}")
        return False


def get_user_data(user_id, username=""):
    if user_id not in USERS_DB:
        USERS_DB[user_id] = {"balance": 0, "username": username, "lang": None}
    if username and USERS_DB[user_id]["username"] != username:
        USERS_DB[user_id]["username"] = username
    return USERS_DB[user_id]


# --- ЛОГИКА БОТА ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u_data = get_user_data(user.id, user.username)

    if not u_data["lang"]:
        text = "🌐 Tilni tanlang / Выберите язык:"
        keyboard = [
            [InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="setlang_uz")],
            [InlineKeyboardButton("🇷🇺 Русский", callback_data="setlang_ru")]
        ]
        if update.message:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    lang = u_data["lang"]
    t = TEXTS[lang]

    text = t["welcome"].format(name=user.first_name, balance=u_data['balance'])

    keyboard = [
        [InlineKeyboardButton(t["btn_shop"], callback_data="menu_shop")],
        [InlineKeyboardButton(t["btn_refill"], callback_data="menu_refill")],
        [InlineKeyboardButton(t["btn_profile"], callback_data="menu_profile")]
    ]

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    u_data = get_user_data(user_id)

    if query.data.startswith("setlang_"):
        selected_lang = query.data.split("_")[1]
        u_data["lang"] = selected_lang
        await start(update, context)
        return

    lang = u_data["lang"] if u_data["lang"] else "ru"
    t = TEXTS[lang]

    if query.data == "menu_main":
        await start(update, context)
    elif query.data == "menu_profile":
        text = t["profile_text"].format(user_id=user_id, balance=u_data['balance'])
        keyboard = [
            [InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="setlang_uz"),
             InlineKeyboardButton("🇷🇺 Русский", callback_data="setlang_ru")],
            [InlineKeyboardButton(t["btn_back"], callback_data="menu_main")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    elif query.data == "menu_shop":
        text = t["shop_main"]
        keyboard = [
            [InlineKeyboardButton(t["shop_stars_cat"], callback_data="shop_stars")],
            [InlineKeyboardButton(t["shop_prem_cat"], callback_data="shop_premium")],
            [InlineKeyboardButton(t["btn_back"], callback_data="menu_main")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    elif query.data == "shop_stars":
        text = t["stars_desc"].format(price=PRICE_PER_STAR)
        keyboard = [
            [InlineKeyboardButton("⭐ 50 Stars (10,500)", callback_data="buy_stars_fixed_50")],
            [InlineKeyboardButton("⭐ 100 Stars (21,000)", callback_data="buy_stars_fixed_100")],
            [InlineKeyboardButton("⭐ 250 Stars (52,500)", callback_data="buy_stars_fixed_250")],
            [InlineKeyboardButton(t["stars_manual"], callback_data="buy_stars_manual")],
            [InlineKeyboardButton(t["btn_back"], callback_data="menu_shop")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    elif query.data == "shop_premium":
        text = t["prem_desc"]
        keyboard = [
            [InlineKeyboardButton("🚀 3 Oy / Mes (75k)", callback_data="buy_prem_fixed_3")],
            [InlineKeyboardButton("🚀 6 Oy / Mes (130k)", callback_data="buy_prem_fixed_6")],
            [InlineKeyboardButton("🚀 12 Oy / Mes (240k)", callback_data="buy_prem_fixed_12")],
            [InlineKeyboardButton(t["btn_back"], callback_data="menu_shop")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


# --- ДИАЛОГ РУЧНОГО ПОПОЛНЕНИЯ БАЛАНСА ЧЕРЕЗ ЧЕК ---

async def refill_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    u_data = get_user_data(user_id)
    lang = u_data["lang"] if u_data["lang"] else "ru"

    await query.message.edit_text(TEXTS[lang]["refill_start"])
    return REFILL_AMOUNT


async def refill_amount_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u_data = get_user_data(user_id)
    lang = u_data["lang"] if u_data["lang"] else "ru"
    t = TEXTS[lang]

    amount_text = update.message.text.replace(" ", "")
    if not amount_text.isdigit():
        await update.message.reply_text(t["refill_bad_num"])
        return REFILL_AMOUNT

    amount = int(amount_text)
    context.user_data["refill_amount"] = amount

    text = t["refill_invoice"].format(amount=amount, card=CARD_NUMBER)
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton(t["btn_cancel"], callback_data="cancel_action")]
    ]), parse_mode="HTML")
    return CONFIRM_REFILL


async def refill_cheque_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u_data = get_user_data(user.id)
    lang = u_data["lang"] if u_data["lang"] else "ru"
    t = TEXTS[lang]

    amount = context.user_data.get("refill_amount", 0)

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document and update.message.document.mime_type.startswith("image/"):
        file_id = update.message.document.file_id
    else:
        await update.message.reply_text(t["refill_bad_photo"])
        return CONFIRM_REFILL

    keyboard = [[
        InlineKeyboardButton("✅ Odobrish", callback_data=f"adm_pay_yes_{user.id}_{amount}"),
        InlineKeyboardButton("❌ Rad etish", callback_data=f"adm_pay_no_{user.id}")
    ]]

    username_text = f"@{user.username}" if user.username else "Yuzerneym yo'q"
    caption_text = (
        f"💰 <b>Пополнение баланса!</b>\n"
        f"👤 От: {username_text} (ID: <code>{user.id}</code>)\n"
        f"💵 Сумма: <b>{amount:,} сумов</b>"
    )

    try:
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=file_id,
            caption=caption_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        await update.message.reply_text(t["refill_done"])
    except Exception as e:
        logging.error(f"Chek yuborishda xatolik: {e}")
        await update.message.reply_text(t["refill_err"])

    context.user_data.clear()
    return ConversationHandler.END


# --- ДИАЛОГ АВТО-ПОКУПКИ ТОВАРА ---

async def buy_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    u_data = get_user_data(user_id)
    lang = u_data["lang"] if u_data["lang"] else "ru"
    t = TEXTS[lang]

    if data == "buy_stars_manual":
        context.user_data["buy_type"] = "stars"
        context.user_data["is_manual"] = True
        await query.message.edit_text(t["buy_stars_enter"])
        return BUY_AMOUNT

    _, prod_type, _, value = data.split("_")
    value = int(value)
    context.user_data["buy_type"] = prod_type
    context.user_data["buy_value"] = value
    context.user_data["is_manual"] = False

    price = value * PRICE_PER_STAR if prod_type == "stars" else {3: 75000, 6: 130000, 12: 240000}.get(value, 0)

    if u_data["balance"] < price:
        await query.message.reply_text(t["buy_no_money"].format(price=price, balance=u_data['balance']))
        return ConversationHandler.END

    context.user_data["buy_price"] = price
    await query.message.edit_text(t["buy_username_enter"])
    return BUY_USERNAME


async def buy_amount_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u_data = get_user_data(user_id)
    lang = u_data["lang"] if u_data["lang"] else "ru"
    t = TEXTS[lang]

    amount_text = update.message.text.strip()
    if not amount_text.isdigit() or int(amount_text) <= 0:
        await update.message.reply_text(t["buy_stars_bad"])
        return BUY_AMOUNT

    value = int(amount_text)
    price = value * PRICE_PER_STAR

    if u_data["balance"] < price:
        await update.message.reply_text(t["buy_no_money"].format(price=price, balance=u_data['balance']))
        return ConversationHandler.END

    context.user_data["buy_value"] = value
    context.user_data["buy_price"] = price
    await update.message.reply_text(t["buy_username_enter"])
    return BUY_USERNAME


async def buy_username_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u_data = get_user_data(user_id)
    lang = u_data["lang"] if u_data["lang"] else "ru"
    t = TEXTS[lang]

    target_username = update.message.text.strip()
    context.user_data["target_username"] = target_username
    prod_type = context.user_data["buy_type"]
    value = context.user_data["buy_value"]
    price = context.user_data["buy_price"]

    prod_name = f"{value} Stars" if prod_type == "stars" else t["prem_months"].format(value=value)

    text = t["buy_confirm_title"].format(prod_name=prod_name, target=target_username, price=price)
    keyboard = [[InlineKeyboardButton(t["buy_confirm_btn"], callback_data="confirm_final_buy")],
                [InlineKeyboardButton(t["btn_cancel"], callback_data="cancel_action")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return BUY_CONFIRM


async def buy_confirm_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    u_data = get_user_data(user_id)
    lang = u_data["lang"] if u_data["lang"] else "ru"
    t = TEXTS[lang]

    prod_type = context.user_data.get("buy_type")
    value = context.user_data.get("buy_value")
    price = context.user_data.get("buy_price")
    target = context.user_data.get("target_username")

    if u_data["balance"] < price:
        await query.message.edit_text(t["buy_no_money"].format(price=price, balance=u_data['balance']))
        return ConversationHandler.END

    u_data["balance"] -= price
    await query.message.edit_text(t["buy_api_sending"])

    api_success = await buy_stars_via_api(target, value) if prod_type == "stars" else await buy_premium_via_api(target,
                                                                                                                value)

    if api_success:
        await query.message.edit_text(
            t["buy_api_success"].format(target=target, price=price, balance=u_data['balance']), parse_mode="HTML")
    else:
        await query.message.edit_text(t["buy_api_fail"])
        prod_name = f"{value} Stars" if prod_type == "stars" else f"Premium {value} m."
        await context.bot.send_message(chat_id=ADMIN_ID,
                                       text=f"⚠️ <b>DIQQAT: AVTO-YUBORISHDA XATOLIK!</b>\n\nBuyurtmani qo'lda topshiring:\n👤 Kimga: {target}\n📦 Mahsulot: {prod_name}")

    context.user_data.clear()
    return ConversationHandler.END


# --- ОБРАБОТЧИК КНОПОК ОДОБРЕНИЯ/ОТКЛОНЕНИЯ ДЛЯ АДМИНИСТРАТОРА ---

async def admin_buttons_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data.startswith("adm_pay_yes_"):
        await query.answer()
        _, _, _, client_id, amount = data.split("_")
        client_id = int(client_id)
        amount = int(amount)

        c_data = get_user_data(client_id)
        c_data["balance"] += amount
        c_lang = c_data["lang"] if c_data["lang"] else "ru"

        new_caption = (
            f"💰 <b>Пополнение баланса</b>\n"
            f"👤 Клиент ID: <code>{client_id}</code>\n"
            f"💵 Сумма: <b>{amount:,} сумов</b>\n\n"
            f"🟢 <b>ОДОБРЕНО! Баланс успешно зачислен клиенту.</b>"
        )
        try:
            await query.message.edit_caption(caption=new_caption, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Admin rasm ostidagi matnni o'zgartira olmadi: {e}")

        try:
            msg_text = f"🎉 Ваш чек проверен! На ваш баланс зачислено {amount:,} сумов." if c_lang == "ru" else f"🎉 Chekingiz tekshirildi! Balansingizga {amount:,} so'm qo'shildi."
            await context.bot.send_message(chat_id=client_id, text=msg_text)
        except Exception:
            pass

    elif data.startswith("adm_pay_no_"):
        await query.answer()
        client_id = int(data.split("_")[3])
        c_data = get_user_data(client_id)
        c_lang = c_data["lang"] if c_data["lang"] else "ru"

        new_caption = (
            f"💰 <b>Пополнение баланса</b>\n"
            f"👤 Клиент ID: <code>{client_id}</code>\n\n"
            f"🔴 <b>ОТКЛОНЕНО! Чек был отклонен администратором.</b>"
        )
        try:
            await query.message.edit_caption(caption=new_caption, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Admin rasm ostidagi matnni o'zgartira olmadi: {e}")

        try:
            msg_text = "❌ Ваш чек был отклонен администратором. Если это ошибка, свяжитесь с поддержкой." if c_lang == "ru" else "❌ Chekingiz administrator tomonidan rad etildi. Agar xatolik bo'lsa, qo'llab-quvvatlash xizmatiga murojaat qiling."
            await context.bot.send_message(chat_id=client_id, text=msg_text)
        except Exception:
            pass


async def cancel_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    u_data = get_user_data(user_id)
    lang = u_data["lang"] if u_data["lang"] else "ru"

    await query.answer(TEXTS[lang]["cancel_msg"])
    context.user_data.clear()
    await start(update, context)
    return ConversationHandler.END


# --- АСИНХРОННЫЙ ЗАПУСК ДЛЯ PYTHON 3.14+ ---

async def main_async():
    threading.Thread(target=run_health_check, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    refill_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(refill_start, pattern="^menu_refill$")],
        states={
            REFILL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, refill_amount_rcv)],
            CONFIRM_REFILL: [MessageHandler(filters.PHOTO | filters.Document.IMAGE, refill_cheque_rcv)]
        },
        fallbacks=[CallbackQueryHandler(cancel_action, pattern="^cancel_action$")]
    )

    buy_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(buy_product_start, pattern="^buy_(stars|prem)_")],
        states={
            BUY_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_amount_rcv)],
            BUY_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_username_rcv)],
            BUY_CONFIRM: [CallbackQueryHandler(buy_confirm_final, pattern="^confirm_final_buy$")]
        },
        fallbacks=[CallbackQueryHandler(cancel_action, pattern="^cancel_action$")]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(refill_conv)
    app.add_handler(buy_conv)
    app.add_handler(CallbackQueryHandler(admin_buttons_handler, pattern="^adm_pay_"))
    app.add_handler(CallbackQueryHandler(cancel_action, pattern="^cancel_action$"))
    app.add_handler(CallbackQueryHandler(menu_handler, pattern="^menu_|^shop_|^setlang_"))

    print("Бот успешно запущен и готов к автовыдачам!")

    await app.initialize()
    await app.updater.start_polling()
    await app.start()

    while True:
        await asyncio.sleep(3600)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()