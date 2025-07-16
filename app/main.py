import os

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.db import get_clickhouse_client
from app.services.coverage import aggregate_coverage_data, generate_map

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")


@app.get("/coverage/{band}", response_class=HTMLResponse)
async def get_coverage(band: int, request: Request):
    try:
        ch_client = get_clickhouse_client()
        df = aggregate_coverage_data(ch_client, band)
        output_path = "app/templates/coverage_map.html"

        # Создаём директорию, если её нет
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        generate_map(df, band, output_path)
        return templates.TemplateResponse("coverage_map.html", {"request": request})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))