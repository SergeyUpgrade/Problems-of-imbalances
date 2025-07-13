from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.db import get_clickhouse_client
from app.services.coverage import get_coverage_data, generate_map

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")

@app.get("/coverage/{band}", response_class=HTMLResponse)
async def get_coverage(band: int, request: Request):
    """Генерирует карту покрытия для заданного band."""
    ch_client = get_clickhouse_client()
    df = get_coverage_data(ch_client, band)
    generate_map(df, band)
    return templates.TemplateResponse("map.html", {"request": request})