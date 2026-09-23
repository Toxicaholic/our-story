import os
import time
import base64
import asyncio
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message

# Настройки из переменных окружения Render
BOT_TOKEN = os.getenv("BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")

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
        "message": f"Add photo {file_name} via Telegram Bot ❤️",
        "content": encoded_content
    }

    async with aiohttp.ClientSession() as session:
        async with session.put(url, headers=headers, json=data) as resp:
            return resp.status in (200, 201)

@dp.message(CommandStart())
async def handle_start(message: Message):
    if ALLOWED_USERS and str(message.from_user.id) not in ALLOWED_USERS:
        await message.reply("Ой, доступ закрыт 💔")
        return
    await message.reply("Привет, любимые! 💕\nОтправьте мне фоточку, и я с любовью добавлю её в наш слайдер воспоминаний! 📸✨")

@dp.message(F.photo)
async def handle_photo(message: Message):
    if ALLOWED_USERS and str(message.from_user.id) not in ALLOWED_USERS:
        await message.reply("Ой, доступ закрыт 💔")
        return

    msg = await message.reply("Бережно сохраняю наше воспоминание... ⏳💖")
    
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    
    stream = await bot.download_file(file.file_path)
    image_bytes = stream.read()

    filename = f"img_{int(time.time())}.jpg"

    success = await upload_to_github(image_bytes, filename)
    if success:
        await msg.edit_text("Ура! Фоточка успешно добавлена в наш альбомчик! 💞🥰")
    else:
        await msg.edit_text("Ой, что-то пошло не так при отправке на GitHub... 🥺💔 Попробуй ещё разок!")

@dp.message()
async def fallback(message: Message):
    if ALLOWED_USERS and str(message.from_user.id) not in ALLOWED_USERS:
        await message.reply("Ой, доступ закрыт 💔")
        return
    await message.reply("Жду от тебя красивую фотографию! 💌 Отправь мне фоточку, и она появится на нашем сайте 💕")

# Вспомогательный веб-сервер для Render Web Service
async def handle_ping(request):
    return web.Response(text="Bot is in love! ❤️")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/healthz", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web server started on port {port}")

async def main():
    print("Бот с сердечками запущен... ❤️")
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
