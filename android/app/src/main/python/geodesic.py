"""Обратная и прямая геодезические задачи (формулы лабораторной работы МИИГАиК)."""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

# GRS80 / WGS-84 (большая полуось и квадрат первого эксцентриситета)
WGS84_A = 6378137.0
WGS84_E2 = 0.00669437999014


def dms_to_deg(degrees: float, minutes: float, seconds: float) -> float:
    sign = -1.0 if degrees < 0 or minutes < 0 or seconds < 0 else 1.0
    return sign * (abs(degrees) + abs(minutes) / 60.0 + abs(seconds) / 3600.0)


def deg_to_dms(value: float) -> Tuple[int, int, float]:
    sign = -1 if value < 0 else 1
    abs_val = abs(value)
    degrees = int(abs_val)
    minutes_full = (abs_val - degrees) * 60.0
    minutes = int(minutes_full)
    seconds = (minutes_full - minutes) * 60.0
    if seconds >= 59.9995:
        seconds = 0.0
        minutes += 1
    if minutes >= 60:
        minutes = 0
        degrees += 1
    return sign * degrees, minutes, seconds


def format_dms(value: float, precision: int = 1) -> str:
    d, m, s = deg_to_dms(value)
    hemi = ""
    if d < 0:
        hemi = "-"
        d = abs(d)
    return f"{hemi}{d}° {m:02d}′ {s:0{precision + 3}.{precision}f}″"


def normalize_deg_0_360(value: float) -> float:
    return value % 360.0


def normalize_lon(value: float) -> float:
    wrapped = (value + 180.0) % 360.0 - 180.0
    if wrapped == -180.0:
        return 180.0
    return wrapped


def inverse_geodetic_problem(
    B1_deg: float,
    L1_deg: float,
    B2_deg: float,
    L2_deg: float,
    a: float = WGS84_A,
    e2: float = WGS84_E2,
    iterations: int = 4,
) -> Dict[str, float]:
    """ОГЗ, формулы (28)–(50). Коэффициенты A, B', C' — лабораторные (47)–(49)."""
    del a  # в лабораторной схеме расстояние не зависит от a

    B1 = math.radians(B1_deg)
    L1 = math.radians(L1_deg)
    B2 = math.radians(B2_deg)
    L2 = math.radians(L2_deg)

    sin_B1, cos_B1 = math.sin(B1), math.cos(B1)
    sin_B2, cos_B2 = math.sin(B2), math.cos(B2)

    W1 = math.sqrt(1.0 - e2 * sin_B1 ** 2)
    W2 = math.sqrt(1.0 - e2 * sin_B2 ** 2)

    sin_u1 = sin_B1 * math.sqrt(1.0 - e2) / W1
    sin_u2 = sin_B2 * math.sqrt(1.0 - e2) / W2
    cos_u1 = cos_B1 / W1
    cos_u2 = cos_B2 / W2

    l_deg = math.degrees(L2 - L1)
    a1 = sin_u1 * sin_u2
    a2 = cos_u1 * cos_u2
    b1 = cos_u1 * sin_u2
    b2 = sin_u1 * cos_u2

    delta = 0.0
    lam_deg = 0.0
    A1 = 0.0
    sigma = 0.0
    x = 0.0
    sin_A0 = 0.0
    cos2_A0 = 0.0
    sin_sigma = 0.0
    cos_sigma = 0.0

    for _ in range(max(1, int(iterations))):
        lam_deg = l_deg + math.degrees(delta)
        lam = math.radians(lam_deg)
        p = cos_u2 * math.sin(lam)
        q = b1 - b2 * math.cos(lam)
        A1 = math.atan2(p, q)
        sin_sigma = p * math.sin(A1) + q * math.cos(A1)
        cos_sigma = a1 + a2 * math.cos(lam)
        sigma = math.atan2(sin_sigma, cos_sigma)
        sin_A0 = cos_u1 * math.sin(A1)
        cos2_A0 = 1.0 - sin_A0 ** 2
        x = 2.0 * a1 - cos_sigma * cos2_A0
        alpha = (33523299.0 - (28189.0 - 70.0 * cos2_A0) * cos2_A0) * 1e-10
        beta = (28189.0 - 94.0 * cos2_A0) * 1e-10
        delta = (alpha * sigma - beta * x * sin_sigma) * sin_A0

    lam = math.radians(lam_deg)
    # (50) через atan2 — азимут геодезической в конечной точке; обратный = +180°.
    A2_dir = math.atan2(cos_u1 * math.sin(lam), b1 * math.cos(lam) - b2)
    A2_rev = A2_dir + math.pi
    A = 6356863.020 + (10708.959 - 13.474 * cos2_A0) * cos2_A0
    B_prime = 10708.938 - 17.956 * cos2_A0
    C_prime = 4.487
    y = (cos2_A0 ** 2 - 2.0 * x ** 2) * cos_sigma
    s = A * sigma + (B_prime * x + C_prime * y) * sin_sigma

    return {
        "A1_deg": normalize_deg_0_360(math.degrees(A1)),
        "A2_deg": normalize_deg_0_360(math.degrees(A2_rev)),
        "A2_dir_deg": normalize_deg_0_360(math.degrees(A2_dir)),
        "s_m": s,
        "sigma_rad": sigma,
        "lambda_rad": lam,
    }


