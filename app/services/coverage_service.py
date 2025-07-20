from app.database import get_clickhouse_client


def get_coverage_data(min_lat, max_lat, min_lon, max_lon):
    """Получает данные покрытия из базы данных"""
    client = get_clickhouse_client()

    query = '''
    SELECT latitude, longitude, band 
    FROM lte_coverage.coverage_data
    WHERE latitude BETWEEN %(min_lat)s AND %(max_lat)s
    AND longitude BETWEEN %(min_lon)s AND %(max_lon)s
    LIMIT 100000
    '''

    data = client.execute(query, {
        'min_lat': min_lat,
        'max_lat': max_lat,
        'min_lon': min_lon,
        'max_lon': max_lon
    })

    return data