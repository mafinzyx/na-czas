"""Small geometry helpers shared by the route providers."""

import math

LatLon = tuple[float, float]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * earth_radius_km * math.asin(math.sqrt(a))


def path_length_km(points: list[LatLon]) -> float:
    return sum(haversine_km(*a, *b) for a, b in zip(points, points[1:]))


def decode_polyline(encoded: str, precision: int = 5) -> list[LatLon]:
    """Decodes Google's encoded polyline format into (lat, lon) pairs."""
    factor = 10**precision
    points: list[LatLon] = []
    index = lat = lon = 0

    while index < len(encoded):
        deltas = []
        for _ in range(2):
            shift = result = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        lat += deltas[0]
        lon += deltas[1]
        points.append((lat / factor, lon / factor))
    return points


def thin(points: list, max_points: int) -> list:
    """Keeps at most max_points evenly spaced items, always including the last one."""
    if len(points) <= max_points:
        return points
    step = (len(points) - 1) / (max_points - 1)
    return [points[round(i * step)] for i in range(max_points)]
