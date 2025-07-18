import os
from pathlib import Path

import h3
import pandas as pd
import folium
from clickhouse_driver import Client
from typing import Optional
import geopandas as gpd
from matplotlib import pyplot as plt

from config import H3_RESOLUTION, CLICKHOUSE_HOST, CLICKHOUSE_USER, CLICKHOUSE_PASSWORD, CLICKHOUSE_DB

#def load_excel_to_clickhouse():
#    """Загружает данные из Excel во временную таблицу ClickHouse."""
#    current_dir = Path(__file__).parent
#    file_path = current_dir / "Данные проблемы дисбалансов.xlsx"
#
#    if not file_path.exists():
#        available_files = "\n".join(os.listdir(current_dir / "coverage"))
#        raise FileNotFoundError(
#            f"Файл '{file_path}' не найден!\n"
#            f"Доступные файлы в {current_dir }:\n{available_files}"
#        )
#
#    df = pd.read_excel(file_path, sheet_name=0, usecols=["latitude", "longitude", "band","servingcellrsrp", "avtocod", "eventtime"])
#    df["band"] = df["band"].map({"LTE1800": 1800, "LTE2100": 2100})
#
#    print(df.head(5))
#
#    # Подключение к ClickHouse
#    ch_client = Client(
#        host=CLICKHOUSE_HOST,
#        user=CLICKHOUSE_USER,
#        password=CLICKHOUSE_PASSWORD,
#        database=CLICKHOUSE_DB,
#        settings={"use_numpy": True}
#    )
#
#    # Создаём временную таблицу
#    ch_client.execute(f"""
#    CREATE TABLE IF NOT EXISTS emr_ch.distr_h3_emr (
#        latitude Float64,
#        longitude Float64,
#        band Integer,
#        servingcellrsrp Float64,
#        avtocod Integer,
#        eventtime Datetime
#    ) ENGINE = MergeTree
#    ORDER BY band
#    """)
#
#    # Вставляем данные
#    ch_client.insert_dataframe(f"INSERT INTO emr_ch.distr_h3_emr VALUES", df)
def load_excel_to_clickhouse():
    """Загружает данные из Excel во временную таблицу ClickHouse."""
    current_dir = Path(__file__).parent
    file_path = current_dir / "Данные проблемы дисбалансов.xlsx"

    try:
        df = pd.read_excel(file_path,
                           sheet_name=0,
                           usecols=["latitude", "longitude", "band", "servingcellrsrp", "avtocod", "eventtime"])
        df["band"] = df["band"].map({"LTE1800": 1800, "LTE2100": 2100})

        # Подключение к ClickHouse
        ch_client = Client(
            host=CLICKHOUSE_HOST,
            user=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
            database=CLICKHOUSE_DB,
            settings={"use_numpy": True}
        )

        # Вставка данных
        ch_client.insert_dataframe(
            "INSERT INTO emr_ch.distr_h3_emr (latitude, longitude, band, servingcellrsrp, avtocod, eventtime) VALUES",
            df
        )
        print("Данные успешно загружены в ClickHouse")
        return True  # Успешное завершение
    except Exception as e:
        print(f"Ошибка при загрузке данных: {str(e)}")
        return False  # Ошибка


def aggregate_coverage_data(ch_client, band: int) -> pd.DataFrame:
    """Агрегирует данные по H3-ячейкам"""
    print(f"Запрашиваем данные для band={band}")

    query = """
SELECT 
    latitude,
    longitude,
    band,
    geoToH3(latitude, longitude, 7) AS h3_index,
    h3ToGeoBoundary(h3_index) AS boundary
FROM emr_ch.distr_h3_emr
WHERE band = %(band)s
"""
    params = {'band': band}
    return ch_client.execute(query, params)


# Основной код
if __name__ == "__main__":
    # 1. Загрузка данных
    load_success = load_excel_to_clickhouse()

    if load_success:
        # 2. Подключение для запроса данных
        ch_client = Client(
            host=CLICKHOUSE_HOST,
            user=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
            database=CLICKHOUSE_DB
        )

        # 3. Получение данных (пример для band=1800)
        result = aggregate_coverage_data(ch_client, band=1800)

        if result:
            print(f"Получено строк из ClickHouse: {len(result)}")
            # Дальнейшая обработка...
        else:
            print("Запрос не вернул данных. Проверьте:")
            print("- Существует ли таблица emr_ch.distr_h3_emr")
            print("- Есть ли данные для выбранного band")
    else:
        print("Не удалось загрузить данные в ClickHouse")

# Конвертируем в DataFrame
df = pd.DataFrame(result, columns=['latitude', 'longitude', 'band', 'h3_index', 'boundary'])
# Преобразуем boundary в геометрию (если нужно для geopandas)
from shapely.geometry import Polygon

