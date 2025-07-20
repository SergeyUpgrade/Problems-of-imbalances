import os
from pathlib import Path

class Settings:
    CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
    CLICKHOUSE_DB = os.getenv("CLICKHOUSE_DB", "lte_coverage")
    DATA_FILE = Path("../data/Данные проблемы дисбалансов.xlsx")

settings = Settings()