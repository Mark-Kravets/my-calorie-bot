import os
import logging
import re
import base64
import time
import threading
import httpx
import stripe
from flask import Flask, request
from groq import Groq

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

# --- НАЛАШТУВАННЯ КЛЮЧІВ ---
# Рекомендую використовувати os.environ.get("KEY_NAME")
TELEGRAM_TOKEN = "ТВІЙ_ТЕЛЕГРАМ_ТОКЕН"
GROQ_API_KEY = "ТВІЙ_GROQ_КЛЮЧ"
OPENROUTER_API_KEY = "ТВІЙ_OPENROUTER_КЛЮЧ"
STRIPE_SECRET_KEY = "ТВІЙ_STRIPE_КЛЮЧ"
BOT_USERNAME = "smart_kaloria_bot"

# Ініціалізація клієнтів
stripe.api_key = STRIPE_SECRET_KEY
groq_client = Groq(api_key=GROQ_API_KEY)

# База даних (у пам'яті - скидається при перезапуску)
FREE_USERS = [872550266]  # Твій ID
PAID_USERS = {}  # {user_id: timestamp_expiry}

# Стани діалогу
SELECT_LANG, ASK_NAME, ASK_GENDER, MAIN_MENU, ANALYZE_FOOD = range(5)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

STRINGS = {
    'uk': {
        'name_req': "👋 Привіт! Як тебе звати?",
        'bad_name': "❌ Будь ласка, введи нормальне ім'я без символів та лайки:",
        'gender': "Круте ім'я, {name}! Оберіть стать:",
        'wait': "AI чаклує... 🪄",
        'photo_req': "📸 Скидай фото їжі, а я розберу її на атоми (і калорії)!",
        'btn_gender': ["🙋‍♂️ Чоловік", "🙋‍♀️ Жінка"],
        'btn_menu': ["📸 Що на тарілці?", "📊 Моя норма"],
        'pay_msg': "🔒 Ця функція доступна у Premium. Вартість: 4$ на 3 тижні.",
        'pay_btn': "💳 Оплатити Premium"
    },
    'ru': {
        'name_req': "👋 Привет! Как тебя зовут?",
        'bad_name': "❌ Пожалуйста, введи нормальное имя без матов и цифр:",
        'gender': "Крутое имя, {name}! Выбери пол:",
        'wait': "AI колдует... 🪄",
        'photo_req': "📸 Скидывай фото еды, а я посчитаю калории!",
        'btn_gender': ["🙋‍♂️ Мужчина", "🙋‍♀️ Женщина"],
        'btn_menu': ["📸 Что на тарелке?", "📊 Моя норма"],
        'pay_msg': "🔒 Эта функция доступна в Premium. Цена: 4$ на 3 недели.",
        'pay_btn': "💳 Оплатить Premium"
    }
}

# --- ДОПОМІЖНІ ФУНКЦІЇ ---

def is_bad_content(text):
    banned = ['хуй', 'пизда', 'еблан', 'лох', 'сука', 'бля', 'чмо']
    text = text.lower()
    if any(word in text for word in banned): return True
    if len(text) < 2 or len(text) > 15: return True
    if not re.match(r"^[a-zA-Zа-яА-ЯіїєґІЇЄҐ\s]+$", text): return True
    return False

def has_access(user_id):
    if user_id in FREE_USERS: return True
    expiry = PAID_USERS.get(user_id)
    if expiry and expiry > time.time(): return True
    return False

async def create_payment_link(user_id):
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {'name': 'Premium AI Food Bot - 3 тижні'},
                    'unit_amount': 400, # 4.00 USD
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f'https://t.me/{BOT_USERNAME}',
            cancel_url=f'https://t.me/{BOT_USERNAME}',
            metadata={'telegram_id': str(user_id)}
        )
        return session.url
    except Exception as e:
        logging.error(f"Stripe error: {e}")
        return None

# --- ЛОГІКА ТЕЛЕГРАМ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = ReplyKeyboardMarkup([["🇺🇦 Українська", "🇷🇺 Русский"]], resize_keyboard=True)
    await update.message.reply_text("🇺🇦 Оберіть мову / 🇷🇺 Выберите язык:", reply_markup=kb)
    return SELECT_LANG

