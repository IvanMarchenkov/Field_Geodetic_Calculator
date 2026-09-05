import json
import os

from export_utils import write_kml, write_map_html, write_pdf
from geodesic import (
    dms_to_deg,
    format_dms,
    inverse_geodetic_problem,
    polar_points_from_station,
)


def set_export_dir(path: str) -> str:
    os.environ["GEOCALC_EXPORT_DIR"] = path
    os.makedirs(path, exist_ok=True)
    return path


def _parse_dms_block(block: dict, label: str) -> float:
    if not isinstance(block, dict):
        raise ValueError(f"Заполните координаты {label}")
    for key in ("d", "m", "s"):
        if block.get(key) in (None, ""):
            raise ValueError(f"Заполните координаты {label}")
        try:
            float(block[key])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Некорректное значение {label}") from exc
    return dms_to_deg(float(block["d"]), float(block["m"]), float(block["s"]))


def _parse_float(value, label: str) -> float:
    if value in (None, ""):
        raise ValueError(f"Не указано: {label}")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Некорректное значение: {label}") from exc


def solve_ogz(payload: str) -> str:
    data = json.loads(payload)
    B1 = _parse_dms_block(data["B1"], "точки 1 (B)")
    L1 = _parse_dms_block(data["L1"], "точки 1 (L)")
    B2 = _parse_dms_block(data["B2"], "точки 2 (B)")
    L2 = _parse_dms_block(data["L2"], "точки 2 (L)")
    a = _parse_float(data.get("a"), "a")
    e2 = _parse_float(data.get("e2"), "e²")
    iterations = int(_parse_float(data.get("iterations", 4), "итерации"))

    if not (-90 <= B1 <= 90 and -90 <= B2 <= 90):
        raise ValueError("Широта должна быть от −90° до 90°")
    if not (-180 <= L1 <= 180 and -180 <= L2 <= 180):
        raise ValueError("Долгота должна быть от −180° до 180°")
    if a <= 0:
        raise ValueError("a должна быть положительной")
    if not (0 < e2 < 1):
        raise ValueError("e² должен быть в интервале (0, 1)")
    if iterations < 1:
        raise ValueError("Число итераций должно быть не меньше 1")

    result = inverse_geodetic_problem(B1, L1, B2, L2, a, e2, iterations)
    return json.dumps(
        {
            "B1_deg": B1,
            "L1_deg": L1,
            "B2_deg": B2,
            "L2_deg": L2,
            "A1_deg": result["A1_deg"],
            "A2_deg": result["A2_deg"],
            "A1_dms": format_dms(result["A1_deg"]),
            "A2_dms": format_dms(result["A2_deg"]),
            "s_m": result["s_m"],
        }
    )


def solve_polar(payload: str) -> str:
    data = json.loads(payload)
    legs = []
    for row in data["legs"]:
        if row.get("s") in (None, ""):
            raise ValueError("Не указано расстояние")
        dist = _parse_float(row["s"], "расстояние")
        if dist <= 0:
            raise ValueError("Расстояние должно быть больше нуля")
        gu = dms_to_deg(
            float(row.get("deg") or 0),
            float(row.get("min") or 0),
            float(row.get("sec") or 0),
        )
        legs.append((gu, dist))
    points = polar_points_from_station(
        float(data["B1"]),
        float(data["L1"]),
        float(data["A1"]),
        legs,
        float(data["a"]),
        float(data["e2"]),
    )
    for point in points:
        point["B_dms"] = format_dms(point["B_deg"])
        point["L_dms"] = format_dms(point["L_deg"])
        point["A_rev_dms"] = format_dms(point["A_rev_deg"])
    return json.dumps(points)


def export_bundle(payload: str, kind: str) -> str:
    data = json.loads(payload)
    points = data["points"]
    meta = data["meta"]
    if kind == "pdf":
        return write_pdf(points, meta)
    if kind == "kml":
        return write_kml(points, meta)
    if kind == "map":
        return write_map_html(points)
    raise ValueError("Неизвестный формат экспорта")
