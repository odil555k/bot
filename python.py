import logging
import json
import aiohttp
import threading
import os
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- НАСТРОЙКИ ---
BOT_TOKEN = "8844899781:AAEjbqNXXf8R1hSPjutPkIyKXEv2mInzux4"
ADMIN_ID = 6636620529
CARD_NUMBER = "5614 6835 8985 1641"
ELDER_API_KEY = "e2e4d97e848f59429355d52148c6163a"

ELDER_API_URL = "https://asosiy.elder.uz/api"
PRICE_PER_STAR = 210

USERS_DB = {}

# Состояния диалогов
REFILL_AMOUNT, CONFIRM_REFILL = range(2)
BUY_AMOUNT, BUY_USERNAME, BUY_CONFIRM = range(2, 5)
ADMIN_BAN_ID, ADMIN_UNBAN_ID, ADMIN_MSG_ID, ADMIN_MSG_TEXT = range(5, 9)

# --- ЛОКАЛИЗАЦИЯ ---
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
        "refill_done": "⏳ Ваш чек отправлен администратору на проверку.",
        "refill_err": "❌ Ошибка отправки чека.",
        "buy_stars_enter": "✏️ Сколько Telegram Stars (звёзд) вы хотите купить? Введите число:",
        "buy_stars_bad": "❌ Введите правильное целое число звёзд:",
        "buy_no_money": "❌ Недостаточно средств. Заказ стоит {price:,} сумов, у вас {balance:,} сумов.",
        "buy_username_enter": "✏️ Введите Telegram Юзернейм (@username) или ID получателя:",
        "buy_confirm_title": "📝 <b>Подтверждение покупки</b>\n\n📦 Товар: {prod_name}\n👤 Получатель: {target}\n💵 Стоимость: <b>{price:,} сумов</b>\n\nСписать деньги с баланса?",
        "buy_confirm_btn": "✅ Да, купить",
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
        "refill_done": "⏳ Sizning chekingiz administratorga tekshirish uchun yuborildi.",
        "refill_err": "❌ Chek yuborishda xatolik.",
        "buy_stars_enter": "✏️ Qancha Telegram Stars (yulduz) sotib olmoqchisiz?",
        "buy_stars_bad": "❌ Iltimos, yulduzlar sonini to'g'ri kiriting:",
        "buy_no_money": "❌ Mablag' yetarli emas.",
        "buy_username_enter": "✏️ Qabul qiluvchining Telegram Yuzerneymini (@username) yoki ID raqamini kiriting:",
        "buy_confirm_title": "📝 <b>Xaridni tasdiqlash</b>\n\n📦 Mahsulot: {prod_name}\n👤 Qabul qiluvchi: {target}\n💵 Qiяmati: <b>{price:,} so'm</b>",
        "buy_confirm_btn": "✅ Ha, sotib olish",
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
        self.wfile.write(b"OK")

    def log_message(self, format, *args): return


def run_health_check():
    server = HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 8000))), HealthCheckHandler)
    server.serve_forever()


def get_user_data(user_id, username="", name=""):
    if user_id not in USERS_DB:
        USERS_DB[user_id] = {"balance": 0, "username": username, "name": name, "lang": "ru", "is_banned": False}
    return USERS_DB[user_id]


async def is_user_banned(update: Update) -> bool:
    uid = update.effective_user.id
    if USERS_DB.get(uid, {}).get("is_banned", False):
        msg = TEXTS[USERS_DB[uid]["lang"]]["banned_msg"]
        if update.message:
            await update.message.reply_text(msg)
        elif update.callback_query:
            await update.callback_query.answer(msg, show_alert=True)
        return True
    return False


# --- СТАРТ И ИНЛАЙН ГЛАВНОЕ МЕНЮ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_user_banned(update): return ConversationHandler.END
    context.user_data.clear()

    user = update.effective_user
    u_data = get_user_data(user.id, user.username, user.first_name)
    lang = u_data["lang"]
    t = TEXTS[lang]

    # Кнопки теперь внутри сообщения (Inline)
    inline_keyboard = [
        [InlineKeyboardButton(t["btn_shop"], callback_data="main_shop")],
        [InlineKeyboardButton(t["btn_refill"], callback_data="main_refill"),
         InlineKeyboardButton(t["btn_profile"], callback_data="main_profile")]
    ]
    markup = InlineKeyboardMarkup(inline_keyboard)
    text = t["welcome"].format(name=user.first_name, balance=u_data['balance'])

    # Принудительно очищаем старую нижнюю клавиатуру, если она осталась
    if update.message:
        await update.message.reply_text(text, reply_markup=markup)
        # Отправляем невидимое удаление нижних кнопок
        msg = await update.message.reply_text(".", reply_markup=ReplyKeyboardRemove())
        await msg.delete()
    else:
        await update.callback_query.message.reply_text(text, reply_markup=markup)
    return ConversationHandler.END


