import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import sqlite3
from datetime import datetime

# Логи
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Категории и упражнения
EXERCISES = {
    "Грудь": [
        "Жим в кроссовере горизонтально",
        "Жим в тренажере от груди вверх",
        "Жим гантелей на скамье",
        "Жим штанги лежа",
        "Разведение гантелей на скамье",
        "Сведение рук бабочка",
    ],
    "Руки": [
        "Сгибание рук с гантелями",
        "Сгибание рук с гантелями сидя",
        "Сгибание одной руки от колена",
        "Сгибание рук в блоке",
        "Сгибание рук в блоке обратным хватом",
        "Сгибание рук в блоке с веревкой",
        "Сгибание рук с разворотом",
        "Сгибание рук со штангой",
        "Разгибание рук в блоке",
        "Разгибание рук в блоке обратным хватом",
        "Разгибание рук из-за головы с гантелью",
        "Разгибание рук из-за головы с гантелью сидя",
    ],
    "Спина": [
        "Вертикальная тяга блока за голову",
        "Вертикальная тяга к груди",
        "Горизонтальная тяга блока сидя",
        "Пуловер в блоке с прямой ручкой стоя",
        "Тяга в наклоне в тренажере Смита прямым хватом",
        "Тяга в наклоне в тренажере Смита обратным хватом",
        "Тяга гантелей к поясу в наклоне",
        "Тяга штанги в наклоне прямым хватом",
        "Тяга штанги в наклоне обратным хватом",
    ],
    "Ноги": [
        "Выпады",
        "Приседания",
        "Жим ногами",
        "Приседания в тренажере смита",
        "Бег",
        "Разгибание ног сидя",
        "Сгибание ног сидя",
    ]
}

NO_WEIGHT = ["Выпады", "Приседания", "Бег"]

# Создание ID для кнопок
CATEGORY_IDS = {f"cat{i}": cat for i, cat in enumerate(EXERCISES)}
CATEGORY_NAMES = {v: k for k, v in CATEGORY_IDS.items()}

EXERCISE_IDS = {}
EXERCISE_LOOKUP = {}

counter = 0
for cat, ex_list in EXERCISES.items():
    for ex in ex_list:
        ex_id = f"ex{counter}"
        EXERCISE_IDS[ex_id] = {"category": cat, "exercise": ex}
        EXERCISE_LOOKUP[(cat, ex)] = ex_id
        counter += 1


