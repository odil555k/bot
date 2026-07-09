import logging
import json
import asyncio
import httpx
import sqlite3
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
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
BOT_TOKEN = "8844899781:AAHO-vgDPn4z5kJi5wCAX4o47OBQSwenkEU"
ADMIN_ID = 6636620529
CARD_NUMBER = "5614 6835 8985 1641"
ELDER_API_KEY = "60c5ea48d40a93662e2a3f6600ae3b03"  # API ключ от @elderstarsbot
ELDER_API_URL = "https://asosiy.elder.uz/api"

PRICE_PER_STAR = 210

# Состояния диалогов
REFILL_AMOUNT, CONFIRM_REFILL = range(2)
BUY_AMOUNT, BUY_USERNAME, BUY_CONFIRM = range(2, 5)

DB_FILE = "bot_database.db"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS users
                   (
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
    cursor.execute("SELECT balance, username, name, lang, is_banned FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if row is None:
        cursor.execute(
            "INSERT INTO users (user_id, username, name, balance, lang, is_banned) VALUES (?, ?, ?, 0, 'ru', 0)",
            (user_id, username or "", name or "")
        )
        conn.commit()
        res = {"balance": 0, "username": username or "", "name": name or "", "lang": "ru", "is_banned": False}
    else:
        res = {
            "balance": row[0],
            "username": row[1],
            "name": row[2],
            "lang": row[3],
            "is_banned": bool(row[4])
        }
    conn.close()
    return res


def update_user_balance(user_id, amount):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()


def update_user_lang(user_id, lang):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))
    conn.commit()
    conn.close()


def update_user_ban(user_id, is_banned):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (1 if is_banned else 0, user_id))
    conn.commit()
    conn.close()


def get_all_users():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, name, balance, is_banned FROM users")
    rows = cursor.fetchall()
    conn.close()
    return rows


# --- СИСТЕМА ДЛЯ ЗАЩИТЫ БАЛАНСОВ НА RENDER (АВТО-БЭКАП) ---
async def send_db_backup(context: ContextTypes.DEFAULT_TYPE):
    """Отправляет файл базы данных администратору в личные сообщения"""
    if not os.path.exists(DB_FILE):
        return
    try:
        with open(DB_FILE, 'rb') as f:
            await context.bot.send_document(
                chat_id=ADMIN_ID,
                document=f,
                caption="📦 <b>Авто-бэкап базы данных.</b>\nСохраните этот файл! Если при обновлении кода на Render пропадут балансы, просто закиньте этот файл обратно в проект."
            )
        logging.info("Бэкап базы данных успешно отправлен админу.")
    except Exception as e:
        logging.error(f"Ошибка отправки бэкапа: {e}")


# --- ФЕЙКОВЫЙ ВЕБ-СЕРВЕР ДЛЯ ОБМАНА RENDER ---
class WebServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Bot is running smoothly!")

    def log_message(self, format, *args):
        return


