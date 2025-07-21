##LTE Coverage Analysis API
##Описание проекта
API для анализа и визуализации данных покрытия LTE сетей. Позволяет получать данные о качестве сигнала, отображать их на картах и анализировать структуру данных.

##Установка

Настройте подключение к ClickHouse в app/config.py

##Запустите сервер:

bash
uvicorn main:app --reload

##Доступные эндпоинты

GET / - Главная страница с картой покрытия

GET /coverage-map - Страница с гексагональной картой покрытия

GET /hexmap - Альтернативная страница с картой покрытия

##Получение данных
POST /coverage - Получение данных покрытия для заданной области

json
{
  "min_lat": float,
  "max_lat": float,
  "min_lon": float,
  "max_lon": float
}
Возвращает изображение карты в base64

GET /coverage-data - Получение агрегированных данных по H3 гексагонам

json
[
  {
    "h3_index": string,
    "lat": float,
    "lng": float,
    "band": string,
    "avg_rsrp": float,
    "avg_rsrq": float,
    "point_count": int
  }
]

##Визуализация
GET /coverage-hexmap - Гексагональная карта покрытия (JSON с base64 изображением)

GET /coverage_map_with_antenns - HTML страница с картой покрытия и антеннами

##Анализ данных
GET /api/table-structure-full - Полная структура таблицы coverage_data

json
{
  "exists": bool,
  "columns": [
    {
      "name": string,
      "type": string,
      "default": string,
      "comment": string
    }
  ]
}
GET /api/check-data - Проверка целостности данных

json
{
  "table_exists": bool,
  "row_count": int,
  "columns": {
    "column_name": {
      "exists_in_table": bool,
      "non_null_count": int,
      "null_percentage": float
    }
  }
}

Примеры использования
Получение данных покрытия
python
import requests

response = requests.post(
    "http://localhost:8000/coverage",
    json={
        "min_lat": 55.0,
        "max_lat": 56.0,
        "min_lon": 37.0,
        "max_lon": 38.0
    }
)
print(response.json())

##Визуализация в браузере
Откройте в браузере:

http://localhost:8000/coverage-map - интерактивная карта

http://localhost:8000/hexmap - альтернативный вариант карты

Технические детали
Использует H3 геопространственную индексацию для агрегации данных

Поддерживает два частотных диапазона: LTE1800 и LTE2100

Визуализация с помощью Matplotlib

Данные хранятся в ClickHouse