# --- ПРОФИЛЬ И СМЕНА ЯЗЫКА ---
async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_user_banned(update): return
    user_id = update.effective_user.id
    u_data = get_user_data(user_id)
    t = TEXTS[u_data["lang"]]

    text = t["profile_text"].format(user_id=user_id, balance=u_data['balance'])
    inline_keyboard = [
        [InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="setlang_uz"),
         InlineKeyboardButton("🇷🇺 Русский", callback_data="setlang_ru")],
        [InlineKeyboardButton(t["btn_back"], callback_data="back_to_main")]
    ]

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard), parse_mode="HTML")
    elif update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard),
                                                      parse_mode="HTML")


# --- ОБРАБОТЧИК ВСЕХ ИНЛАЙН КНОПОК ---
async def inline_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_user_banned(update): return
    query = update.callback_query
    await query.answer()
    u_data = get_user_data(query.from_user.id)
    lang = u_data["lang"]
    t = TEXTS[lang]

    # Смена языка
    if query.data.startswith("setlang_"):
        u_data["lang"] = query.data.split("_")[1]
        await show_profile(update, context)
        return

    # Нажатие на "Назад"
    if query.data == "back_to_main":
        inline_keyboard = [
            [InlineKeyboardButton(t["btn_shop"], callback_data="main_shop")],
            [InlineKeyboardButton(t["btn_refill"], callback_data="main_refill"),
             InlineKeyboardButton(t["btn_profile"], callback_data="main_profile")]
        ]
        text = t["welcome"].format(name=query.from_user.first_name, balance=u_data['balance'])
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard))
        return

    # Главное меню: Купить услуги
    if query.data == "main_shop":
        keyboard = [
            [InlineKeyboardButton(t["shop_stars_cat"], callback_data="shop_stars")],
            [InlineKeyboardButton(t["shop_prem_cat"], callback_data="shop_premium")],
            [InlineKeyboardButton(t["btn_back"], callback_data="back_to_main")]
        ]
        await query.message.edit_text(t["shop_main"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return

    # Главное меню: Личный кабинет
    if query.data == "main_profile":
        await show_profile(update, context)
        return

    # Категория Stars
    if query.data == "shop_stars":
        keyboard = [
            [InlineKeyboardButton("⭐ 50 Stars (10,500)", callback_data="buy_stars_fixed_50")],
            [InlineKeyboardButton("⭐ 100 Stars (21,000)", callback_data="buy_stars_fixed_100")],
            [InlineKeyboardButton(t["stars_manual"], callback_data="buy_stars_manual")],
            [InlineKeyboardButton(t["btn_back"], callback_data="main_shop")]
        ]
        await query.message.edit_text(t["stars_desc"].format(price=PRICE_PER_STAR),
                                      reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return

    # Категория Premium
    if query.data == "shop_premium":
        keyboard = [
            [InlineKeyboardButton("🚀 3 Oy / Mes (75k)", callback_data="buy_prem_fixed_3")],
            [InlineKeyboardButton("🚀 6 Oy / Mes (130k)", callback_data="buy_prem_fixed_6")],
            [InlineKeyboardButton("🚀 12 Oy / Mes (240k)", callback_data="buy_prem_fixed_12")],
            [InlineKeyboardButton(t["btn_back"], callback_data="main_shop")]
        ]
        await query.message.edit_text(t["prem_desc"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return


# --- ПОПОЛНЕНИЕ И ПОКУПКА ---
async def refill_start_from_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    u_data = get_user_data(query.from_user.id)
    await context.bot.send_message(chat_id=query.from_user.id, text=TEXTS[u_data["lang"]]["refill_start"])
    return REFILL_AMOUNT


async def refill_amount_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    txt = update.message.text.replace(" ", "")
    if not txt.isdigit():
        await update.message.reply_text(TEXTS[u_data["lang"]]["refill_bad_num"])
        return REFILL_AMOUNT
    context.user_data["refill_amount"] = int(txt)
    await update.message.reply_text(TEXTS[u_data["lang"]]["refill_invoice"].format(amount=int(txt), card=CARD_NUMBER),
                                    parse_mode="HTML")
    return CONFIRM_REFILL


async def refill_cheque_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u_data = get_user_data(user.id)
    amount = context.user_data.get("refill_amount", 0)
    fid = update.message.photo[-1].file_id if update.message.photo else update.message.document.file_id
    kb = [[InlineKeyboardButton("✅ Odobrish", callback_data=f"adm_pay_yes_{user.id}_{amount}"),
           InlineKeyboardButton("❌ Rad etish", callback_data=f"adm_pay_no_{user.id}")]]
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=fid,
                                 caption=f"💰 Пополнение! ID: {user.id}\nСумма: {amount:,} сумов",
                                 reply_markup=InlineKeyboardMarkup(kb))
    await update.message.reply_text(TEXTS[u_data["lang"]]["refill_done"])
    return ConversationHandler.END


async def buy_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    u_data = get_user_data(query.from_user.id)
    t = TEXTS[u_data["lang"]]

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
    if not update.message.text.isdigit(): return BUY_AMOUNT
    val = int(update.message.text)
    price = val * PRICE_PER_STAR
    if u_data["balance"] < price:
        await update.message.reply_text(
            TEXTS[u_data["lang"]]["buy_no_money"].format(price=price, balance=u_data['balance']))
        return ConversationHandler.END
    context.user_data["buy_value"] = val
    context.user_data["buy_price"] = price
    await update.message.reply_text(TEXTS[u_data["lang"]]["buy_username_enter"])
    return BUY_USERNAME


async def buy_username_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    t = TEXTS[u_data["lang"]]
    context.user_data["target_username"] = update.message.text.strip()
    p_name = f"{context.user_data['buy_value']} Stars" if context.user_data[
                                                              "buy_type"] == "stars" else f"Premium {context.user_data['buy_value']} m."
    text = t["buy_confirm_title"].format(prod_name=p_name, target=context.user_data["target_username"],
                                         price=context.user_data["buy_price"])
    kb = [[InlineKeyboardButton(t["buy_confirm_btn"], callback_data="confirm_final_buy")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return BUY_CONFIRM


async def buy_confirm_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u_data = get_user_data(query.from_user.id)
    u_data["balance"] -= context.user_data.get("buy_price", 0)
    await query.message.edit_text("✅ Заказ успешно оплачен и передан в обработку!")
    context.user_data.clear()
    return ConversationHandler.END


# --- ПАНЕЛЬ АДМИНИСТРАТОРА ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    context.user_data.clear()
    keyboard = [
        [InlineKeyboardButton("👥 Список пользователей", callback_data="admin_list_users")],
        [InlineKeyboardButton("🚫 Блокировать ID", callback_data="admin_ban_start")],
        [InlineKeyboardButton("🟢 Разблокировать ID", callback_data="admin_unban_start")],
        [InlineKeyboardButton("✉️ Сообщение в ЛС", callback_data="admin_msg_start")]
    ]
    await update.message.reply_text("🛠 <b>Панель администратора</b>", reply_markup=InlineKeyboardMarkup(keyboard),
                                    parse_mode="HTML")
    return ConversationHandler.END


async def admin_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID: return
    await query.answer()
    if query.data == "admin_list_users":
        rep = "👥 <b>Список пользователей:</b>\n"
        for uid, info in USERS_DB.items():
            rep += f"• ID: <code>{uid}</code> | Бал: {info['balance']} сум | Бан: {info['is_banned']}\n"
        await query.message.reply_text(rep or "Пусто.", parse_mode="HTML")


async def admin_ban_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("Введите ID для бана:")
    return ADMIN_BAN_ID


async def admin_ban_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user_data(int(update.message.text.strip()))["is_banned"] = True
    await update.message.reply_text("Забанен.")
    return ConversationHandler.END


async def admin_unban_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("Введите ID для разбана:")
    return ADMIN_UNBAN_ID


async def admin_unban_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user_data(int(update.message.text.strip()))["is_banned"] = False
    await update.message.reply_text("Разбанен.")
    return ConversationHandler.END


async def admin_msg_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


async def admin_pay_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


# --- ЗАПУСК ---
async def main_async():
    threading.Thread(target=run_health_check, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))

    app.add_handler(ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_ban_start, pattern="^admin_ban_start$"),
            CallbackQueryHandler(admin_unban_start, pattern="^admin_unban_start$"),
            CallbackQueryHandler(admin_msg_start, pattern="^admin_msg_start$")
        ],
        states={
            ADMIN_BAN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_ban_rcv)],
            ADMIN_UNBAN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_unban_rcv)],
            ADMIN_MSG_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_msg_id_rcv)],
            ADMIN_MSG_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_msg_text_rcv)]
        },
        fallbacks=[CommandHandler("start", start)]
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(refill_start_from_inline, pattern="^main_refill$")],
        states={
            REFILL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, refill_amount_rcv)],
            CONFIRM_REFILL: [MessageHandler(filters.PHOTO | filters.Document.IMAGE, refill_cheque_rcv)]
        },
        fallbacks=[CommandHandler("start", start)]
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(buy_product_start, pattern="^buy_(stars|prem)_")],
        states={
            BUY_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_amount_rcv)],
            BUY_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_username_rcv)],
            BUY_CONFIRM: [CallbackQueryHandler(buy_confirm_final, pattern="^confirm_final_buy$")]
        },
        fallbacks=[CommandHandler("start", start)]
    ))

    app.add_handler(CallbackQueryHandler(admin_menu_cb, pattern="^admin_list_users$"))
    app.add_handler(CallbackQueryHandler(admin_pay_buttons, pattern="^adm_pay_"))
    app.add_handler(CallbackQueryHandler(inline_handler, pattern="^shop_|^setlang_|^main_|^back_to_main$"))

    await app.initialize()
    await app.updater.start_polling()
    await app.start()
    while True: await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main_async())