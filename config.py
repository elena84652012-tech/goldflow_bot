"""
GoldFlow — конфигурация.
Токен бота берётся из переменной окружения BOT_TOKEN (файл .env),
а не хранится в коде — это важно для безопасности при публикации на GitHub.
"""

import os
from dotenv import load_dotenv

load_dotenv()  # подхватывает переменные из файла .env

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if not BOT_TOKEN:
    raise ValueError(
        "BOT_TOKEN не найден! Создай файл .env в корне проекта и добавь строку:\n"
        "BOT_TOKEN=твой_токен_от_BotFather"
    )

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL не найден! Добавь в файл .env строку с адресом базы данных Neon:\n"
        "DATABASE_URL=postgresql://..."
    )
