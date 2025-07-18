import h3
import pandas as pd
from shapely.geometry import Polygon
import geopandas as gpd
import matplotlib.pyplot as plt

# 1. Близко расположенные города в Московской области
data = [
    (55.7558, 37.6176, 1),  # Москва (центр)
    (55.7690, 37.6380, 2),  # Москва (северо-восток)
    (55.7420, 37.6250, 3)   # Москва (юго-запад)
]
df = pd.DataFrame(data, columns=['latitude', 'longitude', 'band'])

# 2. Создаем H3-ячейки с подходящим разрешением (9 - мелкие, 7 - крупные)
resolution = 9
df['h3_index'] = df.apply(
    lambda row: h3.latlng_to_cell(row['latitude'], row['longitude'], resolution),
    axis=1
)

# 3. Функция для создания полигонов
def create_hexagon(h3_index):
    boundary = h3.cell_to_boundary(h3_index)
    return Polygon([(x[1], x[0]) for x in boundary])  # меняем lat/lng на lng/lat

df['geometry'] = df['h3_index'].apply(create_hexagon)

# 4. Создаем GeoDataFrame
gdf = gpd.GeoDataFrame(df, geometry='geometry', crs="EPSG:4326")

# 5. Визуализация с улучшенным отображением
fig, ax = plt.subplots(figsize=(12, 10))

# Рисуем шестиугольники с прозрачной заливкой
gdf.plot(
    ax=ax,
    facecolor='none',
    edgecolor='blue',
    linewidth=3,
    alpha=0.7,
    label=f'H3 ячейки (уровень {resolution})'
)

# Рисуем исходные точки
gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(df.longitude, df.latitude),
    crs="EPSG:4326"
).plot(
    ax=ax,
    color='red',
    markersize=200,
    marker='*',
    label='Города'
)

# Добавляем подписи
for idx, row in df.iterrows():
    ax.text(
        row['longitude'] + 0.001,
        row['latitude'] + 0.001,
        f"Точка {row['band']}",
        fontsize=12,
        bbox=dict(facecolor='white', alpha=0.7)
    )

# Настраиваем вид
plt.title('Сетка H3 для близко расположенных городов', fontsize=16)
plt.xlabel('Долгота', fontsize=12)
plt.ylabel('Широта', fontsize=12)
plt.grid(True, linestyle=':', alpha=0.5)
plt.legend(fontsize=12)

# Автоматически подбираем границы с небольшим отступом
minx, miny, maxx, maxy = gdf.total_bounds
ax.set_xlim(minx-0.01, maxx+0.01)
ax.set_ylim(miny-0.01, maxy+0.01)

plt.tight_layout()
plt.savefig('h3_close_cities.png', dpi=300)
plt.show()
