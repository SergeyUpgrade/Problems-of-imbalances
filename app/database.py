from clickhouse_driver import Client
import pandas as pd
import os


def init_clickhouse():
    client = Client(host='localhost')

    # Создаем базу данных и таблицу, если их нет
    client.execute('CREATE DATABASE IF NOT EXISTS lte_coverage')
    client.execute('''
    CREATE TABLE IF NOT EXISTS lte_coverage.coverage_data (
        latitude Float64,
        longitude Float64,
        band String,
        h3_index String
    ) ENGINE = MergeTree()
    ORDER BY (band, h3_index)
    ''')
    return client


def load_data_to_clickhouse(client, file_path):
    # Читаем данные из Excel
    df = pd.read_excel(file_path)

    # Добавляем H3 индекс для каждой точки (разрешение 9 - около 175м)
    import h3
    df['h3_index'] = df.apply(
        lambda row: h3.latlng_to_cell(row['latitude'], row['longitude'], 9),
        axis=1
    )

    # Загружаем данные в ClickHouse
    client.execute(
        'INSERT INTO lte_coverage.coverage_data VALUES',
        df.to_dict('records')
    )