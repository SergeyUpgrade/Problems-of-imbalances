from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os

from app.database import init_database, load_data_to_clickhouse
from app.config import settings
from app.api.router import router as api_router

app = FastAPI()

# Инициализация базы данных
client = init_database()
if settings.DATA_FILE.exists():
    load_data_to_clickhouse(client, settings.DATA_FILE)

# Подключение API роутеров
app.include_router(api_router)

@app.on_event("startup")
async def startup_event():
    """Действия при запуске приложения"""
    print("Приложение загружается")