from clickhouse_driver import Client
from config import CLICKHOUSE_HOST, CLICKHOUSE_USER, CLICKHOUSE_PASSWORD, CLICKHOUSE_DB

def test_connection():
    client = Client(
        host=CLICKHOUSE_HOST,
        user=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD
    )
    try:
        databases = client.execute("SHOW DATABASES")
        print("Доступные базы данных:", [db[0] for db in databases])
        if CLICKHOUSE_DB not in [db[0] for db in databases]:
            print(f"❌ База данных '{CLICKHOUSE_DB}' не существует!")
    except Exception as e:
        print(f"Ошибка подключения: {e}")

test_connection()

def ensure_schema_exists():
    client = Client(
        host=CLICKHOUSE_HOST,
        user=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD
    )
    client.execute("CREATE DATABASE IF NOT EXISTS emr_ch")
    client.execute("""
    CREATE TABLE IF NOT EXISTS emr_ch.distr_h3_emr (
        latitude Float64,
        longitude Float64,
        band String,
    ) ENGINE = MergeTree()
    ORDER BY (eventtime, band)
    """)


ensure_schema_exists()


def get_clickhouse_client():
    client = Client(
        host=CLICKHOUSE_HOST,
        user=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD
    )

    # Проверяем и создаём БД, если её нет
    client.execute(f"CREATE DATABASE IF NOT EXISTS {CLICKHOUSE_DB}")

    client = Client(
        host=CLICKHOUSE_HOST,
        user=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DB
    )
    try:
        client.execute("SELECT 1")
        print("✅ ClickHouse: подключение успешно")
    except Exception as e:
        print(f"❌ ClickHouse: ошибка подключения - {e}")
    return client
