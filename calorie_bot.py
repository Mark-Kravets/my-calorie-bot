import os
import logging
import re
import base64
import httpx  # Додано для запитів до OpenRouter
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from groq import Groq

# --- НАЛАШТУВАННЯ ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

# Список VIP-користувачів
VIP_USERS = [123456789, 987654321] 

client = Groq(api_key=GROQ_API_KEY)

# Стани
SELECT_LANG, ASK_NAME, ASK_GENDER, ASK_WEIGHT, ASK_HEIGHT, ASK_AGE, ASK_GOAL, MAIN_MENU, ANALYZE_FOOD = range(9)

logging.basicConfig(level=logging.INFO)

STRINGS = {
    'uk': {
        'name_req': "👋 Привіт! Як тебе звати?",
        'bad_name': "❌ Ей, пиши адекватно! Без матів. Спробуй ще раз:",
        'gender': "Круте ім'я, {name}! Оберіть стать:",
        'wait': "Секунду, AI чаклує... 🪄",
        'photo_req': "📸 Скидай фото їжі, я гляну що там по калоріях!",
        'menu': "Головне меню:",
        'btn_gender': ["🙋‍♂️ Чоловік", "🙋‍♀️ Жінка"],
        'btn_menu': ["📸 Що на тарілці?", "📊 Моя норма", "💡 Порада"],
        'premium_msg': "💎 Ця функція доступна у Premium версії. Але для тебе — безкоштовно!"
    },
    'ru': {
        'name_req': "👋 Привет! Как тебя зовут?",
        'bad_name': "❌ Пиши адекватно! Без матов. Попробуй еще раз:",
        'gender': "Крутое имя, {name}! Выбери пол:",
        'wait': "Секунду, AI колдует... 🪄",
        'photo_req': "📸 Кидай фото еды, я гляну что там по калориям!",
        'menu': "Главное меню:",
        'btn_gender': ["🙋‍♂️ Мужчина", "🙋‍♀️ Женщина"],
        'btn_menu': ["📸 Что на тарелке?", "📊 Моя норма", "💡 Совет"],
        'premium_msg': "💎 Эта функция доступна в Premium. Но для тебя — бесплатно!"
    }
}

# --- ПЕРЕВІРКИ ---
def is_bad_content(text):
    banned = ['хуй', 'пизда', 'еблан', 'лох', 'сука', 'бля', 'чмо']
    text = text.lower()
    if any(word in text for word in banned): return True
    if len(text) < 2 or len(text) > 15: return True
    if not re.match(r"^[a-zA-Zа-яА-ЯіїєґІЇЄҐ\s]+$", text): return True
    return False

# --- ЛОГІКА БОТА ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = ReplyKeyboardMarkup([["🇺🇦 Українська", "🇷🇺 Русский"]], resize_keyboard=True)
    await update.message.reply_text("🇺🇦 Оберіть мову / 🇷🇺 Выберите язык:", reply_markup=kb)
    return SELECT_LANG

async def select_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['lang'] = 'uk' if "🇺🇦" in update.message.text else 'ru'
    await update.message.reply_text(STRINGS[context.user_data['lang']]['name_req'], reply_markup=ReplyKeyboardRemove())
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

# (Пропущені етапи ASK_WEIGHT, ASK_HEIGHT тощо — реалізуй за аналогією)
# Для прикладу перескакуємо на MAIN_MENU після статі:
async def handle_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gender'] = update.message.text
    return await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = context.user_data
    lang = u['lang']
    await update.message.reply_text(STRINGS[lang]['wait'])
    
    prompt = f"User: {u['name']}, {u.get('gender')}. Goal: Healthy lifestyle. Calculate calories in {lang}. Be funny."
    res = client.chat.completions.create(messages=[{"role":"user","content":prompt}], model="llama-3.3-70b-versatile").choices[0].message.content
    context.user_data['report'] = res
    
    kb = ReplyKeyboardMarkup([STRINGS[lang]['btn_menu']], resize_keyboard=True)
    await update.message.reply_text(res, reply_markup=kb)
    return MAIN_MENU

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    lang = context.user_data['lang']
    user_id = update.effective_user.id

    if "📸" in text:
        if user_id in VIP_USERS:
            await update.message.reply_text(STRINGS[lang]['premium_msg'])
        await update.message.reply_text(STRINGS[lang]['photo_req'])
        return ANALYZE_FOOD
    
    elif "📊" in text:
        await update.message.reply_text(context.user_data.get('report', "Error"))
    
    return MAIN_MENU

# НОВА ФУНКЦІЯ АНАЛІЗУ ЧЕРЕЗ OPENROUTER
async def analyze_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get('lang', 'uk')
    await update.message.reply_text(STRINGS[lang]['wait'])
    
    # 1. Отримуємо фото
    photo_file = await update.message.photo[-1].get_file()
    # Використовуємо user_id у назві, щоб уникнути конфліктів файлів
    photo_path = f"food_{update.effective_user.id}.jpg"
    await photo_file.download_to_drive(photo_path)
    
    # 2. Кодуємо в base64
    with open(photo_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')

    # 3. Запит до OpenRouter
    try:
        async with httpx.AsyncClient() as client_http:
            response = await client_http.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "google/gemini-pro-1.5-exp", 
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": f"Що на цьому фото? Скільки приблизно калорій? Відповідь строго на мові: {lang}. Будь коротким і веселим."},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                            ]
                        }
                    ]
                },
                timeout=45.0
            )
            
            data = response.json()
            result = data['choices'][0]['message']['content']
    except Exception as e:
        logging.error(f"OpenRouter Error: {e}")
        result = "Ой, щось пішло не так при аналізі фото. Спробуй пізніше!"
    finally:
        # Видаляємо тимчасовий файл
        if os.path.exists(photo_path):
            os.remove(photo_path)
    
    kb = ReplyKeyboardMarkup([STRINGS[lang]['btn_menu']], resize_keyboard=True)
    await update.message.reply_text(f"🍽️ {result}", reply_markup=kb)
    return MAIN_MENU

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_LANG: [MessageHandler(filters.TEXT, select_lang)],
            ASK_NAME: [MessageHandler(filters.TEXT, handle_name)],
            ASK_GENDER: [MessageHandler(filters.TEXT, handle_gender)],
            MAIN_MENU: [MessageHandler(filters.TEXT, handle_menu)],
            ANALYZE_FOOD: [MessageHandler(filters.PHOTO, analyze_photo)]
        },
        fallbacks=[CommandHandler("start", start)]
    )
    app.add_handler(conv)
    print("Бот запущений через OpenRouter...")
    app.run_polling()

if __name__ == "__main__":
    main()
