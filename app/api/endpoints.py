import h3
from typing import List, Dict, Any
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database import get_clickhouse_client
from app.models.schemas import AreaRequest, CoverageResponse
from app.services.coverage_service import get_coverage_data
from app.services.mapping_service import create_coverage_map
import pandas as pd

router = APIRouter()

# Получаем абсолютный путь к директории с шаблонами
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@router.get("/", response_class=HTMLResponse)
async def show_map(request: Request):
    """Главная страница с картой"""
    return templates.TemplateResponse("map.html", {"request": request})


@router.post("/coverage", response_model=CoverageResponse)
async def get_coverage(area: AreaRequest):
    """Получение данных покрытия для заданной области"""
    data = get_coverage_data(
        area.min_lat, area.max_lat,
        area.min_lon, area.max_lon
    )

    df = pd.DataFrame(data, columns=['latitude', 'longitude', 'band'])
    map_img = create_coverage_map(df)

    return {"map_image": map_img}


@router.get("/api/coverage-map", response_class=HTMLResponse)
async def coverage_map(request: Request):
    """Главная страница с гексагональной картой"""
    return templates.TemplateResponse("coverage_map.html", {"request": request})


@router.get("/api/coverage", response_model=List[Dict[str, Any]])
async def get_coverage():
    """
    GET-эндпоинт для получения данных покрытия с группировкой по H3 гексагонам
    Возвращает агрегированные данные по каждому гексагону
    """
    try:
        client = get_clickhouse_client()

        # Запрос данных с группировкой по H3 индексу
        query = """
        SELECT 
            h3_index,
            avg(latitude) as latitude,
            avg(longitude) as longitude,
            band,
            avg(rsrp) as avg_rsrp,
            avg(rsrq) as avg_rsrq,
            count() as point_count
        FROM lte_coverage.coverage_data
        GROUP BY h3_index, band
        LIMIT 10000
        """

        data = client.execute(query)

        # Преобразуем в список словарей
        return [dict(zip([
            'h3_index', 'lat', 'lng',
            'band', 'avg_rsrp', 'avg_rsrq', 'point_count'
        ], row)) for row in data]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при получении данных: {str(e)}"
        )


@router.get("/api/table-structure-full")
async def get_table_structure_full():
    try:
        client = get_clickhouse_client()

        # Получаем полное описание таблицы
        structure = client.execute(f"""
        SELECT 
            name, 
            type,
            default_expression,
            comment
        FROM system.columns
        WHERE database = '{settings.CLICKHOUSE_DB}' 
        AND table = 'coverage_data'
        """)

        # Проверяем существование таблицы
        exists = client.execute(f"""
        SELECT count()
        FROM system.tables
        WHERE database = '{settings.CLICKHOUSE_DB}'
        AND name = 'coverage_data'
        """)[0][0] > 0

        if not exists:
            return {"error": "Table does not exist"}

        return {
            "exists": exists,
            "columns": [dict(zip(['name', 'type', 'default', 'comment'], row)) for row in structure]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/check-data")
async def check_data():
    try:
        client = get_clickhouse_client()

        # 1. Проверяем существование таблицы
        exists = client.execute(f"""
        SELECT count()
        FROM system.tables
        WHERE database = '{settings.CLICKHOUSE_DB}'
        AND name = 'coverage_data'
        """)[0][0] > 0

        if not exists:
            return {"error": "Table does not exist"}

        # 2. Проверяем количество записей
        count = client.execute(f"SELECT count() FROM {settings.CLICKHOUSE_DB}.coverage_data")[0][0]

        # 3. Проверяем наличие данных в каждом столбце
        columns_check = {}
        for col in ['latitude', 'longitude', 'altitude', 'band', 'rsrp', 'rsrq', 'h3_index', 'eventtime']:
            non_null = client.execute(f"""
            SELECT count()
            FROM {settings.CLICKHOUSE_DB}.coverage_data
            WHERE {col} IS NOT NULL
            """)[0][0]
            columns_check[col] = {
                "exists_in_table": True,
                "non_null_count": non_null,
                "null_percentage": round((1 - non_null / count) * 100, 2) if count > 0 else 100
            }

        return {
            "table_exists": exists,
            "row_count": count,
            "columns": columns_check
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))