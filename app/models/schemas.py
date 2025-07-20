from datetime import datetime

from pydantic import BaseModel

class AreaRequest(BaseModel):
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float

class CoverageResponse(BaseModel):
    map_image: str

class CoveragePoint(BaseModel):
    latitude: float
    longitude: float
    altitude: float
    band: str
    rsrp: float
    rsrq: float
    eventtime: datetime
    h3_index: str