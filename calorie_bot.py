import os
import logging
import base64
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
import anthropic
 
# ============================
# НАЛАШТУВАННЯ — ЗАМІНИ ЦЕ!
# ============================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
# ============================
# Стани розмови
# ============================
ASK_NAME, ASK_WEIGHT, ASK_HEIGHT, ASK_AGE, ASK_GOAL, ASK_PHOTO, MAIN_MENU, ASK_PRODUCTS, SHOW_RECIPES = range(9)
 
logging.basicConfig(level=logging.INFO)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
 
# ============================
# СТАРТ
# ============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "👋 Привіт! Я твій особистий AI-помічник по харчуванню!\n\n"
        "Я допоможу тобі:\n"
        "🔥 Рахувати калорії\n"
        "🍽️ Підбирати рецепти з того що є\n"
        "📊 Досягати твоєї цілі (схуднення або набір маси)\n\n"
        "Як тебе звати?"
    )
    return ASK_NAME
 
async def ask_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text(f"Приємно познайомитись, {update.message.text}! 💪\n\nСкільки ти важиш? (наприклад: 70)")
    return ASK_WEIGHT
 
async def ask_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['weight'] = update.message.text
    await update.message.reply_text("Який у тебе зріст в см? (наприклад: 175)")
    return ASK_HEIGHT
 
async def ask_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['height'] = update.message.text
    await update.message.reply_text("Скільки тобі років?")
    return ASK_AGE
 
async def ask_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['age'] = update.message.text
    keyboard = ReplyKeyboardMarkup(
        [["🔥 Схуднути", "💪 Набрати масу"], ["⚖️ Підтримати вагу"]],
        resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text("Яка твоя ціль?", reply_markup=keyboard)
    return ASK_GOAL
 
async def ask_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['goal'] = update.message.text
    await update.message.reply_text(
        "Чудово! 📸 Тепер надішли фото свого тіла (необов'язково) — "
        "або натисни /skip щоб пропустити.\n\n"
        "Це допоможе мені краще оцінити твій прогрес."
    )
    return ASK_PHOTO
 
async def skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await show_main_menu(update, context)
 
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()
    photo_bytes = await file.download_as_bytearray()
    context.user_data['photo'] = base64.b64encode(photo_bytes).decode()
    await update.message.reply_text("✅ Фото збережено!")
    return await show_main_menu(update, context)
 
# ============================
# ГОЛОВНЕ МЕНЮ
# ============================
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Рахуємо калорії через Claude
    weight = context.user_data.get('weight', '70')
    height = context.user_data.get('height', '170')
    age = context.user_data.get('age', '20')
    goal = context.user_data.get('goal', 'підтримати вагу')
    name = context.user_data.get('name', 'друже')
 
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"Людина: вага {weight}кг, зріст {height}см, вік {age} років, ціль: {goal}. "
                      f"Порахуй добову норму калорій (формула Міффліна-Сан Жеора, стать чоловік). "
                      f"Дай коротку відповідь: тільки калорії та 2-3 речення пояснення. Відповідай українською."
        }]
    )
    
    calories_info = response.content[0].text
    context.user_data['calories_info'] = calories_info
 
    keyboard = ReplyKeyboardMarkup([
        ["🍽️ Що приготувати?", "📊 Моя норма калорій"],
        ["⚡ Швидкий рецепт (15 хв)", "💡 Порада дня"]
    ], resize_keyboard=True)
 
    await update.message.reply_text(
        f"✅ {name}, твій профіль готовий!\n\n"
        f"📊 {calories_info}\n\n"
        f"Обери що хочеш зробити:",
        reply_markup=keyboard
    )
    return MAIN_MENU
 
# ============================
# ОБРОБКА МЕНЮ
# ============================
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
 
    if "Що приготувати" in text:
        await update.message.reply_text(
            "🛒 Напиши продукти які є у тебе вдома через кому.\n\n"
            "Наприклад: яйця, гречка, молоко, хліб, помідори"
        )
        return ASK_PRODUCTS
 
    elif "норма калорій" in text:
        calories_info = context.user_data.get('calories_info', 'Дані не знайдено')
        await update.message.reply_text(f"📊 Твоя норма:\n\n{calories_info}")
        return MAIN_MENU
 
    elif "Швидкий рецепт" in text:
        await update.message.reply_text(
            "⚡ Напиши продукти які є — знайду рецепт на 15 хвилин!\n\n"
            "Наприклад: яйця, сир, хліб"
        )
        context.user_data['quick_mode'] = True
        return ASK_PRODUCTS
 
    elif "Порада дня" in text:
        goal = context.user_data.get('goal', 'підтримати вагу')
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": f"Дай одну коротку практичну пораду по харчуванню для людини з ціллю: {goal}. Максимум 3 речення. Українською."
            }]
        )
        tip = response.content[0].text
        await update.message.reply_text(f"💡 Порада дня:\n\n{tip}")
        return MAIN_MENU
 
    return MAIN_MENU
 
