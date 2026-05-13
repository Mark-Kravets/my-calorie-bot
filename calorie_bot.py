import os
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from groq import Groq

# Налаштування
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

# Стани
ASK_NAME, ASK_WEIGHT, ASK_HEIGHT, ASK_AGE, ASK_GOAL, ASK_PHOTO, MAIN_MENU, ASK_PRODUCTS = range(8)

logging.basicConfig(level=logging.INFO)

def ask_ai(prompt):
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
    )
    return chat_completion.choices[0].message.content

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привіт! Я твій AI-дієтолог!\n\nЯк тебе звати?")
    return ASK_NAME

async def ask_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text(f"Скільки ти важиш? (кг)")
    return ASK_WEIGHT

async def ask_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['weight'] = update.message.text
    await update.message.reply_text("Який у тебе зріст? (см)")
    return ASK_HEIGHT

async def ask_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['height'] = update.message.text
    await update.message.reply_text("Скільки тобі років?")
    return ASK_AGE

async def ask_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['age'] = update.message.text
    kb = ReplyKeyboardMarkup([["🔥 Схуднути", "💪 Набрати масу"], ["⚖️ Підтримати вагу"]], resize_keyboard=True)
    await update.message.reply_text("Яка твоя ціль?", reply_markup=kb)
    return ASK_GOAL

async def ask_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['goal'] = update.message.text
    await update.message.reply_text("Натисни /skip для розрахунку.")
    return ASK_PHOTO

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    w = context.user_data.get('weight')
    h = context.user_data.get('height')
    a = context.user_data.get('age')
    g = context.user_data.get('goal')
    
    res = ask_ai(f"Людина: {w}кг, {h}см, {a} років, ціль: {g}. Порахуй калорії українською коротко.")
    
    kb = ReplyKeyboardMarkup([["🍽️ Що приготувати?", "📊 Моя норма"]], resize_keyboard=True)
    await update.message.reply_text(f"✅ Готово!\n\n📊 {res}", reply_markup=kb)
    return MAIN_MENU

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_weight)],
            ASK_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_height)],
            ASK_HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_age)],
            ASK_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_goal)],
            ASK_GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_photo)],
            ASK_PHOTO: [MessageHandler(filters.ALL, show_main_menu), CommandHandler("skip", show_main_menu)],
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: MAIN_MENU)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    app.add_handler(conv)
    app.run_polling()

if __name__ == "__main__":
    main()
