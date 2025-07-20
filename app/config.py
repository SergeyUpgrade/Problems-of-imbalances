import os
from pathlib import Path

class Settings:
    CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
    CLICKHOUSE_DB = os.getenv("CLICKHOUSE_DB", "lte_coverage")
    CLICKHOUSE_USER=os.getenv("CLICKHOUSE_USER", "default")
    CLICKHOUSE_PASSWORD=os.getenv("CLICKHOUSE_PASSWORD", "")
    DATA_FILE = Path("../data/Данные проблемы дисбалансов.xlsx")

settings = Settings()