# ============================
# РЕЦЕПТИ З ПРОДУКТІВ
# ============================
async def handle_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = update.message.text
    goal = context.user_data.get('goal', 'підтримати вагу')
    quick_mode = context.user_data.get('quick_mode', False)
    calories_target = context.user_data.get('calories_info', '')
 
    await update.message.reply_text("🤔 Думаю що можна приготувати...")
 
    time_limit = "до 15 хвилин" if quick_mode else "різний час приготування"
 
    response = client.messages.create(
       model="claude-3-5-sonnet-20241022",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": f"У людини є продукти: {products}. Ціль: {goal}. Час: {time_limit}.\n"
                      f"Запропонуй 3 страви які можна приготувати. Для кожної:\n"
                      f"- Назва страви\n"
                      f"- Калорії (приблизно)\n"
                      f"- Час приготування\n"
                      f"- Коротко чому підходить для цілі\n\n"
                      f"Відповідай українською, коротко і чітко."
        }]
    )
 
    recipes_text = response.content[0].text
    context.user_data['last_recipes'] = recipes_text
    context.user_data['last_products'] = products
    context.user_data['quick_mode'] = False
 
    # Кнопки для вибору рецепту
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍳 Рецепт страви 1", callback_data="recipe_1")],
        [InlineKeyboardButton("🥗 Рецепт страви 2", callback_data="recipe_2")],
        [InlineKeyboardButton("🍲 Рецепт страви 3", callback_data="recipe_3")],
    ])
 
    await update.message.reply_text(
        f"✅ Ось що можна приготувати:\n\n{recipes_text}\n\n"
        f"Натисни на страву — отримаєш покроковий рецепт!",
        reply_markup=keyboard
    )
    return MAIN_MENU
 
# ============================
# ПОКРОКОВИЙ РЕЦЕПТ
# ============================
async def handle_recipe_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
 
    recipe_num = query.data.split("_")[1]
    products = context.user_data.get('last_products', '')
    recipes = context.user_data.get('last_recipes', '')
 
    await query.message.reply_text("📝 Готую покроковий рецепт...")
 
    response = client.messages.create(
      model="claude-3-5-sonnet-20241022",
        max_tokens=800,
        messages=[{
            "role": "user",
            "content": f"З цих страв: {recipes}\n\nДай детальний покроковий рецепт для страви номер {recipe_num}.\n"
                      f"Продукти які є: {products}\n"
                      f"Формат:\n"
                      f"🍽️ НАЗВА СТРАВИ\n"
                      f"⏱️ Час: X хвилин\n"
                      f"🔥 Калорії: X ккал\n\n"
                      f"ІНГРЕДІЄНТИ:\n- ...\n\n"
                      f"КРОКИ:\n1. ...\n2. ...\n\n"
                      f"Відповідай українською."
        }]
    )
 
    recipe_detail = response.content[0].text
 
    keyboard = ReplyKeyboardMarkup([
        ["🍽️ Що приготувати?", "📊 Моя норма калорій"],
        ["⚡ Швидкий рецепт (15 хв)", "💡 Порада дня"]
    ], resize_keyboard=True)
 
    await query.message.reply_text(
        f"{recipe_detail}\n\n✅ Смачного! 🎉",
        reply_markup=keyboard
    )
 
# ============================
# ЗАПУСК БОТА
# ============================
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
 
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_weight)],
            ASK_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_height)],
            ASK_HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_age)],
            ASK_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_goal)],
            ASK_GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_photo)],
            ASK_PHOTO: [
                MessageHandler(filters.PHOTO, handle_photo),
                CommandHandler("skip", skip_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, skip_photo),
            ],
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu)],
            ASK_PRODUCTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_products)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
 
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(handle_recipe_button, pattern="^recipe_"))
 
    print("🤖 Бот запущено!")
    app.run_polling()
 
if __name__ == "__main__":
    main()
