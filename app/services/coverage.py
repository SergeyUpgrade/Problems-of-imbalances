import os
from pathlib import Path

import h3
import pandas as pd
import folium
from clickhouse_driver import Client
from typing import Optional
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
    df = pd.read_excel(file_path,
                       sheet_name=0,
                       usecols=["latitude", "longitude", "band", "servingcellrsrp", "avtocod", "eventtime"])

    # Функция для безопасного преобразования band
    def safe_convert_band(band_value):
        try:
            if pd.isna(band_value):
                return 0  # или другое значение по умолчанию

            # Если значение уже число
            if isinstance(band_value, (int, float)):
                return int(band_value)

            # Если строка вида "LTE1800"
            if isinstance(band_value, str):
                # Извлекаем все цифры из строки
                digits = ''.join(filter(str.isdigit, band_value))
                return int(digits) if digits else 0

            return 0  # для всех остальных случаев
        except (ValueError, TypeError):
            return 0

    # Применяем преобразование
    df["band"] = df["band"].apply(safe_convert_band)

    # Проверяем результат
    print("Статистика по band:")
    print(df["band"].value_counts(dropna=False))

    # Подключение к ClickHouse
    ch_client = Client(
        host=CLICKHOUSE_HOST,
        user=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DB,
        settings={"use_numpy": True}
    )

    # Вставка с явным указанием столбцов
    try:
        ch_client.insert_dataframe(
            "INSERT INTO emr_ch.distr_h3_emr (latitude, longitude, band, servingcellrsrp, avtocod, eventtime) VALUES",
            df
        )
        print("Данные успешно загружены в ClickHouse")
    except Exception as e:
        print(f"Ошибка при загрузке данных: {str(e)}")
        # Выводим первые проблемные строки
        print("Пример проблемных данных:")
        print(df.head())

load_excel_to_clickhouse()


def aggregate_coverage_data(ch_client, band: int) -> pd.DataFrame:
    """Агрегирует данные по H3-ячейкам"""
    print(f"Запрашиваем данные для band={band}")  # Отладочный вывод

    query = """
    SELECT 
        latitude, longitude, servingcellrsrp,
        geoToH3(latitude, longitude, %(resolution)s) AS h3_index
    FROM emr_ch.distr_h3_emr
    WHERE 
        avtocod = 38
        AND band = %(band)s
    """

    params = {'resolution': H3_RESOLUTION, 'band': band}

    try:
        # Выводим выполняемый запрос
        print(f"Выполняем запрос:\n{query % params}")

        data = ch_client.execute(query, params)
        print(f"Получено {len(data)} записей")  # Количество полученных строк

        if not data:
            print("Предупреждение: запрос вернул 0 записей!")

        return pd.DataFrame(data, columns=["latitude", "longitude", "rsrp", "h3_index"])

    except Exception as e:
        print(f"Ошибка при выполнении запроса: {str(e)}")
        raise



#def generate_map(df: pd.DataFrame, band: int, output_file: str) -> folium.Map:
#    """Генерирует карту покрытия и сохраняет в HTML"""
#    if df.empty:
#        raise ValueError("Нет данных для визуализации")
#
#    center = [df['latitude'].mean(), df['longitude'].mean()]
#    m = folium.Map(location=center, zoom_start=12)
#
#    for _, row in df.iterrows():
#        hexagon = h3.cell_to_boundary(row['h3_index'])
#        color = "green" if row['rsrp'] >= -85 else "orange" if row['rsrp'] >= -100 else "red"
#        folium.Polygon(
#            locations=hexagon,
#            color=color,
#            fill=True,
#            popup=f"RSRP: {row['rsrp']:.1f} dBm (Band {band})"
#        ).add_to(m)
#
#    m.save(output_file)
#    return m
def generate_map(df: pd.DataFrame, band: int, output_file: str) -> folium.Map:
    """Генерирует карту покрытия и сохраняет в HTML"""
    if df.empty:
        raise ValueError("Нет данных для визуализации")

    center = [df['latitude'].mean(), df['longitude'].mean()]
    m = folium.Map(location=center, zoom_start=12)

    for _, row in df.iterrows():
        # Получаем границы ячейки в формате [[lat, lng], [lat, lng], ...]
        hexagon_coords = h3.cell_to_boundary(row['h3_index'])

        # Преобразуем координаты в формат [ [lng, lat], [lng, lat], ... ] для GeoJSON
        hexagon_geojson = [[lng, lat] for lat, lng in hexagon_coords]

        color = "green" if row['rsrp'] >= -85 else "orange" if row['rsrp'] >= -100 else "red"
        folium.Polygon(
            locations=hexagon_geojson,
            color=color,
            fill=True,
            fill_opacity=0.6,
            popup=f"RSRP: {row['rsrp']:.1f} dBm (Band {band})"
        ).add_to(m)

    m.save(output_file)
    return m

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