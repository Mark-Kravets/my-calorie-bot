import os
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from groq import Groq

# Налаштування
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

# Стани
SELECT_LANG, ASK_NAME, ASK_GENDER, ASK_WEIGHT, ASK_HEIGHT, ASK_AGE, ASK_GOAL, ASK_PHOTO, MAIN_MENU, ASK_PRODUCTS = range(10)

logging.basicConfig(level=logging.INFO)

STRINGS = {
    'uk': {
        'start': "👋 Привіт! Я твій AI-дієтолог. Як тебе звати?",
        'gender': "Приємно познайомитись, {name}! Оберіть вашу стать:",
        'weight': "Яка твоя вага? (кг):",
        'height': "Який твій зріст? (см):",
        'age': "Скільки тобі років?",
        'goal': "Яка твоя мета?",
        'photo': "Надішли фото або тисни /skip для розрахунку! 🚀",
        'wait': "Секунду, я вже рахую... 🧐",
        'menu': "Обери пункт меню:",
        'products_req': "🛒 Напиши продукти, які у тебе є (через кому):",
        'btn_goal': ["🔥 Схуднути", "💪 Набрати масу", "⚖️ Підтримати вагу"],
        'btn_gender': ["🙋‍♂️ Чоловік", "🙋‍♀️ Жінка"],
        'btn_menu': ["🍽️ Що приготувати?", "📊 Моя норма", "💡 Порада дня"]
    },
    'ru': {
        'start': "👋 Привет! Я твой AI-диетолог. Как тебя зовут?",
        'gender': "Приятно познакомиться, {name}! Выбери свой пол:",
        'weight': "Какой у тебя вес? (кг):",
        'height': "Какой твой рост? (см):",
        'age': "Сколько тебе лет?",
        'goal': "Какая твоя цель?",
        'photo': "Пришли фото или жми /skip для расчета! 🚀",
        'wait': "Секундочку, я считаю... 🧐",
        'menu': "Выбери пункт меню:",
        'products_req': "🛒 Напиши продукты, которые есть (через запятую):",
        'btn_goal': ["🔥 Похудеть", "💪 Набрать массу", "⚖️ Удержать вес"],
        'btn_gender': ["🙋‍♂️ Мужчина", "🙋‍♀️ Женщина"],
        'btn_menu': ["🍽️ Что приготовить?", "📊 Моя норма", "💡 Совет дня"]
    }
}

def ask_ai(prompt):
    try:
        chat = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
        )
        return chat.choices[0].message.content
    except:
        return "AI error. Try again later."

# --- Хендлери ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = ReplyKeyboardMarkup([["🇺🇦 Українська", "🇷🇺 Русский"]], resize_keyboard=True)
    await update.message.reply_text("Оберіть мову / Выберите язык:", reply_markup=kb)
    return SELECT_LANG

async def select_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['lang'] = 'uk' if "🇺🇦" in update.message.text else 'ru'
    await update.message.reply_text(STRINGS[context.user_data['lang']]['start'], reply_markup=ReplyKeyboardRemove())
    return ASK_NAME

async def ask_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    lang = context.user_data['lang']
    kb = ReplyKeyboardMarkup([STRINGS[lang]['btn_gender']], resize_keyboard=True)
    await update.message.reply_text(STRINGS[lang]['gender'].format(name=update.message.text), reply_markup=kb)
    return ASK_GENDER

async def ask_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gender'] = update.message.text
    await update.message.reply_text(STRINGS[context.user_data['lang']]['weight'], reply_markup=ReplyKeyboardRemove())
    return ASK_WEIGHT

async def ask_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['weight'] = update.message.text
    await update.message.reply_text(STRINGS[context.user_data['lang']]['height'])
    return ASK_HEIGHT

async def ask_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['height'] = update.message.text
    await update.message.reply_text(STRINGS[context.user_data['lang']]['age'])
    return ASK_AGE

async def ask_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['age'] = update.message.text
    lang = context.user_data['lang']
    kb = ReplyKeyboardMarkup([STRINGS[lang]['btn_goal']], resize_keyboard=True)
    await update.message.reply_text(STRINGS[lang]['goal'], reply_markup=kb)
    return ASK_GOAL

async def ask_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['goal'] = update.message.text
    await update.message.reply_text(STRINGS[context.user_data['lang']]['photo'], reply_markup=ReplyKeyboardRemove())
    return ASK_PHOTO

async def show_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data['lang']
    await update.message.reply_text(STRINGS[lang]['wait'])
    u = context.user_data
    prompt = f"User: {u['gender']}, {u['weight']}kg, {u['height']}cm, {u['age']}y.o, Goal: {u['goal']}. Calculate calories in {lang}. Be funny and supportive."
    res = ask_ai(prompt)
    context.user_data['calories_report'] = res
    kb = ReplyKeyboardMarkup([STRINGS[lang]['btn_menu']], resize_keyboard=True)
    await update.message.reply_text(res, reply_markup=kb)
    return MAIN_MENU

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    lang = context.user_data.get('lang', 'uk')
    
    if any(word in text for word in ["норма", "stats"]):
        await update.message.reply_text(context.user_data.get('calories_report', "Error"))
    elif any(word in text for word in ["Порада", "Совет"]):
        res = ask_ai(f"Дай коротку пораду по харчуванню для цілі {context.user_data.get('goal')} мовою {lang}")
        await update.message.reply_text(f"💡 {res}")
    elif any(word in text for word in ["приготувати", "готовить"]):
        await update.message.reply_text(STRINGS[lang]['products_req'])
        return ASK_PRODUCTS
    return MAIN_MENU

async def handle_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data['lang']
    prods = update.message.text
    await update.message.reply_text("🤔...")
    res = ask_ai(f"У мене є: {prods}. Що приготувати? Напиши 2 рецепти мовою {lang}")
    kb = ReplyKeyboardMarkup([STRINGS[lang]['btn_menu']], resize_keyboard=True)
    await update.message.reply_text(res, reply_markup=kb)
    return MAIN_MENU

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_LANG: [MessageHandler(filters.TEXT, select_lang)],
            ASK_NAME: [MessageHandler(filters.TEXT, ask_gender)],
            ASK_GENDER: [MessageHandler(filters.TEXT, ask_weight)],
            ASK_WEIGHT: [MessageHandler(filters.TEXT, ask_height)],
            ASK_HEIGHT: [MessageHandler(filters.TEXT, ask_age)],
            ASK_AGE: [MessageHandler(filters.TEXT, ask_goal)],
            ASK_GOAL: [MessageHandler(filters.TEXT, ask_photo)],
            ASK_PHOTO: [MessageHandler(filters.ALL, show_result), CommandHandler("skip", show_result)],
            MAIN_MENU: [MessageHandler(filters.TEXT, handle_menu)],
            ASK_PRODUCTS: [MessageHandler(filters.TEXT, handle_products)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    app.add_handler(conv)
    app.run_polling()

if __name__ == "__main__":
    main()
