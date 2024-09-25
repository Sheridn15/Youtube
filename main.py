import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage

API_TOKEN = '6109912254:AAFYDa47LGwNP48cwMnzItuVJiTxUSOtKsc'

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
dp.middleware.setup(LoggingMiddleware())

conn = sqlite3.connect('polls.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS polls (
        poll_id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT,
        options TEXT,
        correct_option_id INTEGER,
        creator_id INTEGER,
        FOREIGN KEY (creator_id) REFERENCES users(user_id)
    )
''')
conn.commit()


class PollStates(StatesGroup):
    waiting_for_poll_question = State()
    waiting_for_poll_options = State()
    waiting_for_correct_option = State()

keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
create_poll_button = KeyboardButton("Создать опрос")
view_polls_button = KeyboardButton("Пройти опрос")
cancel_button = KeyboardButton("Отмена")
keyboard.add(create_poll_button, view_polls_button, cancel_button)


@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)',
                   (message.from_user.id, message.from_user.username))
    conn.commit()
    await message.reply("ну чо негр чо хочешь", reply_markup=keyboard)


@dp.message_handler(lambda message: message.text == "Создать опрос")
async def create_poll(message: types.Message):
    await PollStates.waiting_for_poll_question.set()
    await message.reply("как назвать:")


@dp.message_handler(lambda message: message.text == "Отмена", state="*")
async def cancel_poll_creation(message: types.Message, state: FSMContext):
    await state.finish()
    await message.reply("и чо ты делать будешь он больше нечего не умеет", reply_markup=keyboard)


@dp.message_handler(state=PollStates.waiting_for_poll_question)
async def get_poll_question(message: types.Message, state: FSMContext):
    await state.update_data(poll_question=message.text)
    await PollStates.waiting_for_poll_options.set()
    await message.reply("Вариант ответа через запятую:")


@dp.message_handler(state=PollStates.waiting_for_poll_options)
async def get_poll_options(message: types.Message, state: FSMContext):
    options = [option.strip() for option in message.text.split(',')]
    if len(options) < 2:
        await message.reply("ты чо лысый как я тебе опрос 1 вариантом зделаю.")
        return

    await state.update_data(poll_options=options)
    await PollStates.waiting_for_correct_option.set()
    await message.reply(f"а чо из них правильное (1-{len(options)}):")


@dp.message_handler(state=PollStates.waiting_for_correct_option)
async def get_correct_option(message: types.Message, state: FSMContext):
    data = await state.get_data()
    options = data['poll_options']
    
    try:
        correct_option = int(message.text) - 1
        if correct_option < 0 or correct_option >= len(options):
            raise ValueError
    except ValueError:
        await message.reply(f"ты не путай вот из них выбирай (1-{len(options)}). довай по новой:")
        return

    poll_question = data['poll_question']
    creator_id = message.from_user.id

    
    cursor.execute('''
        INSERT INTO polls (question, options, correct_option_id, creator_id)
        VALUES (?, ?, ?, ?)
    ''', (poll_question, ','.join(options), correct_option, creator_id))
    conn.commit()

    await state.finish()

    await message.reply(f"Опрос негра создан:\n\nВопрос: {poll_question}\nВарианты ответов: {', '.join(options)}\nПравильный ответ: {options[correct_option]}", reply_markup=keyboard)


@dp.message_handler(lambda message: message.text == "Пройти опрос")
async def list_polls(message: types.Message):
    cursor.execute('SELECT poll_id, question FROM polls')
    polls = cursor.fetchall()

    if not polls:
        await message.reply("в душе не чаю чо ты там бозаришь.")
        return

    
    markup = InlineKeyboardMarkup()
    for poll_id, question in polls:
        markup.add(InlineKeyboardButton(text=question, callback_data=f"take_poll_{poll_id}"))
    
    await message.reply("выбери опрос, который хотишь пройти:", reply_markup=markup)


@dp.callback_query_handler(lambda c: c.data.startswith('take_poll_'))
async def take_poll(callback_query: types.CallbackQuery):
    poll_id = int(callback_query.data.split('_')[2])

    cursor.execute('SELECT question, options, correct_option_id FROM polls WHERE poll_id = ?', (poll_id,))
    poll = cursor.fetchone()

    if not poll:
        await bot.answer_callback_query(callback_query.id, text="Опрос не найден.")
        return

    question, options, correct_option_id = poll
    options = options.split(',')

    await bot.send_poll(
        chat_id=callback_query.message.chat.id,
        question=question,
        options=options,
        correct_option_id=correct_option_id,
        type="quiz",
        is_anonymous=False
    )

    await bot.answer_callback_query(callback_query.id)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)