def run_web_server():
    port = int(os.environ.get("PORT", 80))
    server = HTTPServer(("0.0.0.0", port), WebServerHandler)
    logging.info(f"🌐 Фейковый веб-сервер запущен на порту {port} для Render")
    server.serve_forever()


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
        "buy_stars_enter": "✏️ Сколько Telegram Stars (звёзд) вы хотите купить? Введите число:",
        "buy_no_money": "❌ Недостаточно средств. Заказ стоит {price:,} сумов, у вас {balance:,} сумов.",
        "buy_username_enter": "✏️ Введите Telegram Юзернейм получателя (БЕЗ знака @, например: durov):",
        "buy_confirm_title": "📝 <b>Подтверждение покупки</b>\n\n📦 Товар: {prod_name}\n👤 Получатель: {target}\n💵 Стоимость: <b>{price:,} сумов</b>\n\nСписать деньги с баланса?",
        "buy_confirm_btn": "✅ Да, купить",
        "banned_msg": "❌ Вы заблокированы в этом боте."
    },
    "uz": {
        "welcome": "👋 Salom, {name}!\nTelegram Stars & Premium do'koniga xush kelibsiz.\n\n💰 Sizning balansingiz: {balance:,} so'm",
        "btn_shop": "🛍 Xizmatlarni sotib olish",
        "btn_refill": "💳 Balansni to'ldirish",
        "btn_profile": "👤 Shaxsiy kabinet",
        "btn_back": "⬅️ Ortga",
        "btn_cancel": "❌ Bekor qilish",
        "profile_text": "👤 Shaxsiy kabinet\n\n🆔 Sizning ID: <code>{user_id}</code>\n💰 Balans: {balance:,} so'm\n\n🌐 Tilni o'zgartirish / Сменить язык:",
        "shop_main": "🛍 <b>Kategoriyani tanlang:</b>",
        "shop_stars_cat": "💎 Telegram Stars (Yulduzlar)",
        "shop_prem_cat": "🌟 Telegram Premium (Obuna)",
        "stars_desc": "💎 <b>Telegram Stars (Yulduzlar)</b>\n\n💵 Bizning tarif: 1 ta yulduz uchun {price} so'm.",
        "stars_manual": "✏️ Miqdorni qo'da kiritish",
        "prem_desc": "🌟 <b>Telegram Premium narxlari:</b>\n\n🔹 3 oy — 75,000 so'm\n🔹 6 oy — 130,000 so'm\n🔹 12 oy — 240,000 so'm",
        "refill_start": "💳 To'ldirish summasini so'mda kiriting (masalan: 50000):",
        "refill_bad_num": "❌ Iltimos, to'g'ri son kiriting.",
        "refill_invoice": "To'ldirish uchun ariza: <b>{amount:,} so'm</b>\n\nUshbu summani aynan mana shu kartaga o'tkazing:\n<code>{card}</code>\n\nTarixiy to'lovdan so'ng chekning rasmi yoki skrinshotini shu chatga yuboring.",
        "refill_bad_photo": "❌ Iltimos, aynan rasm yoki chek skrinshotini yuboring.",
        "refill_done": "⏳ Sizning chekingiz administratorga tekshirish uchun yuborildi.",
        "buy_stars_enter": "✏️ Qancha Telegram Stars (yulduz) sotib olmoqchisiz?",
        "buy_no_money": "❌ Mablag' yetarli emas.",
        "buy_username_enter": "✏️ Qabul qiluvchining Telegram юзернейmini kiriting (@ belgisiz, masalan: durov):",
        "buy_confirm_title": "📝 <b>Xaridni tasdiqlash</b>\n\n📦 Mahsulot: {prod_name}\n👤 Qabul qiluvchi: {target}\n💵 Qiymati: <b>{price:,} so'm</b>",
        "buy_confirm_btn": "✅ Ha, sotib olish",
        "banned_msg": "❌ Siz ushbu botda bloklangansiz."
    }
}


async def is_user_banned(update: Update) -> bool:
    uid = update.effective_user.id
    u_data = get_user_data(uid)
    if u_data["is_banned"]:
        msg = TEXTS[u_data["lang"]]["banned_msg"]
        if update.message:
            await update.message.reply_text(msg)
        elif update.callback_query:
            await update.callback_query.answer(msg, show_alert=True)
        return True
    return False


# --- ИНТЕГРАЦИЯ ELDER.UZ API ---
async def send_order_to_elder(prod_type: str, value: int, target: str) -> bool:
    target = target.replace("@", "").strip()
    headers = {
        "X-Api-Key": ELDER_API_KEY,
        "Content-Type": "application/json"
    }

    if prod_type == "stars":
        url = f"{ELDER_API_URL}/stars/buy"
        payload = {"username": target, "amount": value}
    else:
        url = f"{ELDER_API_URL}/premium/buy"
        payload = {"username": target, "months": value}

    try:
        async with httpx.AsyncClient() as client:
            logging.info(f"Отправка запроса на {url} с телом {payload}")
            response = await client.post(url, headers=headers, json=payload, timeout=25.0)
            if response.status_code == 200:
                res_json = response.json()
                if res_json.get("success") is True:
                    logging.info(f"Успешный ответ от Elder API: {res_json}")
                    return True
                else:
                    logging.error(f"Elder API вернул success=False: {res_json}")
            else:
                logging.error(f"Ошибка Elder API. Статус: {response.status_code}, Ответ: {response.text}")
    except Exception as e:
        logging.error(f"Критическая ошибка при отправке запроса к Elder API: {e}")
    return False


