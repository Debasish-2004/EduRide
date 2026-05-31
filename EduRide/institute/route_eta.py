import math


BUS_SPEED_KMH = 40


def _haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two GPS points in kilometres."""
    radius_km = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _cumulative_route_distances(route_coords):
    distances = [0]
    for index in range(1, len(route_coords)):
        prev_lat, prev_lng = route_coords[index - 1]
        lat, lng = route_coords[index]
        distances.append(
            distances[index - 1] + _haversine_km(prev_lat, prev_lng, lat, lng)
        )
    return distances


def _project_point_to_route(lat, lng, route_coords, cumulative_distances):
    best_distance = float("inf")
    best_route_km = 0

    lat_scale = 111.32
    lng_scale = 111.32 * math.cos(math.radians(lat))

    for index in range(len(route_coords) - 1):
        start_lat, start_lng = route_coords[index]
        end_lat, end_lng = route_coords[index + 1]

        segment_x = (end_lng - start_lng) * lng_scale
        segment_y = (end_lat - start_lat) * lat_scale
        point_x = (lng - start_lng) * lng_scale
        point_y = (lat - start_lat) * lat_scale

        segment_len_sq = segment_x * segment_x + segment_y * segment_y
        if segment_len_sq == 0:
            t = 0
        else:
            t = (point_x * segment_x + point_y * segment_y) / segment_len_sq
            t = max(0, min(1, t))

        closest_lat = start_lat + (end_lat - start_lat) * t
        closest_lng = start_lng + (end_lng - start_lng) * t
        distance = _haversine_km(lat, lng, closest_lat, closest_lng)

        if distance < best_distance:
            best_distance = distance
            segment_km = cumulative_distances[index + 1] - cumulative_distances[index]
            best_route_km = cumulative_distances[index] + segment_km * t

    return best_route_km


def compute_eta_minutes(stops, route_coords=None):
    """
    Compute cumulative stop ETA using route-polyline distance when available.

    Stops are expected to be ordered and contain ``lat``/``lng`` keys. The list is
    mutated in place and returned. If route geometry is missing, this falls back
    to direct stop-to-stop Haversine distance.
    """
    if route_coords and len(route_coords) > 1:
        cumulative_distances = _cumulative_route_distances(route_coords)
        route_positions = [
            _project_point_to_route(
                stop["lat"], stop["lng"], route_coords, cumulative_distances
            )
            for stop in stops
        ]
        route_origin_km = route_positions[0] if route_positions else 0
        previous_eta_minutes = 0

        for index, stop in enumerate(stops):
            distance_from_origin = max(0, route_positions[index] - route_origin_km)
            eta_minutes = round((distance_from_origin / BUS_SPEED_KMH) * 60)
            stop["eta_minutes"] = max(previous_eta_minutes, eta_minutes)
            previous_eta_minutes = stop["eta_minutes"]
        return stops

    for index, stop in enumerate(stops):
        if index == 0:
            stop["eta_minutes"] = 0
        else:
            prev = stops[index - 1]
            dist_km = _haversine_km(prev["lat"], prev["lng"], stop["lat"], stop["lng"])
            travel_min = (dist_km / BUS_SPEED_KMH) * 60
            stop["eta_minutes"] = prev["eta_minutes"] + round(travel_min)
    return stops
