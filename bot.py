import os
import time
import uuid
import base64
import asyncio
from typing import Any, Callable, Dict, Awaitable, Union, List

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.filters import CommandStart
from aiogram.types import Message, TelegramObject

# ==========================================
# Настройки из переменных окружения Render
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")

raw_users = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS = [x.strip() for x in raw_users.split(",") if x.strip()]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ==========================================
# Middleware для склейки альбомов (Media Group)
# ==========================================
class MediaGroupMiddleware(BaseMiddleware):
    def __init__(self, latency: float = 0.8):
        self.latency = latency
        self.media_groups: Dict[str, List[Message]] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not isinstance(event, Message) or not event.media_group_id:
            return await handler(event, data)

        mg_id = event.media_group_id

        if mg_id not in self.media_groups:
            self.media_groups[mg_id] = [event]
            await asyncio.sleep(self.latency)

            messages = self.media_groups.pop(mg_id, [])
            data["album"] = messages
            return await handler(event, data)
        else:
            self.media_groups[mg_id].append(event)
            return


dp.message.middleware(MediaGroupMiddleware())


# ==========================================
# Функция загрузки в GitHub через REST API
# ==========================================
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


# Склонение слова "фото"
def get_photos_word(count: int) -> str:
    if count == 1:
        return "1 фоточку"
    elif 2 <= count % 10 <= 4 and (count % 100 < 10 or count % 100 >= 20):
        return f"{count} фоточки"
    else:
        return f"{count} фоточек"


# ==========================================
# Обработчики команд и сообщений
# ==========================================
@dp.message(CommandStart())
async def handle_start(message: Message):
    if ALLOWED_USERS and str(message.from_user.id) not in ALLOWED_USERS:
        await message.reply("Ой, доступ закрыт")
        return
    await message.reply("Привет, любимые! 💕\nОтправьте мне одно или сразу пачку фото, и я с любовью добавлю их в наш альбом! 📸")


@dp.message(F.photo)
async def handle_photo_or_album(message: Message, album: List[Message] = None):
    if ALLOWED_USERS and str(message.from_user.id) not in ALLOWED_USERS:
        await message.reply("Ой, доступ закрыт ")
        return

    # Если отправлен альбом нескольких фото — берем список, иначе одно текущее сообщение
    messages_to_process = album if album else [message]
    total_count = len(messages_to_process)

    msg = await message.reply(f"Бережно сохраняю {get_photos_word(total_count)}... ⏳")

    successful_uploads = 0

    for m in messages_to_process:
        try:
            photo = m.photo[-1]
            file = await bot.get_file(photo.file_id)
            stream = await bot.download_file(file.file_path)
            image_bytes = stream.read()

            # Уникальное имя с миллисекундами и рандомным суффиксом
            filename = f"img_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}.jpg"

            success = await upload_to_github(image_bytes, filename)
            if success:
                successful_uploads += 1
            # Небольшая задержка, чтобы GitHub API не ругался на конфликты одновременных коммитов
            await asyncio.sleep(0.4)
        except Exception as e:
            print(f"Ошибка при обработке фото: {e}")

    if successful_uploads == total_count:
        if total_count == 1:
            await msg.edit_text("Ура! Фоточка успешно добавлена в наш альбомчик! 💞")
        else:
            await msg.edit_text(f"Ура! Все {successful_uploads} фото успешно добавлены в наш альбомчик! 💞")
    elif successful_uploads > 0:
        await msg.edit_text(f"Загружено {successful_uploads} из {total_count} фоточек! Часть не прошла, попробуй дослать остаток 💕")
    else:
        await msg.edit_text("Ой, не получилось сохранить фото... 💔 Попробуй ещё разок!")


@dp.message()
async def fallback(message: Message):
    if ALLOWED_USERS and str(message.from_user.id) not in ALLOWED_USERS:
        await message.reply("Ой, доступ закрыт 💔")
        return
    await message.reply("Жду от тебя красивые фотографии! 💌 Можно скинуть сразу несколько штук альбомом, и все они появятся на сайте 💕")


# ==========================================
# Вспомогательный веб-сервер для Render Web Service
# ==========================================
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
    print("Бот с поддержкой альбомов запущен... ❤️")
    await start_web_server()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
