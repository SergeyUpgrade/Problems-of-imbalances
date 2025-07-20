from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.models.schemas import AreaRequest, CoverageResponse
from app.services.coverage_service import get_coverage_data
from app.services.mapping_service import create_coverage_map
import pandas as pd

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def show_map(request: Request):
    """Главная страница с картой"""
    return templates.TemplateResponse("map.html", {"request": request})


@router.post("/coverage", response_model=CoverageResponse)
async def get_coverage(area: AreaRequest):
    """Получение данных покрытия для заданной области"""
    data = get_coverage_data(
        area.min_lat, area.max_lat,
        area.min_lon, area.max_lon
    )

    df = pd.DataFrame(data, columns=['latitude', 'longitude', 'band'])
    map_img = create_coverage_map(df)

    return {"map_image": map_img}
