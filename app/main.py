from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import h3
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from io import BytesIO
import base64
from app.database import init_clickhouse, load_data_to_clickhouse
import os

app = FastAPI()

# Настраиваем шаблоны
templates = Jinja2Templates(directory="app/templates")

# Инициализируем ClickHouse
client = init_clickhouse()

# Загружаем данные при старте (если еще не загружены)
DATA_FILE = "data/Данные проблемы дисбалансов.xlsx"
if os.path.exists(DATA_FILE):
    load_data_to_clickhouse(client, DATA_FILE)


class AreaRequest(BaseModel):
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float


@app.get("/", response_class=HTMLResponse)
async def show_map(request: Request):
    """Главная страница с картой"""
    return templates.TemplateResponse("map.html", {"request": request})


@app.post("/api/coverage")
async def get_coverage(area: AreaRequest):
    """Получение данных покрытия для заданной области"""
    query = '''
    SELECT latitude, longitude, band 
    FROM lte_coverage.coverage_data
    WHERE latitude BETWEEN %(min_lat)s AND %(max_lat)s
    AND longitude BETWEEN %(min_lon)s AND %(max_lon)s
    LIMIT 10000
    '''
    data = client.execute(query, {
        'min_lat': area.min_lat,
        'max_lat': area.max_lat,
        'min_lon': area.min_lon,
        'max_lon': area.max_lon
    })

    # Преобразуем в DataFrame
    df = pd.DataFrame(data, columns=['latitude', 'longitude', 'band'])

    # Создаем карту
    map_img = create_coverage_map(df)

    return {"map_image": map_img}


def create_coverage_map(df):
    """Создает карту покрытия из DataFrame"""
    # Создаем GeoDataFrame
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df.longitude, df.latitude),
        crs="EPSG:4326"
    )

    # Разделяем по частотам
    lte1800 = gdf[gdf['band'] == 'LTE1800']
    lte2100 = gdf[gdf['band'] == 'LTE2100']

    # Создаем карту
    fig, ax = plt.subplots(figsize=(10, 10))

    # Рисуем точки разными цветами
    if not lte1800.empty:
        lte1800.plot(ax=ax, color='blue', markersize=5, label='LTE1800')
    if not lte2100.empty:
        lte2100.plot(ax=ax, color='red', markersize=5, label='LTE2100')

    ax.legend()
    plt.title('LTE Coverage Map')
    plt.xlabel('Longitude')
    plt.ylabel('Latitude')

    # Сохраняем в буфер
    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close()

    # Кодируем в base64 для HTML
    return base64.b64encode(buf.getvalue()).decode('utf-8')