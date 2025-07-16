import os
from dotenv import load_dotenv

load_dotenv()

CLICKHOUSE_HOST = "localhost"
CLICKHOUSE_USER = "default"
CLICKHOUSE_PASSWORD = ""
CLICKHOUSE_DB = "emr_ch"

# Уровень детализации H3 (10 ~ 500 м)
H3_RESOLUTION = 10