def direct_geodetic_problem(
    B1_deg: float,
    L1_deg: float,
    A1_deg: float,
    s_m: float,
    a: float = WGS84_A,
    e2: float = WGS84_E2,
) -> Dict[str, float]:
    """ПГЗ по Бесселю, формулы (28)–(30), (54)–(70) задания №4."""
    if s_m < 0:
        raise ValueError("Длина геодезической линии не может быть отрицательной")
    if not (0.0 < e2 < 1.0):
        raise ValueError("Квадрат эксцентриситета e² должен быть в интервале (0, 1)")
    if a <= 0:
        raise ValueError("Большая полуось a должна быть положительной")

    B1 = math.radians(B1_deg)
    L1 = math.radians(L1_deg)
    A1 = math.radians(A1_deg)

    b = a * math.sqrt(1.0 - e2)
    ep2 = e2 / (1.0 - e2)

    W1 = math.sqrt(1.0 - e2 * math.sin(B1) ** 2)
    sin_u1 = math.sin(B1) * math.sqrt(1.0 - e2) / W1
    cos_u1 = math.cos(B1) / W1

    sin_A0 = cos_u1 * math.sin(A1)
    if abs(sin_u1) < 1e-18:
        sin2_sigma1 = 0.0
        cos2_sigma1 = 1.0 if (cos_u1 * math.cos(A1)) >= 0.0 else -1.0
    else:
        ctg_sigma1 = (cos_u1 * math.cos(A1)) / sin_u1
        ctg2 = ctg_sigma1 ** 2
        sin2_sigma1 = (2.0 * ctg_sigma1) / (ctg2 + 1.0)
        cos2_sigma1 = (ctg2 - 1.0) / (ctg2 + 1.0)

    cos2_A0 = 1.0 - sin_A0 ** 2
    k2 = ep2 * cos2_A0
    k4 = k2 ** 2
    k6 = k2 ** 3

    A_coeff = b * (1.0 + k2 / 4.0 - 3.0 * k4 / 64.0 + 5.0 * k6 / 256.0)
    B_coeff = b * (k2 / 8.0 - k4 / 32.0 + 15.0 * k6 / 1024.0)
    C_coeff = b * (k4 / 128.0 - 3.0 * k6 / 512.0)

    e4 = e2 ** 2
    e6 = e2 ** 3
    alpha = (e2 / 2.0 + e4 / 8.0 + e6 / 16.0) - (e4 / 16.0 + e6 / 16.0) * cos2_A0 + (
        3.0 * e6 / 128.0
    ) * (cos2_A0 ** 2)
    beta = (e4 / 32.0 + e6 / 32.0) * cos2_A0 - (e6 / 64.0) * (cos2_A0 ** 2)

    sigma0 = (s_m - (B_coeff + C_coeff * cos2_sigma1) * sin2_sigma1) / A_coeff
    sin2_sigma0 = math.sin(2.0 * sigma0)
    cos2_sigma0 = math.cos(2.0 * sigma0)
    sin2_sum = sin2_sigma1 * cos2_sigma0 + cos2_sigma1 * sin2_sigma0
    cos2_sum = cos2_sigma1 * cos2_sigma0 - sin2_sigma1 * sin2_sigma0
    sigma = sigma0 + (B_coeff + 5.0 * C_coeff * cos2_sum) * sin2_sum / A_coeff

    delta = (alpha * sigma + beta * (sin2_sum - sin2_sigma1)) * sin_A0

    sin_sigma = math.sin(sigma)
    cos_sigma = math.cos(sigma)
    sin_u2 = sin_u1 * cos_sigma + cos_u1 * math.cos(A1) * sin_sigma
    sin_u2 = max(-1.0, min(1.0, sin_u2))
    cos_u2_term = math.sqrt(max(0.0, 1.0 - sin_u2 ** 2))
    if cos_u2_term < 1e-18:
        B2 = math.copysign(math.pi / 2.0, sin_u2)
    else:
        B2 = math.atan(sin_u2 / (math.sqrt(1.0 - e2) * cos_u2_term))

    num_l = math.sin(A1) * sin_sigma
    den_l = cos_u1 * cos_sigma - sin_u1 * sin_sigma * math.cos(A1)
    lam = math.atan2(num_l, den_l)
    L2 = L1 + lam - delta

    num_a = cos_u1 * math.sin(A1)
    den_a = cos_u1 * cos_sigma * math.cos(A1) - sin_u1 * sin_sigma
    A2_dir = math.atan2(num_a, den_a)
    A2_rev = A2_dir + math.pi

    return {
        "B2_deg": math.degrees(B2),
        "L2_deg": normalize_lon(math.degrees(L2)),
        "A2_dir_deg": normalize_deg_0_360(math.degrees(A2_dir)),
        "A2_rev_deg": normalize_deg_0_360(math.degrees(A2_rev)),
        "sigma_rad": sigma,
        "delta_rad": delta,
    }


def polar_points_from_station(
    B1_deg: float,
    L1_deg: float,
    A0_deg: float,
    legs: List[Tuple[float, float]],
    a: float = WGS84_A,
    e2: float = WGS84_E2,
) -> List[Dict[str, float]]:
    """Полярная засечка: каждая нога — (ГУ в градусах, расстояние в метрах) от точки 1."""
    results = []
    for index, (gu_deg, distance) in enumerate(legs, start=3):
        azimuth = normalize_deg_0_360(A0_deg + gu_deg)
        computed = direct_geodetic_problem(B1_deg, L1_deg, azimuth, distance, a, e2)
        results.append(
            {
                "number": index,
                "gu_deg": gu_deg,
                "azimuth_deg": azimuth,
                "s_m": distance,
                "B_deg": computed["B2_deg"],
                "L_deg": computed["L2_deg"],
                "A_rev_deg": computed["A2_rev_deg"],
            }
        )
    return results
