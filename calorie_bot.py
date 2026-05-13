import os
import logging
import re
import base64
import stripe
import httpx
import threading
import time

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

# ==================================
# ВСТАВЬ СВОИ КЛЮЧИ
# ==================================

TELEGRAM_TOKEN = "ТУТ_ТВОЙ_НОВЫЙ_TOKEN"
GROQ_API_KEY = "ТУТ_GROQ_KEY"
OPENROUTER_API_KEY = "ТУТ_OPENROUTER_KEY"
STRIPE_SECRET_KEY = "ТУТ_STRIPE_KEY"

BOT_USERNAME = "smart_kaloria_bot"

stripe.api_key = STRIPE_SECRET_KEY
client = Groq(api_key=GROQ_API_KEY)

# ==================================
# БЕСПЛАТНЫЕ ПОЛЬЗОВАТЕЛИ
# ==================================

FREE_USERS = [
    872550266,
]

# ==================================
# ОПЛАТИВШИЕ
# ==================================

PAID_USERS = {}

# ==================================
# СОСТОЯНИЯ
# ==================================

SELECT_LANG, ASK_NAME, ASK_GENDER, MAIN_MENU, ANALYZE_FOOD = range(5)

logging.basicConfig(level=logging.INFO)

# ==================================
# ТЕКСТЫ
# ==================================

STRINGS = {
    'uk': {
        'name_req': "👋 Привіт! Як тебе звати?",
        'bad_name': "❌ Без матів. Спробуй ще раз:",
        'gender': "Круте ім'я, {name}! Оберіть стать:",
        'wait': "AI думає... 🪄",
        'photo_req': "📸 Скидай фото їжі!",
        'btn_gender': ["🙋‍♂️ Чоловік", "🙋‍♀️ Жінка"],
        'btn_menu': ["📸 Що на тарілці?", "📊 Моя норма"],
    },

    'ru': {
        'name_req': "👋 Привет! Как тебя зовут?",
        'bad_name': "❌ Без матов. Попробуй еще раз:",
        'gender': "Крутое имя, {name}! Выбери пол:",
        'wait': "AI думает... 🪄",
        'photo_req': "📸 Скидывай фото еды!",
        'btn_gender': ["🙋‍♂️ Мужчина", "🙋‍♀️ Женщина"],
        'btn_menu': ["📸 Что на тарелке?", "📊 Моя норма"],
    }
}

# ==================================
# ПРОВЕРКА ИМЕНИ
# ==================================

def is_bad_content(text):

    banned = ['хуй', 'пизда', 'еблан', 'лох', 'сука', 'бля', 'чмо']

    text = text.lower()

    if any(word in text for word in banned):
        return True

    if len(text) < 2 or len(text) > 15:
        return True

    if not re.match(r"^[a-zA-Zа-яА-ЯіїєґІЇЄҐ\s]+$", text):
        return True

    return False

# ==================================
# ПРОВЕРКА ДОСТУПА
# ==================================

def has_access(user_id):

    if user_id in FREE_USERS:
        return True

    if user_id in PAID_USERS:

        if PAID_USERS[user_id] > time.time():
            return True

    return False

# ==================================
# STRIPE
# ==================================

async def create_payment_link(user_id):

    session = stripe.checkout.Session.create(

        payment_method_types=['card'],

        line_items=[{
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': 'Premium AI Food Bot - 3 недели'
                },
                'unit_amount': 400,
            },
            'quantity': 1,
        }],

        mode='payment',

        success_url=f'https://t.me/{BOT_USERNAME}',
        cancel_url=f'https://t.me/{BOT_USERNAME}',

        metadata={
            'telegram_id': str(user_id)
        }
    )

    return session.url

# ==================================
# START
# ==================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    kb = ReplyKeyboardMarkup(
        [["🇺🇦 Українська", "🇷🇺 Русский"]],
        resize_keyboard=True
    )

    await update.message.reply_text(
        "🇺🇦 Оберіть мову / 🇷🇺 Выберите язык:",
        reply_markup=kb
    )

    return SELECT_LANG

# ==================================
# ЯЗЫК
# ==================================

async def select_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data['lang'] = 'uk' if '🇺🇦' in update.message.text else 'ru'

    await update.message.reply_text(
        STRINGS[context.user_data['lang']]['name_req'],
        reply_markup=ReplyKeyboardRemove()
    )

    return ASK_NAME

# ==================================
# ИМЯ
# ==================================

async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE):

    name = update.message.text
    lang = context.user_data['lang']

    if is_bad_content(name):

        await update.message.reply_text(
            STRINGS[lang]['bad_name']
        )

        return ASK_NAME

    context.user_data['name'] = name

    kb = ReplyKeyboardMarkup(
        [STRINGS[lang]['btn_gender']],
        resize_keyboard=True
    )

    await update.message.reply_text(
        STRINGS[lang]['gender'].format(name=name),
        reply_markup=kb
    )

    return ASK_GENDER

# ==================================
# ПОЛ
# ==================================

async def handle_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data['gender'] = update.message.text

    return await show_main_menu(update, context)

