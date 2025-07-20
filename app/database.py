import h3
from clickhouse_driver import Client
import pandas as pd

from app.config import settings


def get_clickhouse_client():
    """Инициализация клиента ClickHouse"""
    return Client(host=settings.CLICKHOUSE_HOST)


def init_database():
    """Инициализация базы данных и таблиц"""
    client = get_clickhouse_client()

    client.execute(f'CREATE DATABASE IF NOT EXISTS {settings.CLICKHOUSE_DB}')
    client.execute(f'''
    CREATE TABLE IF NOT EXISTS {settings.CLICKHOUSE_DB}.coverage_data (
        latitude Float64,
        longitude Float64,
        altitude Float64,
        band String,
        rsrp Float64,
        rsrq Float64,
        h3_index String,
        eventtime DateTime
    ) ENGINE = MergeTree()
    ORDER BY (band, h3_index)
    ''')
    return client


def load_data_to_clickhouse(client, file_path):
    """Загрузка данных из Excel в ClickHouse"""
    df = pd.read_excel(file_path)

    numeric_cols = ['vbw', 'servingcellrsrp', 'servingcellrsrq']
    for col in numeric_cols:
        if col in df.columns and df[col].dtype == object:
            df[col] = df[col].astype(str).str.replace(',', '.').astype(float)

    df = df.rename(columns={
        'servingcellrsrp': 'rsrp',
        'servingcellrsrq': 'rsrq',
        'height': 'altitude'
    })

    df['h3_index'] = df.apply(
        lambda row: h3.latlng_to_cell(row['latitude'], row['longitude'], 8),
        axis=1
    )

    columns_to_load = [
        'latitude', 'longitude', 'altitude', 'band',
        'rsrp', 'rsrq', 'h3_index', 'eventtime'
    ]
    existing_columns = [col for col in columns_to_load if col in df.columns]

    client.execute(
        f'INSERT INTO {settings.CLICKHOUSE_DB}.coverage_data VALUES',
        df[existing_columns].to_dict('records')
    )