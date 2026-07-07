import logging
import json
import aiohttp
import threading
import os
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, \
    ReplyKeyboardRemove
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
USERS_DB = {}

# Стейты для диалогов пользователей
REFILL_AMOUNT, CONFIRM_REFILL = range(2)
BUY_AMOUNT, BUY_USERNAME, BUY_CONFIRM = range(2, 5)

# Стейты для админки
ADMIN_BAN_ID, ADMIN_UNBAN_ID, ADMIN_MSG_ID, ADMIN_MSG_TEXT = range(5, 9)

# --- СЛОВАРЬ ЛОКАЛИЗАЦИИ ---
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
        "prem_months": "{value} мес.",
        "banned_msg": "❌ Вы заблокированы в этом боте."
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
        "prem_months": "{value} oylik",
        "banned_msg": "❌ Siz ushbu botda bloklangansiz."
    }
}


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot is running successfully!")

    def log_message(self, format, *args): return


def run_health_check():
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()


def get_user_data(user_id, username="", name=""):
    if user_id not in USERS_DB:
        USERS_DB[user_id] = {"balance": 0, "username": username, "name": name, "lang": "ru", "is_banned": False}
    if username and USERS_DB[user_id]["username"] != username:
        USERS_DB[user_id]["username"] = username
    if name and USERS_DB[user_id]["name"] != name:
        USERS_DB[user_id]["name"] = name
    return USERS_DB[user_id]


async def is_user_banned(update: Update) -> bool:
    user_id = update.effective_user.id
    u_data = get_user_data(user_id)
    if u_data.get("is_banned", False):
        lang = u_data["lang"] or "ru"
        if update.message:
            await update.message.reply_text(TEXTS[lang]["banned_msg"])
        elif update.callback_query:
            await update.callback_query.answer(TEXTS[lang]["banned_msg"], show_alert=True)
        return True
    return False


# --- ФУНКЦИЯ ОТПРАВКИ ГЛАВНОГО МЕНЮ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_user_banned(update): return ConversationHandler.END
    context.user_data.clear()  # Очищаем стейты принудительно

    user = update.effective_user
    u_data = get_user_data(user.id, user.username, user.first_name)
    lang = u_data["lang"] or "ru"
    t = TEXTS[lang]

    # Главное меню делаем ТЕКСТОВЫМИ кнопками (ReplyKeyboardMarkup)
    reply_keyboard = [
        [KeyboardButton(t["btn_shop"])],
        [KeyboardButton(t["btn_refill"]), KeyboardButton(t["btn_profile"])]
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    text = t["welcome"].format(name=user.first_name, balance=u_data['balance'])

    if update.message:
        await update.message.reply_text(text, reply_markup=markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=markup)
    return ConversationHandler.END


# --- ОТПРАВКА ПРОФИЛЯ С КНОПКАМИ СМЕНЫ ЯЗЫКА ---
async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_user_banned(update): return
    user_id = update.effective_user.id
    u_data = get_user_data(user_id)
    lang = u_data["lang"] or "ru"
    t = TEXTS[lang]

    text = t["profile_text"].format(user_id=user_id, balance=u_data['balance'])

    # Вот инлайн кнопки смены языка, которые выводятся ВНУТРИ Личного кабинета
    inline_keyboard = [
        [InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="setlang_uz"),
         InlineKeyboardButton("🇷🇺 Русский", callback_data="setlang_ru")]
    ]

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard), parse_mode="HTML")
    elif update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard),
                                                      parse_mode="HTML")


