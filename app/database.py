import h3
from clickhouse_driver import Client
import pandas as pd

from app.config import settings


def get_clickhouse_client():
    """Инициализация клиента ClickHouse"""
    return Client(host=settings.CLICKHOUSE_HOST, user=settings.CLICKHOUSE_USER, password=settings.CLICKHOUSE_PASSWORD, database=settings.CLICKHOUSE_DB)

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
    """Улучшенная загрузка данных с проверками"""
    try:
        # 1. Чтение файла
        print(f"Чтение файла: {file_path}")
        df = pd.read_excel(file_path)
        print(f"Прочитано строк: {len(df)}")
        print("Колонки в файле:", df.columns.tolist())

        # 2. Обработка числовых колонок
        numeric_cols = ['vbw', 'servingcellrsrp', 'servingcellrsrq']
        for col in numeric_cols:
            if col in df.columns:
                print(f"Обработка колонки {col}, тип: {df[col].dtype}")
                if df[col].dtype == object:
                    df[col] = df[col].astype(str).str.replace(',', '.').astype(float)
                else:
                    df[col] = df[col].astype(float)
                print(f"После преобразования - тип: {df[col].dtype}")

        # 3. Переименование колонок
        rename_map = {
            'servingcellrsrp': 'rsrp',
            'servingcellrsrq': 'rsrq',
            'height': 'altitude'
        }
        print("Переименование колонок:")
        for old_name, new_name in rename_map.items():
            if old_name in df.columns:
                print(f"  {old_name} -> {new_name}")
                df.rename(columns={old_name: new_name}, inplace=True)

        # 4. Добавление H3 индекса
        if 'latitude' in df.columns and 'longitude' in df.columns:
            print("Добавление H3 индексов...")
            df['h3_index'] = df.apply(
                lambda row: h3.latlng_to_cell(row['latitude'], row['longitude'], 8),
                axis=1
            )
        else:
            raise ValueError("Отсутствуют колонки latitude или longitude")

        # 5. Подготовка к загрузке
        columns_to_load = [
            'latitude', 'longitude', 'altitude', 'band',
            'rsrp', 'rsrq', 'h3_index', 'eventtime'
        ]
        existing_columns = [col for col in columns_to_load if col in df.columns]
        missing_columns = [col for col in columns_to_load if col not in df.columns]
        df['eventtime'] = pd.to_datetime(df['eventtime'])
        print(df['eventtime'].dtype)

        print("Колонки для загрузки:", existing_columns)
        print("Отсутствующие колонки:", missing_columns)

        if not existing_columns:
            raise ValueError("Нет колонок для загрузки")

        # 6. Загрузка данных
        print(f"Загрузка {len(df)} строк в ClickHouse...")
        data_to_insert = df[existing_columns].to_dict('records')

        # Проверка первых 2 строк
        print("Пример данных для вставки (первые 2 строки):")
        for row in data_to_insert[:2]:
            print(row)

        client.execute(
            f'INSERT INTO {settings.CLICKHOUSE_DB}.coverage_data ({", ".join(existing_columns)}) VALUES',
            data_to_insert
        )

        print("Загрузка завершена успешно!")
        return True

    except Exception as e:
        print(f"Ошибка при загрузке данных: {str(e)}")
        raise


