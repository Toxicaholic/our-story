import os
import time
import base64
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message

# Получаем настройки из скрытых переменных Render
BOT_TOKEN = os.getenv("BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")

# Считываем список разрешенных ID (через запятую)
raw_users = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS = [x.strip() for x in raw_users.split(",") if x.strip()]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def upload_to_github(image_bytes: bytes, file_name: str) -> bool:
    """Загрузка изображения напрямую в репозиторий через GitHub REST API"""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/photos/{file_name}"
    encoded_content = base64.b64encode(image_bytes).decode("utf-8")
    
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    data = {
        "message": f"Add photo {file_name} via Telegram Bot",
        "content": encoded_content
    }

    async with aiohttp.ClientSession() as session:
        async with session.put(url, headers=headers, json=data) as resp:
            return resp.status in (200, 201)

@dp.message(F.photo)
async def handle_photo(message: Message):
    # Проверяем отправителя (ваш ID или ID девушки)
    if ALLOWED_USERS and str(message.from_user.id) not in ALLOWED_USERS:
        await message.reply("Доступ закрыт ⛔")
        return

    msg = await message.reply("⏳ Загружаю фото на сайт...")
    
    # Берем самое качественное фото
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    
    stream = await bot.download_file(file.file_path)
    image_bytes = stream.read()

    filename = f"img_{int(time.time())}.jpg"

    success = await upload_to_github(image_bytes, filename)
    if success:
        await msg.edit_text("✅ Фото успешно добавлено в слайдер!")
    else:
        await msg.edit_text("❌ Ошибка отправки на GitHub. Проверьте права токена.")

@dp.message()
async def fallback(message: Message):
    await message.reply("Отправь мне фотографию, и я загружу её на сайт.")

async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
