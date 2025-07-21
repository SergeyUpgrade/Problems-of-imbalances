import base64
from io import BytesIO

import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial import ConvexHull
from matplotlib.patches import Polygon
from matplotlib.lines import Line2D

from app.database import get_clickhouse_client


def plot_coverage_clusters():
    # Запрос данных из ClickHouse
    client = get_clickhouse_client()
    data = client.execute("""
    SELECT latitude, longitude, band 
    FROM lte_coverage.coverage_data
    WHERE latitude IS NOT NULL
    LIMIT 10000
    """)

    # Начальная точка (антенна)
    base_station = (52.27664, 104.27792)

    # Преобразование данных
    points = {'LTE1800': [], 'LTE2100': []}
    for lat, lon, band in data:
        if band in points:
            points[band].append((lon, lat))  # (x,y)

    # Создание графика
    plt.figure(figsize=(12, 10))

    # 1. Рисуем начальную точку (антенну)
    plt.scatter(*base_station, c='red', s=100, marker='^', label='Base Station')

    # 2. Рисуем точки приема
    colors = {'LTE1800': 'blue', 'LTE2100': 'green'}
    for band, coords in points.items():
        if coords:
            x, y = zip(*coords)
            plt.scatter(x, y, c=colors[band], s=20, alpha=0.6, label=band)

    # 3. Вычисляем и рисуем кластеры
    for band, coords in points.items():
        if len(coords) > 10:  # Минимальное количество точек для кластера
            points_array = np.array(coords)

            # Вычисляем выпуклую оболочку для кластера
            hull = ConvexHull(points_array)

            # Рисуем косые линии (штриховка)
            poly = Polygon(
                points_array[hull.vertices],
                closed=True,
                fill=False,
                edgecolor=colors[band],
                linestyle='--',
                linewidth=1.5,
                hatch='////',
                alpha=0.4
            )
            plt.gca().add_patch(poly)

    # Настройки графика
    plt.title('LTE Coverage Clusters', fontsize=14)
    plt.xlabel('Longitude', fontsize=12)
    plt.ylabel('Latitude', fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.5)

    # Автомасштабирование с учетом начальной точки
    all_points = [base_station] + [p for coords in points.values() for p in coords]
    x, y = zip(*all_points)
    plt.xlim(min(x) - 0.01, max(x) + 0.01)
    plt.ylim(min(y) - 0.01, max(y) + 0.01)

    # Легенда
    legend_elements = [
        Line2D([0], [0], marker='^', color='w', label='Base Station',
               markerfacecolor='red', markersize=10),
        Line2D([0], [0], marker='o', color='w', label='LTE1800',
               markerfacecolor='blue', markersize=10),
        Line2D([0], [0], marker='o', color='w', label='LTE2100',
               markerfacecolor='green', markersize=10),
        Line2D([0], [0], color='blue', linestyle='--', label='LTE1800 Cluster'),
        Line2D([0], [0], color='green', linestyle='--', label='LTE2100 Cluster')
    ]
    plt.legend(handles=legend_elements, loc='upper right')

    # Сохранение
    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=120)
    plt.close()
    buf.seek(0)
    return base64.b64encode(buf.rad()).decode('utf-8')