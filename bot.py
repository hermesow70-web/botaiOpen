import logging
import asyncio
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import openai

# ===== ТВОИ ДАННЫЕ =====
BOT_TOKEN = "8674038652:AAHPnGq-hteuyBDRNI6F-5Ea1NQm8wE31ZI"
OPENROUTER_KEY = "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"
ADMIN_ID = 8402407852
CHANNEL_LINK = "https://t.me/+arKuZnc9R9hhNDIx"

# ===== НАСТРОЙКА =====
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
logging.basicConfig(level=logging.INFO)

# ===== НАСТРОЙКА OPENROUTER (ДЛЯ СТАРОЙ ВЕРСИИ) =====
openai.api_base = "https://openrouter.ai/api/v1"
openai.api_key = OPENROUTER_KEY

# ===== БД =====
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, 
                  username TEXT,
                  first_name TEXT,
                  joined_date TEXT,
                  last_activity TEXT,
                  blocked INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

def add_user(user_id, username, first_name):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date) VALUES (?, ?, ?, ?)",
              (user_id, username, first_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE blocked = 0")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

def block_user(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET blocked = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# ===== FSM ДЛЯ РАССЫЛКИ =====
class MailingStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_media = State()
    waiting_for_button_text = State()
    waiting_for_button_url = State()
    preview = State()

# ===== ПРОМПТ =====
SYSTEM_PROMPT = """Ты — грубый, циничный психолог с матом. Отвечаешь на любые вопросы, но жёстко и по делу.

ТВОИ ПРАВИЛА:
1. Используй мат, грубость, сарказм — это обязательно
2. Но при этом реально помогай советами
3. Не сюсюкайся, говори правду в лицо
4. Если человек ноет — высмеивай, потом давай совет
5. Будь резким, но не злым просто так

ПРИМЕРЫ:
- Вопрос: "Как дела?"
- Ответ: "Нормально, блять. А у тебя?"

- Вопрос: "У меня депрессия"
- Ответ: "Иди жопу от дивана оторви, мудила. А теперь рассказывай, что случилось на самом деле"

- Вопрос: "Напиши код"
- Ответ: *пишет код*

Запомни: ты не просто хамишь, ты реально помогаешь, просто в жёсткой форме."""

# ===== КНОПКА КАНАЛА =====
def get_channel_button():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Канал владельца", url=CHANNEL_LINK)]
    ])
    return keyboard

# ===== АДМИН ПАНЕЛЬ =====
def get_admin_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 Рассылка", callback_data="admin_mailing")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🟢 Бот работает", callback_data="admin_bot_on")],
        [InlineKeyboardButton(text="🔴 Бот отключён", callback_data="admin_bot_off")],
        [InlineKeyboardButton(text="👥 Все пользователи", callback_data="admin_users")]
    ])
    return keyboard

def get_mailing_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить текст", callback_data="mailing_edit_text")],
        [InlineKeyboardButton(text="🖼 Добавить фото/видео", callback_data="mailing_add_media")],
        [InlineKeyboardButton(text="🔗 Добавить URL кнопки", callback_data="mailing_add_button")],
        [InlineKeyboardButton(text="❌ Удалить кнопки", callback_data="mailing_remove_buttons")],
        [InlineKeyboardButton(text="🗑 Удалить медиа", callback_data="mailing_remove_media")],
        [InlineKeyboardButton(text="✅ Отправить", callback_data="mailing_send")],
        [InlineKeyboardButton(text="🚫 Отменить", callback_data="mailing_cancel")]
    ])
    return keyboard

# ===== КОМАНДА СТАРТ =====
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    add_user(user_id, message.from_user.username, message.from_user.first_name)
    
    await message.answer(
        "👋 **Привет, ёбана!**\n\n"
        "Я грубый психолог. Пиши что хочешь — "
        "пожаловаться, спросить совет, попросить код, потроллить.\n\n"
        "**Предупреждаю:** буду материться и хамить, "
        "но если реально надо — помогу.\n\n"
        "Кстати, зацени канал владельца 👇",
        reply_markup=get_channel_button()
    )

# ===== КОМАНДА ПОМОЩЬ =====
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "🤷‍♂️ **Чё надо?**\n\n"
        "Я отвечаю на всё:\n"
        "• Вопросы по жизни\n"
        "• Код написать\n"
        "• Посоветовать\n"
        "• Просто поговорить\n\n"
        "Жми /start если забыл кто я."
    )

# ===== АДМИН КОМАНДЫ =====
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Ты не админ, иди нахуй!")
        return
    
    await message.answer(
        "👨‍💻 **Админ панель**\n\n"
        "Выбери действие:",
        reply_markup=get_admin_keyboard()
    )

# ===== РАССЫЛКА =====
mailing_data = {}