async def select_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = 'uk' if '🇺🇦' in update.message.text else 'ru'
    context.user_data['lang'] = lang
    await update.message.reply_text(STRINGS[lang]['name_req'], reply_markup=ReplyKeyboardRemove())
    return ASK_NAME

async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    lang = context.user_data['lang']
    if is_bad_content(name):
        await update.message.reply_text(STRINGS[lang]['bad_name'])
        return ASK_NAME
    
    context.user_data['name'] = name
    kb = ReplyKeyboardMarkup([STRINGS[lang]['btn_gender']], resize_keyboard=True)
    await update.message.reply_text(STRINGS[lang]['gender'].format(name=name), reply_markup=kb)
    return ASK_GENDER

async def handle_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gender'] = update.message.text
    return await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = context.user_data
    lang = u['lang']
    await update.message.reply_text(STRINGS[lang]['wait'])

    prompt = f"User: {u['name']}, {u.get('gender')}. Give a funny 2-sentence greeting about healthy lifestyle in {lang}."
    try:
        res = groq_client.chat.completions.create(
            messages=[{'role': 'user', 'content': prompt}],
            model='llama-3.3-70b-versatile'
        ).choices[0].message.content
        u['report'] = res
    except:
        res = "Привіт! Давай почнемо трекати їжу!"

    kb = ReplyKeyboardMarkup([STRINGS[lang]['btn_menu']], resize_keyboard=True)
    await update.message.reply_text(res, reply_markup=kb)
    return MAIN_MENU

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    lang = context.user_data['lang']
    user_id = update.effective_user.id

    if '📸' in text:
        if not has_access(user_id):
            pay_link = await create_payment_link(user_id)
            if pay_link:
                kb = InlineKeyboardMarkup([[InlineKeyboardButton(STRINGS[lang]['pay_btn'], url=pay_link)]])
                await update.message.reply_text(STRINGS[lang]['pay_msg'], reply_markup=kb)
            else:
                await update.message.reply_text("Помилка платіжної системи.")
            return MAIN_MENU
        
        await update.message.reply_text(STRINGS[lang]['photo_req'])
        return ANALYZE_FOOD

    elif '📊' in text:
        await update.message.reply_text(context.user_data.get('report', 'Спочатку заповни анкету!'))
    
    return MAIN_MENU

async def analyze_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'uk')
    await update.message.reply_text(STRINGS[lang]['wait'])

    photo_file = await update.message.photo[-1].get_file()
    photo_path = f"food_{update.effective_user.id}.jpg"
    await photo_file.download_to_drive(photo_path)

    with open(photo_path, 'rb') as img:
        base64_image = base64.b64encode(img.read()).decode('utf-8')

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                json={
                    "model": "google/gemini-pro-1.5-exp",
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Identify food and calories. Language: {lang}. Funny and short."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                        ]
                    }]
                },
                timeout=45.0
            )
            result = response.json()['choices'][0]['message']['content']
    except Exception as e:
        logging.error(f"AI Error: {e}")
        result = "Не вдалося розпізнати фото."
    finally:
        if os.path.exists(photo_path): os.remove(photo_path)

    kb = ReplyKeyboardMarkup([STRINGS[lang]['btn_menu']], resize_keyboard=True)
    await update.message.reply_text(f"🍽️ {result}", reply_markup=kb)
    return MAIN_MENU

# --- FLASK ДЛЯ WEBHOOK (STRIPE) ---

web_app = Flask(__name__)

@web_app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    # Примітка: Для повної перевірки потрібен STRIPE_WEBHOOK_SECRET
    # Тут спрощена версія для обробки JSON
    event = request.json
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = int(session['metadata']['telegram_id'])
        PAID_USERS[user_id] = time.time() + (21 * 24 * 60 * 60) # 21 день
        logging.info(f"User {user_id} paid successfully!")
    return '', 200

def run_flask():
    web_app.run(host='0.0.0.0', port=5000)

# --- MAIN ---

def main():
    # Запуск Flask у фоні
    threading.Thread(target=run_flask, daemon=True).start()

    # Запуск Telegram бот
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECT_LANG: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_lang)],
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name)],
            ASK_GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_gender)],
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu)],
            ANALYZE_FOOD: [MessageHandler(filters.PHOTO, analyze_photo)]
        },
        fallbacks=[CommandHandler('start', start)]
    )

    app.add_handler(conv)
    logging.info("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
