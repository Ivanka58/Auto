import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv
import vk_api

# Загрузка переменных из .env (если работаем локально)
load_dotenv()

# Чтение конфигурации
TG_TOKEN = os.getenv("TG_TOKEN")
VK_TOKEN = os.getenv("VK_TOKEN")
# Превращаем строку "-123,-456" в список чисел [-123, -456]
GROUPS_STR = os.getenv("GROUP_IDS", "")
GROUP_IDS = [int(i.strip()) for i in GROUPS_STR.split(",") if i.strip()]

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TG_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Состояния
class AdFlow(StatesGroup):
    waiting_for_photo = State()
    waiting_for_text = State()
    confirm = State()

# Клавиатуры
def get_start_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Отправить объявление"))
    return kb

def get_confirm_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Готово ☑️"), KeyboardButton("Изменить"))
    return kb

# Общая функция приветствия
async def send_welcome(message: types.Message):
    text = "Привет Захар, чтобы отправить объявление нажми ниже 👇"
    await message.answer(text, reply_markup=get_start_kb())

@dp.message_handler(commands=['start', 'avto'])
async def cmd_start(message: types.Message):
    await send_welcome(message)

@dp.message_handler(lambda m: m.text == "Отправить объявление", state="*")
async def start_ad_process(message: types.Message):
    await message.answer("Отправь фото твоего объявления", reply_markup=types.ReplyKeyboardRemove())
    await AdFlow.waiting_for_photo.set()

@dp.message_handler(content_types=['photo'], state=AdFlow.waiting_for_photo)
async def process_photo(message: types.Message, state: FSMContext):
    # Сохраняем ID самого качественного фото
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    await message.answer("Теперь отправь текст к фото")
    await AdFlow.waiting_for_text.set()

@dp.message_handler(state=AdFlow.waiting_for_text)
async def process_text(message: types.Message, state: FSMContext):
    await state.update_data(ad_text=message.text)
    await message.answer(

        "Точно уверен? В тексте все четко? Ничего изменить не хочешь?",
        reply_markup=get_confirm_kb()
    )
    await AdFlow.confirm.set()

@dp.message_handler(lambda m: m.text == "Изменить", state=AdFlow.confirm)
async def restart_flow(message: types.Message):
    await start_ad_process(message)

@dp.message_handler(lambda m: m.text == "Готово ☑️", state=AdFlow.confirm)
async def final_post(message: types.Message, state: FSMContext):
    if not VK_TOKEN:
        await message.answer("Ключ вк не подключен!! Обратись к администратору @Ivanka58", reply_markup=get_start_kb())
        await state.finish()
        return

    data = await state.get_data()
    photo_id = data.get("photo_id")
    ad_text = data.get("ad_text")

    await message.answer("Начинаю процесс отправки... подожди.")

    try:
        # Авторизация в ВК
        vk_session = vk_api.VkApi(token=VK_TOKEN)
        vk = vk_session.get_api()
        upload = vk_api.VkUpload(vk_session)

        # Скачиваем фото из ТГ
        photo_file = await bot.get_file(photo_id)
        photo_name = "temp_car.jpg"
        await bot.download_file(photo_file.file_path, photo_name)

        # Загружаем в ВК
        vk_photo = upload.photo_wall(photo_name)[0]
        attachment = f"photo{vk_photo['owner_id']}_{vk_photo['id']}"
        os.remove(photo_name) # Удаляем временный файл

        results = []
        for g_id in GROUP_IDS:
            try:
                vk.wall.post(owner_id=g_id, message=ad_text, attachments=attachment)
                results.append(f"Группа {g_id}: Отправлено")
            except Exception as e:
                results.append(f"Группа {g_id}: Ошибка, группа закрыта, обратись к администратору @Ivanka58")
            
            await asyncio.sleep(2) # Защита от спам-фильтра ВК

        await message.answer("\n".join(results), reply_markup=get_start_kb())

    except Exception as e:
        await message.answer(f"Произошла критическая ошибка: {e}\nОбратись к администратору @Ivanka58", reply_markup=get_start_kb())

    await state.finish()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
