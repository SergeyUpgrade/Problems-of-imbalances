import geopandas as gpd
import matplotlib.pyplot as plt
from io import BytesIO
import base64


def create_coverage_map(df):
    """Создает карту покрытия из DataFrame"""
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df.longitude, df.latitude),
        crs="EPSG:4326"
    )

    lte1800 = gdf[gdf['band'] == 'LTE1800']
    lte2100 = gdf[gdf['band'] == 'LTE2100']

    fig, ax = plt.subplots(figsize=(10, 10))

    if not lte1800.empty:
        lte1800.plot(ax=ax, color='blue', markersize=5, label='LTE1800')
    if not lte2100.empty:
        lte2100.plot(ax=ax, color='red', markersize=5, label='LTE2100')

    ax.legend()
    plt.title('LTE Coverage Map')
    plt.xlabel('Longitude')
    plt.ylabel('Latitude')

    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close()

    return base64.b64encode(buf.getvalue()).decode('utf-8')