# --- МЕНЮ И КОМАНДЫ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_user_banned(update): return ConversationHandler.END
    context.user_data.clear()

    user = update.effective_user
    u_data = get_user_data(user.id, user.username, user.first_name)
    t = TEXTS[u_data["lang"]]

    inline_keyboard = [
        [InlineKeyboardButton(t["btn_shop"], callback_data="main_shop")],
        [InlineKeyboardButton(t["btn_refill"], callback_data="main_refill"),
         InlineKeyboardButton(t["btn_profile"], callback_data="main_profile")]
    ]
    text = t["welcome"].format(name=user.first_name, balance=u_data['balance'])

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard))
        msg = await update.message.reply_text(".", reply_markup=ReplyKeyboardRemove())
        await msg.delete()
    else:
        await update.callback_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard))
    return ConversationHandler.END


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


async def inline_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_user_banned(update): return
    query = update.callback_query
    await query.answer()
    u_data = get_user_data(query.from_user.id)
    t = TEXTS[u_data["lang"]]

    if query.data.startswith("setlang_"):
        new_lang = query.data.split("_")[1]
        update_user_lang(query.from_user.id, new_lang)
        await show_profile(update, context)
        return

    if query.data == "back_to_main":
        inline_keyboard = [
            [InlineKeyboardButton(t["btn_shop"], callback_data="main_shop")],
            [InlineKeyboardButton(t["btn_refill"], callback_data="main_refill"),
             InlineKeyboardButton(t["btn_profile"], callback_data="main_profile")]
        ]
        text = t["welcome"].format(name=query.from_user.first_name, balance=u_data['balance'])
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard))
        return

    if query.data == "main_shop":
        keyboard = [
            [InlineKeyboardButton(t["shop_stars_cat"], callback_data="shop_stars")],
            [InlineKeyboardButton(t["shop_prem_cat"], callback_data="shop_premium")],
            [InlineKeyboardButton(t["btn_back"], callback_data="back_to_main")]
        ]
        await query.message.edit_text(t["shop_main"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return

    if query.data == "main_profile":
        await show_profile(update, context)
        return

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

    if query.data == "shop_premium":
        keyboard = [
            [InlineKeyboardButton("🚀 3 Oy / Mes (75k)", callback_data="buy_prem_fixed_3")],
            [InlineKeyboardButton("🚀 6 Oy / Mes (130k)", callback_data="buy_prem_fixed_6")],
            [InlineKeyboardButton("🚀 12 Oy / Mes (240k)", callback_data="buy_prem_fixed_12")],
            [InlineKeyboardButton(t["btn_back"], callback_data="main_shop")]
        ]
        await query.message.edit_text(t["prem_desc"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return


# --- ПОПОЛНЕНИЕ ---
async def refill_start_from_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    u_data = get_user_data(query.from_user.id)
    await query.message.edit_text(text=TEXTS[u_data["lang"]]["refill_start"])
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

    if not (update.message.photo or (
            update.message.document and update.message.document.mime_type.startswith("image/"))):
        await update.message.reply_text(TEXTS[u_data["lang"]]["refill_bad_photo"])
        return CONFIRM_REFILL

    fid = update.message.photo[-1].file_id if update.message.photo else update.message.document.file_id
    kb = [[InlineKeyboardButton("✅ Одобрить", callback_data=f"adm_pay_yes_{user.id}_{amount}"),
           InlineKeyboardButton("❌ Отклонить", callback_data=f"adm_pay_no_{user.id}")]]
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=fid,
                                 caption=f"💰 Пополнение! ID: {user.id}\nСумма: {amount:,} сумов",
                                 reply_markup=InlineKeyboardMarkup(kb))
    await update.message.reply_text(TEXTS[u_data["lang"]]["refill_done"])
    return ConversationHandler.END


# --- ПОКУПКА ---
async def buy_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    u_data = get_user_data(query.from_user.id)
    t = TEXTS[u_data["lang"]]

    if data == "buy_stars_manual":
        context.user_data["buy_type"] = "stars"
        await query.message.edit_text(t["buy_stars_enter"])
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

    prod_type = context.user_data.get("buy_type")
    value = context.user_data.get("buy_value")
    target = context.user_data.get("target_username")
    price = context.user_data.get("buy_price", 0)

    if u_data["balance"] < price:
        await query.message.edit_text("❌ Ошибка: недостаточно средств.")
        return ConversationHandler.END

    await query.message.edit_text("🔄 Подождите секундочку...")
    success = await send_order_to_elder(prod_type, value, target)

    if success:
        update_user_balance(query.from_user.id, -price)
        await query.message.edit_text(f"✅ Успешно! Заказ на {value} {prod_type} для {target} отправлен и оплачен.")
        try:
            await context.bot.send_message(chat_id=ADMIN_ID,
                                           text=f"🚀 Авто-заказ через API!\nЮзер: {query.from_user.id}\nТовар: {value} {prod_type}\nКуда: {target}")
        except Exception:
            pass
    else:
        await query.message.edit_text(
            "❌ Произошла ошибка на стороне API поставщика. Деньги не списаны. Проверьте баланс на Elder.uz или обратитесь к админу.")

    context.user_data.clear()
    return ConversationHandler.END


# --- АДМИН ПАНЕЛЬ ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return

    keyboard = [
        [InlineKeyboardButton("👥 Список пользователей", callback_data="admin_list_users_0")],
        [InlineKeyboardButton("❌ Закрыть панель", callback_data="admin_close")]
    ]

    text = (
        "🛠 <b>Панель администратора</b>\n\n"
        "Для управления пользователями используйте быстрые команды:\n"
        "👉 <code>/setbal [ID] [сумма]</code> — изменить баланс\n"
        "👉 <code>/ban [ID]</code> — забанить\n"
        "👉 <code>/unban [ID]</code> — разбанить\n"
        "👉 <code>/msg [ID] [текст]</code> — отправить сообщение\n\n"
        "<i>Пример: /setbal 12345678 50000</i>"
    )
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


# --- ТВОЙ ОБНОВЛЕННЫЙ ОБРАБОТЧИК АДМИН-КНОПОК ---
async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID: return
    await query.answer()

    if query.data == "admin_close":
        await query.message.delete()
        return

    if query.data.startswith("admin_list_users_"):
        page = int(query.data.split("_")[-1])
        all_users = get_all_users()
        total_users = len(all_users)

        if total_users == 0:
            await query.message.reply_text("⚠️ База данных пользователей пуста.")
            return

        per_page = 15
        start_idx = page * per_page
        end_idx = start_idx + per_page

        users_page = all_users[start_idx:end_idx]
        total_pages = (total_users + per_page - 1) // per_page

        rep = f"👥 <b>Все пользователи вашего бота (Страница {page + 1}/{total_pages}):</b>\n"
        rep += f"Всего человек запустили бота: <b>{total_users}</b>\n\n"

        for uid, username, name, balance, is_banned in users_page:
            # ПОЛНОСТЬЮ УБРАЛИ вывод Имени и Юзернейма (как ты просил)
            rep += f"• 🆔 <b>ID:</b> <code>{uid}</code> | <b>Баланс:</b> {balance:,} сум | <b>Бан:</b> {'⛔' if is_banned else '🟢'}\n───────────────────\n"

        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"admin_list_users_{page - 1}"))
        if end_idx < total_users:
            nav_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"admin_list_users_{page + 1}"))

        nav_buttons.append(InlineKeyboardButton("❌ Закрыть", callback_data="admin_close"))

        kb = []
        if len(nav_buttons) > 1 and nav_buttons[-1].text == "❌ Закрыть":
            kb.append(nav_buttons[:-1])
            kb.append([nav_buttons[-1]])
        else:
            kb.append(nav_buttons)

        try:
            await query.message.edit_text(rep, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        except Exception:
            await query.message.reply_text(rep, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")


# --- БЫСТРЫЕ КОМАНДЫ АДМИНИСТРАТОРА ---
async def cmd_setbal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("❌ Ошибка. Формат: <code>/setbal [ID] [сумма]</code>", parse_mode="HTML")
        return

    tgt_id, amt_str = context.args[0], context.args[1]
    if tgt_id.isdigit() and (amt_str.isdigit() or (amt_str.startswith("-") and amt_str[1:].isdigit())):
        tgt_id = int(tgt_id)
        amount = int(amt_str)
        update_user_balance(tgt_id, amount)
        new_data = get_user_data(tgt_id)
        await update.message.reply_text(
            f"✅ Баланс ID <code>{tgt_id}</code> изменен на {amount:+,}. Текущий: {new_data['balance']:,} сум.",
            parse_mode="HTML")
        try:
            await context.bot.send_message(chat_id=tgt_id,
                                           text=f"🔔 Твой баланс изменен на {amount:+,} сум.\n💰 Текущий баланс: {new_data['balance']:,} сум.")
        except Exception:
            pass
    else:
        await update.message.reply_text("❌ Укажите корректный ID и число суммы.")


async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: return
    tgt = context.args[0]
    if tgt.isdigit():
        update_user_ban(int(tgt), True)
        await update.message.reply_text(f"⛔ Пользователь {tgt} ЗАБЛОКИРОВАН.")


async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: return
    tgt = context.args[0]
    if tgt.isdigit():
        update_user_ban(int(tgt), False)
        await update.message.reply_text(f"🟢 Пользователь {tgt} РАЗБЛОКИРОВАН.")


async def cmd_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args or len(context.args) < 2: return
    tgt_id = context.args[0]
    text_to_send = " ".join(context.args[1:])
    if tgt_id.isdigit():
        try:
            await context.bot.send_message(chat_id=int(tgt_id),
                                           text=f"✉️ <b>Сообщение от админа:</b>\n\n{text_to_send}", parse_mode="HTML")
            await update.message.reply_text("✅ Отправлено!")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")


async def admin_pay_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("adm_pay_yes_"):
        _, _, _, cid, amt = query.data.split("_")
        update_user_balance(int(cid), int(amt))
        await query.message.edit_caption("🟢 Одобрено!")
        try:
            await context.bot.send_message(chat_id=int(cid), text="🎉 Ваш баланс пополнен!")
        except Exception:
            pass
        # Сразу после одобрения шлем бэкап базы, чтобы новые деньги точно зафиксировались!
        await send_db_backup(context)

    elif query.data.startswith("adm_pay_no_"):
        await query.message.edit_caption("🔴 Отклонено!")


def main():
    init_db()
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("setbal", cmd_setbal))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("msg", cmd_msg))
    app.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^admin_"))

    app.add_handler(CommandHandler("start", start))

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

    app.add_handler(CallbackQueryHandler(admin_pay_buttons, pattern="^adm_pay_"))
    app.add_handler(CallbackQueryHandler(inline_handler, pattern="^shop_|^setlang_|^main_|^back_to_main$"))

    # Настраиваем автоматический бэкап базы данных админу в ЛС раз в час (3600 секунд)
    if app.job_queue:
        app.job_queue.run_repeating(send_db_backup, interval=3600, first=10)

    app.run_polling()


if __name__ == "__main__":
    main()