import logging
import json
import aiohttp
import threading
import os
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

# --- НАСТРОЙКИ (ОБЯЗАТЕЛЬНО ЗАПОЛНИ) ---
BOT_TOKEN = "8844899781:AAEjbqNXXf8R1hSPjutPkIyKXEv2mInzux4"
ADMIN_ID = 6636620529  # ТВОЙ_ТЕЛЕГРАМ_ID (числом, без кавычек)
CARD_NUMBER = "5614 6835 8985 1641"  # Твоя карта для приема сумов
ELDER_API_KEY = "b4c71a41a37ac7e98c69092464e31acf"

ELDER_API_URL = "https://asosiy.elder.uz/api"
PRICE_PER_STAR = 210

# Имитация базы данных
USERS_DB = {}  # {user_id: {"balance": 0, "username": "..."}}

# Стейты для диалогов
REFILL_AMOUNT, CONFIRM_REFILL = range(2)
BUY_AMOUNT, BUY_USERNAME, BUY_CONFIRM = range(2, 5)


# --- МИКРО-СЕРВЕР ДЛЯ RENDER.COM ---

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot is running successfully!")

    def log_message(self, format, *args):
        return  # Отключаем лишний спам логов сервера в консоль


def run_health_check():
    # Render автоматически передает порт в переменную окружения PORT, по умолчанию ставим 8000
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logging.info(f"Фоновый веб-сервер запущен на порту {port}")
    server.serve_forever()


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ API (Elder Stars) ---

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
        logging.error(f"Сбой сети API Stars: {e}")
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
        logging.error(f"Сбой сети API Premium: {e}")
        return False


def get_user_data(user_id, username=""):
    if user_id not in USERS_DB:
        USERS_DB[user_id] = {"balance": 0, "username": username}
    if username and USERS_DB[user_id]["username"] != username:
        USERS_DB[user_id]["username"] = username
    return USERS_DB[user_id]