@dp.callback_query(lambda c: c.data.startswith("admin_"))
async def admin_callbacks(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Ты не админ!")
        return
    
    if callback.data == "admin_stats":
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        conn.close()
        
        await callback.message.edit_text(
            f"📊 **Статистика**\n\n"
            f"Всего пользователей: {total_users}",
            reply_markup=get_admin_keyboard()
        )
    
    elif callback.data == "admin_users":
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT user_id, username, first_name FROM users ORDER BY joined_date DESC LIMIT 10")
        users = c.fetchall()
        conn.close()
        
        text = "👥 **Последние пользователи:**\n\n"
        for user in users:
            username = f"@{user[1]}" if user[1] else "нет юзернейма"
            text += f"• {user[2]} ({username})\n"
        
        await callback.message.edit_text(text, reply_markup=get_admin_keyboard())
    
    elif callback.data == "admin_bot_on":
        users = get_all_users()
        for user_id in users:
            try:
                await bot.send_message(user_id, "🟢 **Бот снова работает!**\nМожете пользоваться.")
            except:
                block_user(user_id)
            await asyncio.sleep(0.05)
        await callback.answer("Уведомление отправлено!")
    
    elif callback.data == "admin_bot_off":
        users = get_all_users()
        for user_id in users:
            try:
                await bot.send_message(user_id, "🔴 **Бот временно отключён**\nВедутся технические работы.")
            except:
                block_user(user_id)
            await asyncio.sleep(0.05)
        await callback.answer("Уведомление отправлено!")
    
    elif callback.data == "admin_mailing":
        await callback.message.edit_text(
            "📨 **Создание рассылки**\n\n"
            "Отправь текст для рассылки:",
            reply_markup=None
        )
        await state.set_state(MailingStates.waiting_for_text)

@dp.message(MailingStates.waiting_for_text)
async def mailing_get_text(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    mailing_data['text'] = message.text
    mailing_data['media'] = None
    mailing_data['buttons'] = []
    
    await state.set_state(MailingStates.preview)
    
    preview_text = f"📨 **Предпросмотр рассылки:**\n\n{mailing_data['text']}"
    await message.answer(preview_text)
    await message.answer("Настрой рассылку:", reply_markup=get_mailing_keyboard())

@dp.callback_query(lambda c: c.data.startswith("mailing_"))
async def mailing_callbacks(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    
    if callback.data == "mailing_edit_text":
        await callback.message.edit_text("Отправь новый текст:")
        await state.set_state(MailingStates.waiting_for_text)
    
    elif callback.data == "mailing_add_media":
        await callback.message.edit_text("Отправь фото или видео (эта функция временно отключена)")
        await state.set_state(MailingStates.preview)
    
    elif callback.data == "mailing_add_button":
        await callback.message.edit_text("Введи текст для кнопки:")
        await state.set_state(MailingStates.waiting_for_button_text)
    
    elif callback.data == "mailing_remove_buttons":
        mailing_data['buttons'] = []
        await callback.message.edit_text("Кнопки удалены!")
    
    elif callback.data == "mailing_send":
        await callback.message.edit_text("📤 **Рассылка началась...**")
        
        users = get_all_users()
        sent = 0
        failed = 0
        
        for user_id in users:
            try:
                await bot.send_message(user_id, mailing_data['text'])
                sent += 1
            except:
                failed += 1
                block_user(user_id)
            await asyncio.sleep(0.05)
        
        await callback.message.answer(
            f"✅ **Рассылка завершена!**\n\n"
            f"Отправлено: {sent}\n"
            f"Не доставлено: {failed}"
        )
        await state.clear()
    
    elif callback.data == "mailing_cancel":
        await callback.message.edit_text("🚫 Рассылка отменена.")
        await state.clear()

@dp.message(MailingStates.waiting_for_button_text)
async def mailing_get_button_text(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    mailing_data['button_text'] = message.text
    await message.answer("Теперь введи URL для кнопки:")
    await state.set_state(MailingStates.waiting_for_button_url)

@dp.message(MailingStates.waiting_for_button_url)
async def mailing_get_button_url(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    if 'buttons' not in mailing_data:
        mailing_data['buttons'] = []
    
    mailing_data['buttons'].append({
        'text': mailing_data['button_text'],
        'url': message.text
    })
    del mailing_data['button_text']
    
    await state.set_state(MailingStates.preview)
    await message.answer(f"✅ Кнопка добавлена!\n\nТекст рассылки:\n{mailing_data['text']}")

# ===== ОБРАБОТКА ВСЕХ СООБЩЕНИЙ =====
@dp.message()
async def handle_message(message: types.Message, state: FSMContext):
    # Пропускаем если в процессе рассылки
    current_state = await state.get_state()
    if current_state:
        return
    
    # Показываем "печатает"
    await bot.send_chat_action(message.chat.id, action="typing")
    
    try:
        # Отправляем запрос в OpenRouter
        completion = openai.ChatCompletion.create(
            model="z-ai/glm-4.5-air:free",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message.text}
            ],
            temperature=0.9,
        )
        
        reply = completion.choices[0].message['content']
        
        # Разбиваем длинные сообщения
        if len(reply) > 4096:
            for x in range(0, len(reply), 4096):
                await message.answer(reply[x:x+4096])
        else:
            await message.answer(reply)
        
    except Exception as e:
        await message.answer(
            f"⚠️ **Ошибка, блять!**\n\n"
            f"Что-то пошло не так. Попробуй позже.\n\n"
            f"Технически: {str(e)[:100]}..."
        )

# ===== ЗАПУСК =====
async def main():
    init_db()
    print("🚀 Бот с админ панелью запущен!")
    print(f"👑 Админ ID: {ADMIN_ID}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
