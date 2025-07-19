import numpy as np
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from matplotlib.collections import PolyCollection
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


def create_hex_map(df, resolution=8):
    """Создает карту с гексагонами H3"""
    plt.figure(figsize=(12, 10))
    ax = plt.gca()

    # Цвета для разных частот
    colors = {'LTE1800': 'blue', 'LTE2100': 'red'}

    # Собираем уникальные гексагоны для каждой частоты
    hexagons = {band: set() for band in df['band'].unique()}

    for _, row in df.iterrows():
        hex_id = h3.latlng_to_cell(row['latitude'], row['longitude'], resolution)
        hexagons[row['band']].add(hex_id)

    # Рисуем гексагоны
    for band, hex_ids in hexagons.items():
        if not hex_ids:
            continue

        polygons = []
        for hex_id in hex_ids:
            # Получаем границы гексагона
            points = h3.cell_to_boundary(hex_id, geo_json=True)
            polygons.append(np.array(points))

        # Создаем коллекцию полигонов
        coll = PolyCollection(
            polygons,
            facecolors=colors[band],
            edgecolors='black',
            linewidths=0.3,
            alpha=0.6,
            label=band
        )
        ax.add_collection(coll)

    # Настраиваем вид карты
    ax.autoscale_view()
    plt.title('LTE Coverage Hexagons')
    plt.xlabel('Longitude')
    plt.ylabel('Latitude')

    # Добавляем легенду
    if any(hexagons.values()):
        plt.legend()

    # Сохраняем в буфер
    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    plt.close()
    buf.seek(0)

    return base64.b64encode(buf.read()).decode('utf-8')


@app.post("/api/coverage/hex")
async def get_hex_coverage(area: AreaRequest):
    try:
        # Тестовые данные (замените на реальные)
        test_data = [
            (52.330262, 104.208583, "LTE1800"),
            (52.331000, 104.209000, "LTE2100"),
            (52.332000, 104.210000, "LTE1800"),
            (52.332500, 104.211000, "LTE2100"),
            (52.333000, 104.212000, "LTE1800")
        ]

        df = pd.DataFrame(test_data, columns=['latitude', 'longitude', 'band'])

        # Генерируем сетку гексагонов
        hex_image = create_hex_map(df, resolution=8)

        return JSONResponse({
            "status": "success",
            "map_image": hex_image,
            "hex_count": sum(len(hexagons) for hexagons in [
                set(h3.latlng_to_cell(lat, lon, 8)
                    for lat, lon, _ in test_data)
            ])
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
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