async def text_menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_user_banned(update): return
    text = update.message.text
    user_id = update.effective_user.id
    u_data = get_user_data(user_id)
    lang = u_data["lang"] or "ru"

    if text == TEXTS["ru"]["btn_profile"] or text == TEXTS["uz"]["btn_profile"]:
        await show_profile(update, context)
    elif text == TEXTS["ru"]["btn_shop"] or text == TEXTS["uz"]["btn_shop"]:
        t = TEXTS[lang]
        keyboard = [
            [InlineKeyboardButton(t["shop_stars_cat"], callback_data="shop_stars")],
            [InlineKeyboardButton(t["shop_prem_cat"], callback_data="shop_premium")]
        ]
        await update.message.reply_text(t["shop_main"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    elif text == TEXTS["ru"]["btn_refill"] or text == TEXTS["uz"]["btn_refill"]:
        # Перенаправляем на инлайн-запуск диалога пополнения
        class FakeQuery:
            def __init__(self, msg): self.message = msg

            async def answer(self): pass

        update.callback_query = FakeQuery(update.message)
        return await refill_start(update, context)


async def inline_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_user_banned(update): return
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    u_data = get_user_data(user_id)

    if query.data.startswith("setlang_"):
        u_data["lang"] = query.data.split("_")[1]
        await show_profile(update, context)  # Перерисовываем профиль на новом языке
        # Обновляем нижние кнопки под новый язык
        t = TEXTS[u_data["lang"]]
        markup = ReplyKeyboardMarkup(
            [[KeyboardButton(t["btn_shop"])], [KeyboardButton(t["btn_refill"]), KeyboardButton(t["btn_profile"])]],
            resize_keyboard=True)
        await query.message.reply_text("✅ Language updated / Til o'zgartirildi", reply_markup=markup)
        return

    lang = u_data["lang"] or "ru"
    t = TEXTS[lang]

    if query.data == "shop_stars":
        text = t["stars_desc"].format(price=PRICE_PER_STAR)
        keyboard = [
            [InlineKeyboardButton("⭐ 50 Stars (10,500)", callback_data="buy_stars_fixed_50")],
            [InlineKeyboardButton("⭐ 100 Stars (21,000)", callback_data="buy_stars_fixed_100")],
            [InlineKeyboardButton("⭐ 250 Stars (52,500)", callback_data="buy_stars_fixed_250")],
            [InlineKeyboardButton(t["stars_manual"], callback_data="buy_stars_manual")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    elif query.data == "shop_premium":
        text = t["prem_desc"]
        keyboard = [
            [InlineKeyboardButton("🚀 3 Oy / Mes (75k)", callback_data="buy_prem_fixed_3")],
            [InlineKeyboardButton("🚀 6 Oy / Mes (130k)", callback_data="buy_prem_fixed_6")],
            [InlineKeyboardButton("🚀 12 Oy / Mes (240k)", callback_data="buy_prem_fixed_12")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


# --- ОСТАЛЬНАЯ ЛОГИКА ОСТАЕТСЯ БЕЗ ИЗМЕНЕНИЙ ---
async def refill_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    lang = u_data["lang"] or "ru"
    await context.bot.send_message(chat_id=update.effective_user.id, text=TEXTS[lang]["refill_start"])
    return REFILL_AMOUNT


async def refill_amount_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    lang = u_data["lang"] or "ru"
    t = TEXTS[lang]
    amount_text = update.message.text.replace(" ", "")
    if not amount_text.isdigit():
        await update.message.reply_text(t["refill_bad_num"])
        return REFILL_AMOUNT
    amount = int(amount_text)
    context.user_data["refill_amount"] = amount
    await update.message.reply_text(t["refill_invoice"].format(amount=amount, card=CARD_NUMBER),
                                    reply_markup=InlineKeyboardMarkup(
                                        [[InlineKeyboardButton(t["btn_cancel"], callback_data="cancel_action")]]),
                                    parse_mode="HTML")
    return CONFIRM_REFILL


async def refill_cheque_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u_data = get_user_data(user.id)
    lang = u_data["lang"] or "ru"
    amount = context.user_data.get("refill_amount", 0)
    file_id = update.message.photo[-1].file_id if update.message.photo else update.message.document.file_id

    keyboard = [[InlineKeyboardButton("✅ Odobrish", callback_data=f"adm_pay_yes_{user.id}_{amount}"),
                 InlineKeyboardButton("❌ Rad etish", callback_data=f"adm_pay_no_{user.id}")]]
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=file_id,
                                 caption=f"💰 <b>Пополнение!</b>\n👤 От: {user.id}\n💵 Сумма: {amount:,} сумов",
                                 reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    await update.message.reply_text(TEXTS[lang]["refill_done"])
    return ConversationHandler.END


async def buy_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    u_data = get_user_data(query.from_user.id)
    lang = u_data["lang"] or "ru"
    t = TEXTS[lang]

    if data == "buy_stars_manual":
        context.user_data["buy_type"] = "stars"
        await query.message.reply_text(t["buy_stars_enter"])
        return BUY_AMOUNT

    _, prod_type, _, value = data.split("_")
    value = int(value)
    context.user_data["buy_type"] = prod_type
    context.user_data["buy_value"] = value
    price = value * PRICE_PER_STAR if prod_type == "stars" else {3: 75000, 6: 130000, 12: 240000}.get(value, 0)

    if u_data["balance"] < price:
        await query.message.reply_text(t["buy_no_money"].format(price=price, balance=u_data['balance']))
        return ConversationHandler.END

    context.user_data["buy_price"] = price
    await query.message.reply_text(t["buy_username_enter"])
    return BUY_USERNAME


async def buy_amount_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    lang = u_data["lang"] or "ru"
    if not update.message.text.isdigit(): return BUY_AMOUNT
    value = int(update.message.text)
    price = value * PRICE_PER_STAR
    if u_data["balance"] < price:
        await update.message.reply_text(TEXTS[lang]["buy_no_money"].format(price=price, balance=u_data['balance']))
        return ConversationHandler.END
    context.user_data["buy_value"] = value
    context.user_data["buy_price"] = price
    await update.message.reply_text(TEXTS[lang]["buy_username_enter"])
    return BUY_USERNAME


async def buy_username_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    lang = u_data["lang"] or "ru"
    t = TEXTS[lang]
    context.user_data["target_username"] = update.message.text.strip()
    prod_name = f"{context.user_data['buy_value']} Stars" if context.user_data[
                                                                 "buy_type"] == "stars" else f"Premium {context.user_data['buy_value']} мес"

    text = t["buy_confirm_title"].format(prod_name=prod_name, target=context.user_data["target_username"],
                                         price=context.user_data["buy_price"])
    keyboard = [[InlineKeyboardButton(t["buy_confirm_btn"], callback_data="confirm_final_buy")],
                [InlineKeyboardButton(t["btn_cancel"], callback_data="cancel_action")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return BUY_CONFIRM


async def buy_confirm_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u_data = get_user_data(query.from_user.id)
    price = context.user_data.get("buy_price")
    u_data["balance"] -= price
    await query.message.edit_text("✅ Заказ принят!")
    context.user_data.clear()
    return ConversationHandler.END


# --- АДМИНКА ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    context.user_data.clear()  # Принудительно сбрасываем старые зависшие диалоги
    keyboard = [
        [InlineKeyboardButton("👥 Список пользователей", callback_data="admin_list_users")],
        [InlineKeyboardButton("🚫 Блокировать ID", callback_data="admin_ban_start")],
        [InlineKeyboardButton("🟢 Разблокировать ID", callback_data="admin_unban_start")],
        [InlineKeyboardButton("✉️ Сообщение в ЛС", callback_data="admin_msg_start")]
    ]
    await update.message.reply_text("🛠 <b>Панель администратора</b>", reply_markup=InlineKeyboardMarkup(keyboard),
                                    parse_mode="HTML")
    return ConversationHandler.END


async def admin_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID: return
    await query.answer()
    if query.data == "admin_list_users":
        report = "👥 <b>Список пользователей:</b>\n"
        for uid, info in USERS_DB.items():
            report += f"• ID: <code>{uid}</code> | Баланс: {info['balance']} сумов\n"
        await query.message.reply_text(report or "База пуста.", parse_mode="HTML")


async def admin_ban_start_route(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("Введите ID для блокировки:")
    return ADMIN_BAN_ID


async def admin_ban_id_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = int(update.message.text.strip())
    get_user_data(target)["is_banned"] = True
    await update.message.reply_text("Пользователь заблокирован.")
    return ConversationHandler.END


async def admin_unban_start_route(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("Введите ID для разблокировки:")
    return ADMIN_UNBAN_ID


async def admin_unban_id_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = int(update.message.text.strip())
    get_user_data(target)["is_banned"] = False
    await update.message.reply_text("Пользователь разблокирован.")
    return ConversationHandler.END


async def admin_msg_start_route(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("Введите ID получателя:")
    return ADMIN_MSG_ID


async def admin_msg_id_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["adm_tgt"] = int(update.message.text.strip())
    await update.message.reply_text("Введите текст сообщения:")
    return ADMIN_MSG_TEXT


async def admin_msg_text_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_message(chat_id=context.user_data["adm_tgt"],
                                       text=f"✉️ <b>Сообщение от админа:</b>\n\n{update.message.text}",
                                       parse_mode="HTML")
        await update.message.reply_text("Отправлено!")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")
    return ConversationHandler.END


async def admin_buttons_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("adm_pay_yes_"):
        _, _, _, cid, amt = query.data.split("_")
        get_user_data(int(cid))["balance"] += int(amt)
        await query.message.edit_caption("🟢 Одобрено!")
        try:
            await context.bot.send_message(chat_id=int(cid), text="🎉 Баланс пополнен!")
        except Exception:
            pass
    elif query.data.startswith("adm_pay_no_"):
        await query.message.edit_caption("🔴 Отклонено!")


async def cancel_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query: await update.callback_query.answer()
    return await start(update, context)


# --- ЗАПУСК ---
async def main_async():
    threading.Thread(target=run_health_check, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()

    admin_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_ban_start_route, pattern="^admin_ban_start$"),
            CallbackQueryHandler(admin_unban_start_route, pattern="^admin_unban_start$"),
            CallbackQueryHandler(admin_msg_start_route, pattern="^admin_msg_start$")
        ],
        states={
            ADMIN_BAN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_ban_id_rcv)],
            ADMIN_UNBAN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_unban_id_rcv)],
            ADMIN_MSG_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_msg_id_rcv)],
            ADMIN_MSG_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_msg_text_rcv)]
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(cancel_action, pattern="^cancel_action$")]
    )

    refill_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(refill_start, pattern="^menu_refill$")],
        states={
            REFILL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, refill_amount_rcv)],
            CONFIRM_REFILL: [MessageHandler(filters.PHOTO | filters.Document.IMAGE, refill_cheque_rcv)]
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(cancel_action, pattern="^cancel_action$")]
    )

    buy_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(buy_product_start, pattern="^buy_(stars|prem)_")],
        states={
            BUY_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_amount_rcv)],
            BUY_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_username_rcv)],
            BUY_CONFIRM: [CallbackQueryHandler(buy_confirm_final, pattern="^confirm_final_buy$")]
        },
        fallbacks=[CommandHandler("start", start), CallbackQueryHandler(cancel_action, pattern="^cancel_action$")]
    )

    # Важно: Сначала вешаем явные команды, чтобы они сбрасывали любые диалоги
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))

    app.add_handler(admin_conv)
    app.add_handler(refill_conv)
    app.add_handler(buy_conv)

    app.add_handler(CallbackQueryHandler(admin_menu_callback, pattern="^admin_list_users$"))
    app.add_handler(CallbackQueryHandler(admin_buttons_handler, pattern="^adm_pay_"))
    app.add_handler(CallbackQueryHandler(cancel_action, pattern="^cancel_action$"))
    app.add_handler(CallbackQueryHandler(inline_callback_handler, pattern="^shop_|^setlang_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_menu_router))

    await app.initialize()
    await app.updater.start_polling()
    await app.start()
    while True: await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main_async())