# --- ЛОГИКА БОТА ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u_data = get_user_data(user.id, user.username)

    text = (
        f"👋 Привет, {user.first_name}!\n"
        f"Добро пожаловать в магазин Telegram Stars & Premium.\n\n"
        f"💰 Ваш баланс: {u_data['balance']:,} сумов"
    )

    keyboard = [
        [InlineKeyboardButton("🛍 Купить услуги", callback_data="menu_shop")],
        [InlineKeyboardButton("💳 Пополнить баланс", callback_data="menu_refill")],
        [InlineKeyboardButton("👤 Мой кабинет", callback_data="menu_profile")]
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

    if query.data == "menu_main":
        await start(update, context)
    elif query.data == "menu_profile":
        text = f"👤 <b>Личный кабинет</b>\n\n🆔 Ваш ID: <code>{user_id}</code>\n💰 Баланс: {u_data['balance']:,} сумов"
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ Назад", callback_data="menu_main")]]), parse_mode="HTML")
    elif query.data == "menu_shop":
        text = "🛍 <b>Выберите категорию товара:</b>"
        keyboard = [
            [InlineKeyboardButton("💎 Telegram Stars (Звёзды)", callback_data="shop_stars")],
            [InlineKeyboardButton("🌟 Telegram Premium (Подписка)", callback_data="shop_premium")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="menu_main")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    elif query.data == "shop_stars":
        text = f"💎 <b>Telegram Stars (Звёзды)</b>\n\n💵 Наш тариф: {PRICE_PER_STAR} сумов за 1 звезду."
        keyboard = [
            [InlineKeyboardButton("⭐ 50 Stars (10,500 сумов)", callback_data="buy_stars_fixed_50")],
            [InlineKeyboardButton("⭐ 100 Stars (21,000 сумов)", callback_data="buy_stars_fixed_100")],
            [InlineKeyboardButton("⭐ 250 Stars (52,500 сумов)", callback_data="buy_stars_fixed_250")],
            [InlineKeyboardButton("✏️ Ввести количество вручную", callback_data="buy_stars_manual")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="menu_shop")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    elif query.data == "shop_premium":
        text = "🌟 <b>Цены на Telegram Premium:</b>\n\n🔹 3 месяца — 75,000 сумов\n🔹 6 месяцев — 130,000 сумов\n🔹 12 месяцев — 240,000 сумов"
        keyboard = [
            [InlineKeyboardButton("🚀 3 Месяца (75k)", callback_data="buy_prem_fixed_3")],
            [InlineKeyboardButton("🚀 6 Месяцев (130k)", callback_data="buy_prem_fixed_6")],
            [InlineKeyboardButton("🚀 12 Месяцев (240k)", callback_data="buy_prem_fixed_12")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="menu_shop")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


# --- ДИАЛОГ РУЧНОГО ПОПОЛНЕНИЯ БАЛАНСА ЧЕРЕЗ ЧЕК ---

async def refill_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text("💳 Введите сумму пополнения в сумах (например: 50000):")
    return REFILL_AMOUNT


async def refill_amount_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount_text = update.message.text.replace(" ", "")
    if not amount_text.isdigit():
        await update.message.reply_text("❌ Пожалуйста, введите корректное число.")
        return REFILL_AMOUNT

    amount = int(amount_text)
    context.user_data["refill_amount"] = amount

    text = (
        f"Заявка на пополнение: <b>{amount:,} сумов</b>\n\n"
        f"Переведите ровно эту сумму на карту:\n"
        f"<code>{CARD_NUMBER}</code>\n\n"
        f"После оплаты отправьте фото/скриншот чека в этот чат."
    )
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_action")]
    ]), parse_mode="HTML")
    return CONFIRM_REFILL


async def refill_cheque_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    amount = context.user_data.get("refill_amount", 0)

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document and update.message.document.mime_type.startswith("image/"):
        file_id = update.message.document.file_id
    else:
        await update.message.reply_text("❌ Пожалуйста, отправьте именно картинку или скриншот чека.")
        return CONFIRM_REFILL

    keyboard = [[
        InlineKeyboardButton("✅ Одобрить", callback_data=f"adm_pay_yes_{user.id}_{amount}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"adm_pay_no_{user.id}")
    ]]

    username_text = f"@{user.username}" if user.username else "Нет юзернейма"
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
        await update.message.reply_text(
            "⏳ Ваш чек отправлен администратору на проверку. Баланс обновится сразу после подтверждения.")
    except Exception as e:
        logging.error(f"Ошибка при пересылке чека: {e}")
        await update.message.reply_text("❌ Ошибка отправки чека. Убедитесь, что ADMIN_ID указан верно.")

    context.user_data.clear()
    return ConversationHandler.END


# --- ДИАЛОГ АВТО-ПОКУПКИ ТОВАРА ---

async def buy_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    u_data = get_user_data(user_id)

    if data == "buy_stars_manual":
        context.user_data["buy_type"] = "stars"
        context.user_data["is_manual"] = True
        await query.message.edit_text("✏️ Сколько Telegram Stars (звёзд) вы хотите купить? Введите число:")
        return BUY_AMOUNT

    _, prod_type, _, value = data.split("_")
    value = int(value)
    context.user_data["buy_type"] = prod_type
    context.user_data["buy_value"] = value
    context.user_data["is_manual"] = False

    price = value * PRICE_PER_STAR if prod_type == "stars" else {3: 75000, 6: 130000, 12: 240000}.get(value, 0)

    if u_data["balance"] < price:
        await query.message.reply_text(
            f"❌ Недостаточно средств. Заказ стоит {price:,} сумов, у вас {u_data['balance']:,} сумов.")
        return ConversationHandler.END

    context.user_data["buy_price"] = price
    await query.message.edit_text("✏️ Введите Telegram Юзернейм (@username) или ID получателя:")
    return BUY_USERNAME


async def buy_amount_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount_text = update.message.text.strip()
    if not amount_text.isdigit() or int(amount_text) <= 0:
        await update.message.reply_text("❌ Введите правильное целое число звёзд:")
        return BUY_AMOUNT

    value = int(amount_text)
    price = value * PRICE_PER_STAR
    u_data = get_user_data(update.effective_user.id)

    if u_data["balance"] < price:
        await update.message.reply_text(
            f"❌ Недостаточно средств! Стоимость {value} Stars — {price:,} сумов. У вас {u_data['balance']:,} сумов.")
        return ConversationHandler.END

    context.user_data["buy_value"] = value
    context.user_data["buy_price"] = price
    await update.message.reply_text("✏️ Введите Telegram Юзернейм (@username) или ID получателя:")
    return BUY_USERNAME


async def buy_username_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_username = update.message.text.strip()
    context.user_data["target_username"] = target_username
    prod_type = context.user_data["buy_type"]
    value = context.user_data["buy_value"]
    price = context.user_data["buy_price"]
    prod_name = f"{value} Stars" if prod_type == "stars" else f"Premium на {value} мес."

    text = f"📝 <b>Подтверждение покупки</b>\n\n📦 Товар: {prod_name}\n👤 Получатель: {target_username}\n💵 Стоимость: <b>{price:,} сумов</b>\n\nСписать деньги с баланса и отправить товар?"
    keyboard = [[InlineKeyboardButton("✅ Да, купить", callback_data="confirm_final_buy")],
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel_action")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return BUY_CONFIRM


async def buy_confirm_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    u_data = get_user_data(user_id)

    prod_type = context.user_data.get("buy_type")
    value = context.user_data.get("buy_value")
    price = context.user_data.get("buy_price")
    target = context.user_data.get("target_username")

    if u_data["balance"] < price:
        await query.message.edit_text("❌ Ошибка: Недостаточно средств.")
        return ConversationHandler.END

    u_data["balance"] -= price
    await query.message.edit_text("⏳ Запрос отправляется провайдеру...")

    api_success = await buy_stars_via_api(target, value) if prod_type == "stars" else await buy_premium_via_api(target,
                                                                                                                value)

    if api_success:
        await query.message.edit_text(
            f"✅ <b>Успешно отправлено!</b>\n\nТовар отправлен на аккаунт {target}.\nСписано: {price:,} сумов. Остаток: {u_data['balance']:,} сумов.",
            parse_mode="HTML")
    else:
        await query.message.edit_text(
            f"⏳ <b>Заказ принят в обработку</b>\n\nТовар будет доставлен оператором в течение нескольких минут.")
        prod_name = f"{value} Stars" if prod_type == "stars" else f"Premium {value} мес."
        await context.bot.send_message(chat_id=ADMIN_ID,
                                       text=f"⚠️ <b>ВНИМАНИЕ: СБОЙ АВТО-ВЫДАЧИ!</b>\n\nВыдайте заказ вручную:\n👤 Кому: {target}\n📦 Товар: {prod_name}")

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

        new_caption = (
            f"💰 <b>Пополнение баланса</b>\n"
            f"👤 Клиент ID: <code>{client_id}</code>\n"
            f"💵 Сумма: <b>{amount:,} сумов</b>\n\n"
            f"🟢 <b>ОДОБРЕНО! Баланс успешно зачислен клиенту.</b>"
        )
        try:
            await query.message.edit_caption(caption=new_caption, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Не удалось изменить подпись админу: {e}")

        try:
            await context.bot.send_message(chat_id=client_id,
                                           text=f"🎉 Ваш чек проверен! На ваш баланс зачислено {amount:,} сумов.")
        except Exception:
            pass

    elif data.startswith("adm_pay_no_"):
        await query.answer()
        client_id = int(data.split("_")[3])

        new_caption = (
            f"💰 <b>Пополнение баланса</b>\n"
            f"👤 Клиент ID: <code>{client_id}</code>\n\n"
            f"🔴 <b>ОТКЛОНЕНО! Чек был отклонен администратором.</b>"
        )
        try:
            await query.message.edit_caption(caption=new_caption, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Не удалось изменить подпись админу: {e}")

        try:
            await context.bot.send_message(chat_id=client_id,
                                           text="❌ Ваш чек был отклонен администратором. Если это ошибка, свяжитесь с поддержкой.")
        except Exception:
            pass


async def cancel_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Действие отменено.")
    context.user_data.clear()
    await start(update, context)
    return ConversationHandler.END


# --- ЗАПУСК ПРИЛОЖЕНИЯ ---

def main():
    # Запускаем фоновый веб-сервер для прохождения портов на Render
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
    app.add_handler(CallbackQueryHandler(menu_handler, pattern="^menu_|^shop_"))

    print("Бот успешно запущен и готов к автовыдачам!")
    app.run_polling()


if __name__ == "__main__":
    main()