df['geometry'] = df['boundary'].apply(lambda b: Polygon([(x[1], x[0]) for x in b]))
# 4. Создаем GeoDataFrame
gdf = gpd.GeoDataFrame(df, geometry='geometry', crs="EPSG:4326")
if not gdf.empty:
    # Рассчитываем границы
    minx, miny, maxx, maxy = gdf.total_bounds

    # Проверяем, что границы корректны
    if not all(pd.notna([minx, miny, maxx, maxy])):
        raise ValueError("Некорректные географические координаты")

    # Рассчитываем ширину и высоту
    width = maxx - minx
    height = maxy - miny

    # Проверяем, чтобы height не был близок к нулю
    if height < 0.0001:
        height = 0.0001

    # Создаем фигуру
    fig, ax = plt.subplots(figsize=(12, 10))

    # Рисуем шестиугольники
    gdf.plot(
        ax=ax,
        facecolor='none',
        edgecolor='blue',
        linewidth=1,  # Уменьшаем толщину для лучшего отображения
        alpha=0.7,
        label=f'H3 ячейки (уровень {H3_RESOLUTION})'
    )

    # Рисуем точки
    gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df.longitude, df.latitude),
        crs="EPSG:4326"
    ).plot(
        ax=ax,
        color='red',
        markersize=50,  # Уменьшаем размер точек
        marker='.',
        label='Точки измерений'
    )

    # Настраиваем пропорции карты
    try:
        aspect_ratio = width / height
        ax.set_aspect(aspect_ratio / np.cos(np.deg2rad(np.mean([miny, maxy]))))
    except:
        ax.set_aspect('equal')

    # Устанавливаем границы с запасом
    padding = max(width, height) * 0.1
    ax.set_xlim(minx - padding, maxx + padding)
    ax.set_ylim(miny - padding, maxy + padding)

    # Оформление
    plt.title('Распределение измерений по H3-ячейкам', fontsize=14)
    plt.xlabel('Долгота')
    plt.ylabel('Широта')
    plt.grid(True, linestyle=':', alpha=0.5)
    plt.legend()

    plt.tight_layout()
    plt.savefig('h3_coverage.png', dpi=300, bbox_inches='tight')
    plt.show()
else:
    print("Нет данных для визуализации")
    #params = {'resolution': H3_RESOLUTION, 'band': band}
#
    #try:
    #    # Выводим выполняемый запрос
    #    print(f"Выполняем запрос:\n{query % params}")
#
    #    data = ch_client.execute(query, params)
    #    print(f"Получено {len(data)} записей")  # Количество полученных строк
#
    #    if not data:
    #        print("Предупреждение: запрос вернул 0 записей!")
#
    #    return pd.DataFrame(data, columns=["latitude", "longitude", "h3_index"])
#
    #except Exception as e:
    #    print(f"Ошибка при выполнении запроса: {str(e)}")
    #    raise
#
#
#
#def# generate_map(df: pd.DataFrame, band: int, output_file: str) -> folium.Map:
#   # """Генерирует карту покрытия и сохраняет в HTML"""
#   # if df.empty:
#   #     raise ValueError("Нет данных для визуализации")
##
#   # center = [df['latitude'].mean(), df['longitude'].mean()]
#   # m = folium.Map(location=center, zoom_start=12)
##
#   # for _, row in df.iterrows():
#   #     hexagon = h3.cell_to_boundary(row['h3_index'])
#   #     color = "green" if row['rsrp'] >= -85 else "orange" if row['rsrp'] >= -100 else "red"
#   #     folium.Polygon(
#   #         locations=hexagon,
#   #         color=color,
#   #         fill=True,
#   #         popup=f"RSRP: {row['rsrp']:.1f} dBm (Band {band})"
#   #     ).add_to(m)
##
#   # m.save(output_file)
#   # return m
#def #generate_map(df: pd.DataFrame, band: int, output_file: str) -> folium.Map:
    #"""Генерирует карту покрытия и сохраняет в HTML"""
    #if df.empty:
    #    raise ValueError("Нет данных для визуализации")
#
    #center = [df['latitude'].mean(), df['longitude'].mean()]
    #print(center)
    #m = folium.Map(location=center, zoom_start=12)
    #print(m)
#
    #for _, row in df.iterrows():
    #    # Получаем границы ячейки в формате [[lat, lng], [lat, lng], ...]
    #    hexagon_coords = h3.cell_to_boundary(row['h3_index'])
#
    #    # Преобразуем координаты в формат [ [lng, lat], [lng, lat], ... ] для GeoJSON
    #    hexagon_geojson = [[lng, lat] for lat, lng in hexagon_coords]
#
    #    color = "green" if row['rsrp'] >= -85 else "orange" if row['rsrp'] >= -100 else "red"
    #    folium.Polygon(
    #        locations=hexagon_geojson,
    #        color=color,
    #        fill=True,
    #        fill_opacity=0.6,
    #        popup=f"RSRP: {row['rsrp']:.1f} dBm (Band {band})"
    #    ).add_to(m)
#
    #m.save(output_file)
    #return m

# Пример использования
#if __name__ == "__main__":
#    # 1. Загрузка Excel в ClickHouse
#    load_excel_to_clickhouse("Данные проблемы дисбалансов.xlsx")
#
#    # 2. Агрегация для Band 3 (1800 МГц)
#    df = aggregate_coverage_data(band=3)
#
#    # 3. Визуализация
#    generate_map(df, band=3, output_file="coverage_band3.html")