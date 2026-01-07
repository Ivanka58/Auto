import os
import telebot
from telebot import types
from flask import Flask
import threading
from dotenv import load_dotenv
from vk_worker import send_to_vk_groups

load_dotenv()

# Настройки из ENV
TOKEN = os.getenv("TG_TOKEN")
VK_TOKEN = os.getenv("VK_TOKEN")
GROUPS_RAW = os.getenv("GROUP_IDS", "")
GROUP_IDS = [int(i.strip()) for i in GROUPS_RAW.split(",") if i.strip()]

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Словарь для хранения данных пользователя (вместо FSM)
user_data = {}

# --- СЕРВЕР ДЛЯ ПОРТА ---
@app.route('/')
def health():
    return "Bot is alive", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- КЛАВИАТУРЫ ---
def get_start_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("Отправить объявление"))
    return kb

def get_confirm_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("Готово ☑️"), types.KeyboardButton("Изменить"))
    return kb

# --- КОМАНДЫ ---
@bot.message_handler(commands=['start', 'avto'])
def send_welcome(message):
    user_data[message.chat.id] = {} # Сброс данных
    bot.send_message(
        message.chat.id, 
        "Привет Захар, чтобы отправить объявление нажми ниже 👇", 
        reply_markup=get_start_kb()
    )

@bot.message_handler(func=lambda m: m.text == "Отправить объявление")
def ask_photo(message):
    bot.send_message(message.chat.id, "Отправь фото твоего объявления", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, get_photo)

def get_photo(message):
    if not message.photo:
        bot.send_message(message.chat.id, "Это не фото! Нажми /start и попробуй снова.")
        return
    
    # Сохраняем самое лучшее качество фото
    file_id = message.photo[-1].file_id
    user_data[message.chat.id]['photo_id'] = file_id
    
    bot.send_message(message.chat.id, "Теперь отправь текст к фото")
    bot.register_next_step_handler(message, get_text)

def get_text(message):
    if not message.text:
        bot.send_message(message.chat.id, "Нужен текст! Нажми /start и попробуй снова.")
        return
    
    user_data[message.chat.id]['text'] = message.text
    bot.send_message(
        message.chat.id, 
        "Точно уверен? В тексте все четко? Ничего изменить не хочешь?", 
        reply_markup=get_confirm_kb()
    )

@bot.message_handler(func=lambda m: m.text in ["Готово ☑️", "Изменить"])
def confirm_step(message):
    if message.text == "Изменить":
        ask_photo(message)
        return

    # Если Готово
    chat_id = message.chat.id
    if not VK_TOKEN:
        bot.send_message(chat_id, "Ключ вк не подключен!! Обратись к администратору @Ivanka58", reply_markup=get_start_kb())
        return

    bot.send_message(chat_id, "Начинаю процесс отправки... подожди.")

    try:
        data = user_data.get(chat_id, {})
        # Скачивание
        file_info = bot.get_file(data['photo_id'])
        downloaded_file = bot.download_file(file_info.file_path)
        
        photo_path = f"img_{chat_id}.jpg"
        with open(photo_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        # Отправка в ВК
        report = send_to_vk_groups(VK_TOKEN, GROUP_IDS, data['text'], photo_path)

        # Удаление мусора
        if os.path.exists(photo_path):
            os.remove(photo_path)

        bot.send_message(chat_id, report, reply_markup=get_start_kb())
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка: {e}\nОбратись к администратору @Ivanka58", reply_markup=get_start_kb())

# --- ЗАПУСК ---
if __name__ == '__main__':
    # Flask в потоке для Render
    threading.Thread(target=run_flask).start()
    # Бот
    print("Бот запущен...")
    bot.infinity_polling()