# ==================================
# МЕНЮ
# ==================================

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

    u = context.user_data
    lang = u['lang']

    await update.message.reply_text(
        STRINGS[lang]['wait']
    )

    prompt = (
        f"User: {u['name']}, "
        f"{u.get('gender')}. "
        f"Healthy lifestyle. "
        f"Answer in {lang}. "
        f"Be funny."
    )

    res = client.chat.completions.create(

        messages=[{
            'role': 'user',
            'content': prompt
        }],

        model='llama-3.3-70b-versatile'

    ).choices[0].message.content

    context.user_data['report'] = res

    kb = ReplyKeyboardMarkup(
        [STRINGS[lang]['btn_menu']],
        resize_keyboard=True
    )

    await update.message.reply_text(
        res,
        reply_markup=kb
    )

    return MAIN_MENU

# ==================================
# ОБРАБОТКА МЕНЮ
# ==================================

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text
    lang = context.user_data['lang']
    user_id = update.effective_user.id

    # Фото еды
    if '📸' in text:

        if not has_access(user_id):

            pay_link = await create_payment_link(user_id)

            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "💳 Оплатить 4$ / 3 недели",
                    url=pay_link
                )
            ]])

            await update.message.reply_text(
                "🔒 Эта функция стоит 4$ на 3 недели.",
                reply_markup=kb
            )

            return MAIN_MENU

        await update.message.reply_text(
            STRINGS[lang]['photo_req']
        )

        return ANALYZE_FOOD

    # Норма
    elif '📊' in text:

        await update.message.reply_text(
            context.user_data.get('report', 'Error')
        )

    return MAIN_MENU

# ==================================
# АНАЛИЗ ФОТО
# ==================================

async def analyze_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    lang = context.user_data.get('lang', 'ru')

    await update.message.reply_text(
        STRINGS[lang]['wait']
    )

    photo_file = await update.message.photo[-1].get_file()

    photo_path = f'food_{update.effective_user.id}.jpg'

    await photo_file.download_to_drive(photo_path)

    with open(photo_path, 'rb') as image_file:

        base64_image = base64.b64encode(
            image_file.read()
        ).decode('utf-8')

    try:

        async with httpx.AsyncClient() as client_http:

            response = await client_http.post(

                url='https://openrouter.ai/api/v1/chat/completions',

                headers={
                    'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                    'Content-Type': 'application/json'
                },

                json={
                    'model': 'google/gemini-pro-1.5-exp',

                    'messages': [{
                        'role': 'user',

                        'content': [

                            {
                                'type': 'text',
                                'text': (
                                    f'Что на фото? '
                                    f'Сколько калорий? '
                                    f'Ответ на языке {lang}. '
                                    f'Коротко и смешно.'
                                )
                            },

                            {
                                'type': 'image_url',

                                'image_url': {
                                    'url':
                                    f'data:image/jpeg;base64,{base64_image}'
                                }
                            }
                        ]
                    }]
                },

                timeout=45.0
            )

            data = response.json()

            result = data['choices'][0]['message']['content']

    except Exception as e:

        logging.error(f'OpenRouter Error: {e}')

        result = 'Ошибка анализа фото.'

    finally:

        if os.path.exists(photo_path):
            os.remove(photo_path)

    kb = ReplyKeyboardMarkup(
        [STRINGS[lang]['btn_menu']],
        resize_keyboard=True
    )

    await update.message.reply_text(
        f'🍽️ {result}',
        reply_markup=kb
    )

    return MAIN_MENU

# ==================================
# FLASK WEBHOOK
# ==================================

web_app = Flask(__name__)

@web_app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():

    payload = request.json

    try:

        if payload['type'] == 'checkout.session.completed':

            session = payload['data']['object']

            user_id = int(
                session['metadata']['telegram_id']
            )

            PAID_USERS[user_id] = (
                time.time() + (21 * 24 * 60 * 60)
            )

            print(f'Оплата от {user_id}')

    except Exception as e:

        print(e)

    return '', 200

# ==================================
# FLASK START
# ==================================

def run_webhook():
    web_app.run(port=5000)

# ==================================
# MAIN
# ==================================

def main():

    threading.Thread(
        target=run_webhook
    ).start()

    app = Application.builder().token(
        TELEGRAM_TOKEN
    ).build()

    conv = ConversationHandler(

        entry_points=[
            CommandHandler('start', start)
        ],

        states={

            SELECT_LANG: [
                MessageHandler(
                    filters.TEXT,
                    select_lang
                )
            ],

            ASK_NAME: [
                MessageHandler(
                    filters.TEXT,
                    handle_name
                )
            ],

            ASK_GENDER: [
                MessageHandler(
                    filters.TEXT,
                    handle_gender
                )
            ],

            MAIN_MENU: [
                MessageHandler(
                    filters.TEXT,
                    handle_menu
                )
            ],

            ANALYZE_FOOD: [
                MessageHandler(
                    filters.PHOTO,
                    analyze_photo
                )
            ]
        },

        fallbacks=[
            CommandHandler('start', start)
        ]
    )

    app.add_handler(conv)

    print('Бот запущен...')

    app.run_polling()

if __name__ == '__main__':
    main()
