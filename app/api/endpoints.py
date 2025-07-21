import h3
from typing import List, Dict, Any
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse,Response
from fastapi.templating import Jinja2Templates
from matplotlib import pyplot as plt
import matplotlib.pyplot as plt
import numpy as np
import h3
from io import BytesIO
import base64
from matplotlib.lines import Line2D
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.database import get_clickhouse_client
from app.config import settings
from app.database import get_clickhouse_client
from app.models.schemas import AreaRequest, CoverageResponse
from app.services.coverage_clusters import plot_coverage_clusters
from app.services.coverage_service import get_coverage_data
from app.services.mapping_service import create_coverage_map
import pandas as pd
import logging
from fastapi import APIRouter, HTTPException
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import h3
import numpy as np
from io import BytesIO
import base64


router = APIRouter()

logger = logging.getLogger(__name__)

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


@router.get("/coverage-map", response_class=HTMLResponse)
async def coverage_map(request: Request):
    """Главная страница с гексагональной картой"""
    return templates.TemplateResponse("coverage_map.html", {"request": request})


@router.get("/coverage-data", response_model=List[Dict[str, Any]])
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


@router.get("/coverage-hexmap")
async def get_coverage_hexmap():
    """Генерация гексагональной карты с улучшенной визуализацией"""
    try:
        client = get_clickhouse_client()
        query = """
        SELECT latitude, longitude, band 
        FROM lte_coverage.coverage_data
        WHERE band IN ('LTE1800', 'LTE2100')
        LIMIT 10000
        """
        data = client.execute(query)

        fig, ax = plt.subplots(figsize=(14, 10))

        # Уменьшаем размер гексагонов (используем resolution=9 вместо 8)
        HEX_RESOLUTION = 10

        # Яркие цвета с контрастными границами
        colors = {
            'LTE1800': ('#1f78b4', '#0a4b8c'),  # (fill, edge)
            'LTE2100': ('#e31a1c', '#a50f15')  # (fill, edge)
        }

        # Собираем границы отдельно для каждого типа
        boundaries = {'LTE1800': [], 'LTE2100': []}

        for lat, lon, band in data:
            try:
                hex_id = h3.latlng_to_cell(lat, lon, HEX_RESOLUTION)
                hex_boundary = h3.cell_to_boundary(hex_id)
                boundaries[band].append(np.array([(lon, lat) for lat, lon in hex_boundary]))
            except:
                continue

        # Рисуем LTE2100 ПЕРВЫМИ (чтобы они не перекрывались LTE1800)
        for coords in boundaries['LTE2100']:
            poly = Polygon(
                coords,
                facecolor=colors['LTE2100'][0],
                edgecolor=colors['LTE2100'][1],
                alpha=0.7,  # Увеличили прозрачность
                linewidth=0.8
            )
            ax.add_patch(poly)

        # Затем рисуем LTE1800
        for coords in boundaries['LTE1800']:
            poly = Polygon(
                coords,
                facecolor=colors['LTE1800'][0],
                edgecolor=colors['LTE1800'][1],
                alpha=0.6,
                linewidth=0.5
            )
            ax.add_patch(poly)

        # Автоматическое масштабирование
        ax.autoscale_view()

        # Улучшенная легенда
        legend_elements = [
            Line2D([0], [0], marker='s', color='w', label='LTE1800',
                   markerfacecolor=colors['LTE1800'][0], markersize=15),
            Line2D([0], [0], marker='s', color='w', label='LTE2100',
                   markerfacecolor=colors['LTE2100'][0], markersize=15)
        ]
        ax.legend(handles=legend_elements, fontsize=12)

        ax.set_title('LTE Coverage Hexagonal Map (Resolution 9)', fontsize=14)
        ax.set_xlabel('Longitude', fontsize=12)
        ax.set_ylabel('Latitude', fontsize=12)

        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=120)
        plt.close(fig)
        buf.seek(0)

        return {"image": f"data:image/png;base64,{base64.b64encode(buf.read()).decode('utf-8')}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hexmap", response_class=HTMLResponse)
async def hexmap(request: Request):
    return templates.TemplateResponse("hexmap.html", {"request": request})


def create_coverage_map():
    """Генерирует карту покрытия и возвращает base64 изображение"""
    try:
        client = get_clickhouse_client()
        data = client.execute("""
        SELECT latitude, longitude, band 
        FROM lte_coverage.coverage_data
        WHERE band IN ('LTE1800', 'LTE2100')
        LIMIT 10000
        """)

        fig, ax = plt.subplots(figsize=(12, 8))

        # Центральная точка (антенна)
        base_station = (52.27664, 104.27792)
        ax.scatter(*base_station, c='red', s=100, marker='^', label='Базовая станция')

        # Отрисовка гексагонов
        colors = {'LTE1800': 'blue', 'LTE2100': 'green'}
        for lat, lon, band in data:
            hex_id = h3.latlng_to_cell(lat, lon, 11)
            hex_boundary = h3.cell_to_boundary(hex_id)
            poly = plt.Polygon(
                np.array(hex_boundary),
                color=colors.get(band, 'gray'),
                alpha=0.5,
                edgecolor='white',
                linewidth=0.3
            )
            ax.add_patch(poly)

        # Настройки графика
        ax.set_title('Карта покрытия LTE')
        ax.set_xlabel('Долгота')
        ax.set_ylabel('Широта')
        ax.legend()
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.autoscale_view()

        # Сохранение в буфер
        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
        plt.close()
        return base64.b64encode(buf.getvalue()).decode('utf-8')

    except Exception as e:
        print(f"Ошибка генерации карты: {e}")
        return None


@router.get("/coverage_map_with ", response_class=HTMLResponse)
async def show_coverage_map():
    """Отображает HTML страницу с картой покрытия"""
    map_image = create_coverage_map()

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Карта покрытия LTE</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 20px;
            }}
            .map-container {{
                width: 80%;
                margin: 0 auto;
                text-align: center;
            }}
            #coverage-map {{
                max-width: 100%;
                border: 1px solid #ddd;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
            }}
            .legend {{
                margin: 20px 0;
                padding: 10px;
                background: #f5f5f5;
                border-radius: 5px;
                display: inline-block;
            }}
            .legend-item {{
                display: inline-block;
                margin: 0 15px;
            }}
            .legend-color {{
                display: inline-block;
                width: 20px;
                height: 20px;
                margin-right: 5px;
                vertical-align: middle;
            }}
        </style>
    </head>
    <body>
        <div class="map-container">
            <h1>Карта покрытия LTE</h1>
            <div class="legend">
                <div class="legend-item">
                    <span class="legend-color" style="background: red;"></span>
                    <span>Базовая станция</span>
                </div>
                <div class="legend-item">
                    <span class="legend-color" style="background: blue;"></span>
                    <span>LTE1800</span>
                </div>
                <div class="legend-item">
                    <span class="legend-color" style="background: green;"></span>
                    <span>LTE2100</span>
                </div>
            </div>
            <img id="coverage-map" src="data:image/png;base64,{map_image}" alt="Карта покрытия">
            <div>
                <button onclick="window.location.reload()">Обновить карту</button>
            </div>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)