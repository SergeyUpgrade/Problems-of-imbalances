from app.db import get_clickhouse_client
client = get_clickhouse_client()
print(client.execute("SHOW TABLES FROM emr_ch"))

from clickhouse_driver import Client

def check_database():
    ch = Client(host='localhost')
    print("Базы данных:", ch.execute("SHOW DATABASES"))
    print("Таблицы в emr_ch:", ch.execute("SHOW TABLES FROM emr_ch"))

check_database()