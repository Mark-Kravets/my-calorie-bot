import os
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from groq import Groq

# Налаштування токенів
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

# Стани розмови
SELECT_LANG, ASK_NAME, ASK_GENDER, ASK_WEIGHT, ASK_HEIGHT, ASK_AGE, ASK_GOAL, ASK_PHOTO, MAIN_MENU = range(9)

logging.basicConfig(level=logging.INFO)

# Тексти для інтерфейсу
STRINGS = {
    'uk': {
        'start': "👋 Привіт! Я твій AI-дієтолог. Давай почнемо! Як тебе звати?",
        'gender': "Приємно познайомитись, {name}! Оберіть вашу стать:",
        'weight': "Яка твоя вага? (у кг, наприклад: 75)",
        'height': "Який твій зріст? (у см, наприклад: 180)",
        'age': "Скільки тобі повних років?",
        'goal': "Яка твоя мета сьогодні?",
        'photo': "Надішли фото для прогресу або тисни /skip, щоб одразу розрахувати калорії! 🚀",
        'wait': "Зачекай секунду, я вже рахую твої цифри... 🧐",
        'menu': "Обери пункт меню:",
        'btn_goal': ["🔥 Схуднути", "💪 Набрати масу", "⚖️ Підтримати вагу"],
        'btn_gender': ["🙋‍♂️ Чоловік", "🙋‍♀️ Жінка"],
        'btn_menu': ["🍽️ Що приготувати?", "📊 Моя норма", "💡 Порада дня"]
    },
    'ru': {
        'start': "👋 Привет! Я твой AI-диетолог. Начнем! Как тебя зовут?",
        'gender': "Приятно познакомиться, {name}! Выбери свой пол:",
        'weight': "Какой у тебя вес? (в кг, например: 70)",
        'height': "Какой твой рост? (в см, например: 175)",
        'age': "Сколько тебе полных лет?",
        'goal': "Какая твоя цель?",
        'photo': "Пришли фото прогресса или жми /skip, чтобы сразу посчитать калории! 🚀",
        'wait': "Секундочку, я уже считаю твои цифры... 🧐",
        'menu': "Выбери пункт меню:",
        'btn_goal': ["🔥 Похудеть", "💪 Набрать массу", "⚖️ Удержать вес"],
        'btn_gender': ["🙋‍♂️ Мужчина", "🙋‍♀️ Женщина"],
        'btn_menu': ["🍽️ Что приготовить?", "📊 Моя норма", "💡 Совет дня"]
    },
    'en': {
        'start': "👋 Hi! I'm your AI Dietitian. Let's start! What is your name?",
        'gender': "Nice to meet you, {name}! Select your gender:",
        'weight': "What is your weight? (kg, e.g.: 70)",
        'height': "What is your height? (cm, e.g.: 180)",
        'age': "How old are you?",
        'goal': "What is your goal?",
        'photo': "Send a photo or press /skip to calculate calories now! 🚀",
        'wait': "Wait a sec, I'm crunching the numbers... 🧐",
        'menu': "Select menu option:",
        'btn_goal': ["🔥 Lose weight", "💪 Gain muscle", "⚖️ Maintain weight"],
        'btn_gender': ["🙋‍♂️ Male", "🙋‍♀️ Female"],
        'btn_menu': ["🍽️ What to cook?", "📊 My stats", "💡 Daily tip"]
    }
}

def get_text(context, key):
    lang = context.user_data.get('lang', 'uk')
    return STRINGS[lang][key]

# --- AI Logic ---
def ask_ai(prompt):
    try:
        chat = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
        )
        return chat.choices[0].message.content
    except:
        return "AI is busy, but you are doing great!"

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    kb = ReplyKeyboardMarkup([["🇺🇦 Українська", "🇷🇺 Русский", "🇺🇸 English"]], resize_keyboard=True)
    await update.message.reply_text("🌍 Choose your language / Оберіть мову / Выберите язык:", reply_markup=kb)
    return SELECT_LANG

async def select_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "🇺🇦" in text: context.user_data['lang'] = 'uk'
    elif "🇷🇺" in text: context.user_data['lang'] = 'ru'
    else: context.user_data['lang'] = 'en'
    
    await update.message.reply_text(get_text(context, 'start'), reply_markup=ReplyKeyboardRemove())
    return ASK_NAME

async def ask_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    kb = ReplyKeyboardMarkup([get_text(context, 'btn_gender')], resize_keyboard=True)
    await update.message.reply_text(get_text(context, 'gender').format(name=update.message.text), reply_markup=kb)
    return ASK_GENDER

async def ask_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gender'] = update.message.text
    await update.message.reply_text(get_text(context, 'weight'), reply_markup=ReplyKeyboardRemove())
    return ASK_WEIGHT

async def ask_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['weight'] = update.message.text
    await update.message.reply_text(get_text(context, 'height'))
    return ASK_HEIGHT

async def ask_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['height'] = update.message.text
    await update.message.reply_text(get_text(context, 'age'))
    return ASK_AGE

async def ask_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['age'] = update.message.text
    kb = ReplyKeyboardMarkup([get_text(context, 'btn_goal')], resize_keyboard=True)
    await update.message.reply_text(get_text(context, 'goal'), reply_markup=kb)
    return ASK_GOAL

async def ask_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['goal'] = update.message.text
    await update.message.reply_text(get_text(context, 'photo'))
    return ASK_PHOTO

async def show_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_text(context, 'wait'))
    
    u = context.user_data
    lang_name = {'uk': 'Ukrainian', 'ru': 'Russian', 'en': 'English'}[u['lang']]
    
    prompt = (f"User: {u['name']}, {u['gender']}, {u['weight']}kg, {u['height']}cm, {u['age']} years old. "
              f"Goal: {u['goal']}. Calculate daily calories and give a fun supportive comment in {lang_name}. Short answer.")
    
    res = ask_ai(prompt)
    context.user_data['calories'] = res
    
    kb = ReplyKeyboardMarkup([get_text(context, 'btn_menu')], resize_keyboard=True)
    await update.message.reply_text(f"✨ {res}", reply_markup=kb)
    return MAIN_MENU

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Тут можна додати обробку "Що приготувати" тощо.
    await update.message.reply_text("Coming soon! Поки що я просто рахую твій результат.")
    return MAIN_MENU

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_LANG: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_lang)],
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_gender)],
            ASK_GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_weight)],
            ASK_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_height)],
            ASK_HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_age)],
            ASK_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_goal)],
            ASK_GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_photo)],
            ASK_PHOTO: [MessageHandler(filters.ALL, show_result), CommandHandler("skip", show_result)],
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    app.add_handler(conv)
    print("🤖 Бот запущений!")
    app.run_polling()

if __name__ == "__main__":
    main()
