from pydantic import BaseModel

class AreaRequest(BaseModel):
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float

class CoverageResponse(BaseModel):
    map_image: str