# Инициализация БД
def init_db():
    conn = sqlite3.connect('workouts.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS workouts
                 (user_id integer, date text, category text, exercise text, 
                  weight text, reps text, sets text, time text)''')
    conn.commit()
    conn.close()


# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("НОВАЯ ТРЕНИРОВКА", callback_data="new")],
        [InlineKeyboardButton("СТАТИСТИКА", callback_data="stats")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)


# Выбор категории
async def new_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    buttons = [
        [InlineKeyboardButton(cat, callback_data=cat_id)]
        for cat_id, cat in CATEGORY_IDS.items()
    ]
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="back")])

    await query.edit_message_text("Выберите категорию:", reply_markup=InlineKeyboardMarkup(buttons))


# Выбор упражнения
async def show_exercises(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    cat_id = query.data
    category = CATEGORY_IDS.get(cat_id)
    if not category:
        await query.edit_message_text("❌ Ошибка! Категория не найдена.")
        return

    context.user_data['category'] = category

    buttons = []
    for ex in EXERCISES[category]:
        ex_id = EXERCISE_LOOKUP[(category, ex)]
        buttons.append([InlineKeyboardButton(ex, callback_data=ex_id)])

    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="new")])
    buttons.append([InlineKeyboardButton("✅ Завершить", callback_data="finish")])

    await query.edit_message_text(f"{category}\nВыберите упражнение:", reply_markup=InlineKeyboardMarkup(buttons))


# Обработка выбранного упражнения
async def handle_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    ex_id = query.data
    entry = EXERCISE_IDS.get(ex_id)
    if not entry:
        await query.edit_message_text("❌ Ошибка! Упражнение не найдено.")
        return

    context.user_data['exercise'] = entry['exercise']
    context.user_data['category'] = entry['category']

    if entry['exercise'] in NO_WEIGHT:
        if entry['exercise'] == "Бег":
            await query.edit_message_text("Введите время в минутах:")
        else:
            await query.edit_message_text("Введите подходы (формат: 10x5):")
    else:
        await query.edit_message_text("Введите данные (формат: вес Х повторения Х подходы):")


# Сохранение данных
async def save_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    category = context.user_data.get('category')
    exercise = context.user_data.get('exercise')

    try:
        if exercise in NO_WEIGHT:
            if exercise == "Бег":
                time = f"{text} мин"
                data = (user_id, datetime.now().strftime('%Y-%m-%d'), category, exercise, '', '', '', time)
            else:
                reps, sets = text.split('x')
                data = (user_id, datetime.now().strftime('%Y-%m-%d'), category, exercise, '', reps, sets, '')
        else:
            weight, reps, sets = text.split('x')
            data = (user_id, datetime.now().strftime('%Y-%m-%d'), category, exercise, weight, reps, sets, '')

        conn = sqlite3.connect('workouts.db')
        c = conn.cursor()
        c.execute("INSERT INTO workouts VALUES (?, ?, ?, ?, ?, ?, ?, ?)", data)
        conn.commit()
        conn.close()

        await update.message.reply_text('✅ Успешно сохранено!')
        await show_exercises_again(update, context)

    except Exception:
        await update.message.reply_text('❌ Ошибка формата! Попробуйте снова.')


# Повторный выбор упражнения
async def show_exercises_again(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category = context.user_data['category']
    buttons = []
    for ex in EXERCISES[category]:
        ex_id = EXERCISE_LOOKUP[(category, ex)]
        buttons.append([InlineKeyboardButton(ex, callback_data=ex_id)])

    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="new")])
    buttons.append([InlineKeyboardButton("✅ Завершить", callback_data="finish")])

    await update.message.reply_text(f"{category}\nВыберите упражнение:", reply_markup=InlineKeyboardMarkup(buttons))


# Завершение тренировки
async def finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🏁 Тренировка завершена!")
    await start(update, context)


# Показ статистики
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    conn = sqlite3.connect('workouts.db')
    c = conn.cursor()
    c.execute("SELECT * FROM workouts WHERE user_id=? ORDER BY date DESC", (user_id,))
    data = c.fetchall()
    conn.close()

    if not data:
        await query.edit_message_text("📊 Статистика пуста")
        return

    stats = {}
    for row in data:
        date = row[1]
        if date not in stats:
            stats[date] = []
        stats[date].append(row)

    message = "📊 Ваша статистика:\n\n"
    for date, workouts in stats.items():
        message += f"📅 {date}:\n"
        for w in workouts:
            if w[7]:
                message += f"  - {w[3]}: {w[7]}\n"
            elif w[4]:
                message += f"  - {w[3]}: {w[4]}кг x{w[5]} x{w[6]}\n"
            else:
                message += f"  - {w[3]}: x{w[5]} x{w[6]}\n"
        message += "\n"

    await query.edit_message_text(message)


# Назад
async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)


# Запуск
def main():
    init_db()
    app = Application.builder().token("8067510613:AAFgWaMdeI0b_gMfHO0lHMurD1MI8YfQnFU").build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(new_workout, pattern='^new$'))
    app.add_handler(CallbackQueryHandler(show_exercises, pattern='^cat\d+$'))
    app.add_handler(CallbackQueryHandler(handle_exercise, pattern='^ex\d+$'))
    app.add_handler(CallbackQueryHandler(show_stats, pattern='^stats$'))
    app.add_handler(CallbackQueryHandler(finish, pattern='^finish$'))
    app.add_handler(CallbackQueryHandler(back, pattern='^back$'))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_data))

    app.run_polling()


if __name__ == '__main__':
    main()
