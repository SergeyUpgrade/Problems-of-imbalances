import uvicorn
from fastapi import FastAPI
from app.database import init_database, load_data_to_clickhouse
from app.config import settings
from app.api.router import router as api_router
import os
from pathlib import Path

# Инициализация FastAPI
app = FastAPI()


def initialize_app():
    """Инициализация приложения"""
    print("🔄 Инициализация приложения...")

    # Инициализация базы данных
    try:
        client = init_database()
        if settings.DATA_FILE.exists():
            print(f"📂 Загрузка данных из {settings.DATA_FILE}")
            load_data_to_clickhouse(client, settings.DATA_FILE)
        else:
            print(f"⚠️ Файл данных не найден: {settings.DATA_FILE}")
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        raise


# Подключение роутеров
app.include_router(api_router)


@app.on_event("startup")
async def startup_event():
    """Действия при запуске приложения"""
    initialize_app()
    print("✅ Приложение готово к работе")


if __name__ == "__main__":
    # Определяем корневую директорию проекта
    BASE_DIR = Path(__file__).resolve().parent.parent
    os.chdir(BASE_DIR)

    # Конфигурация Uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
