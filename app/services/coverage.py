import h3
import pandas as pd
import folium
from clickhouse_driver import Client
from typing import Optional
from config import H3_RESOLUTION, CLICKHOUSE_HOST, CLICKHOUSE_USER, CLICKHOUSE_PASSWORD, CLICKHOUSE_DB


def load_excel_to_clickhouse(file_path: str, table_name: str = "temp_coverage") -> None:
    """Загружает данные из Excel во временную таблицу ClickHouse."""
    df = pd.read_excel("Данные проблемы дисбалансов.xlsx")

    # Подключение к ClickHouse
    ch_client = Client(
        host=CLICKHOUSE_HOST,
        user=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DB
    )

    # Создаём временную таблицу
    ch_client.execute(f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        latitude Float64,
        longitude Float64,
        rsrp Float64,
        band UInt8,
        eventtime DateTime DEFAULT now()
    ) ENGINE = Memory
    """)

    # Вставляем данные
    ch_client.execute(f"INSERT INTO {table_name} (latitude, longitude, rsrp, band) VALUES", df.to_dict('records'))


def get_coverage_data(band: int, table_name: str = "temp_coverage") -> pd.DataFrame:
    """Агрегирует данные из ClickHouse по H3-ячейкам."""
    ch_client = Client(
        host=CLICKHOUSE_HOST,
        user=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DB
    )

    query = f"""
    SELECT 
        latitude, longitude, rsrp,
        h3ToCell(latitude, longitude, {H3_RESOLUTION}) AS h3_index
    FROM {table_name}
    WHERE band = {band}
    """
    data = ch_client.execute(query)
    df = pd.DataFrame(data, columns=["latitude", "longitude", "rsrp", "h3_index"])
    return df.groupby("h3_index").agg({"rsrp": "mean", "latitude": "first", "longitude": "first"}).reset_index()


def generate_map(df: pd.DataFrame, band: int, output_file: str) -> None:
    """Генерирует карту покрытия."""
    m = folium.Map(location=[df['latitude'].mean(), df['longitude'].mean()], zoom_start=12)

    for _, row in df.iterrows():
        hexagon = h3.h3_to_geo_boundary(row['h3_index'], geo_json=True)
        color = "green" if row['rsrp'] >= -85 else "orange" if row['rsrp'] >= -100 else "red"
        folium.Polygon(
            locations=hexagon,
            color=color,
            fill=True,
            popup=f"RSRP: {row['rsrp']:.1f} dBm"
        ).add_to(m)

    m.save(output_file)


# Пример использования
if __name__ == "__main__":
    # 1. Загрузка Excel в ClickHouse
    load_excel_to_clickhouse("path/to/data.xlsx")

    # 2. Агрегация для Band 3 (1800 МГц)
    df = get_coverage_data(band=3)

    # 3. Визуализация
    generate_map(df, band=3, output_file="coverage_band3.html")