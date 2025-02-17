from shapely.geometry import Point
from shapely.wkb import loads
from shapely.wkt import loads as wkt_loads  # ✅ Import for WKT handling
import math

def validate_location(lat: float, lon: float, db_location) -> bool:
    """
    Validates if the provided coordinates are within acceptable range
    of the QR code's location.
    """
    if not db_location:
        return True
    
    try:
        # Check if db_location is already a WKT string and parse it
        if isinstance(db_location, str) and db_location.startswith("POINT"):
            db_point = wkt_loads(db_location)  # ✅ Use Shapely's WKT parser
        elif hasattr(db_location, "desc"):  # If it's a WKTElement from GeoAlchemy
            db_point = wkt_loads(db_location.desc)
        else:
            # Handle cases where it's a WKB (fallback)
            db_point = loads(bytes.fromhex(db_location))
    except Exception as e:
        print(f"Error parsing location: {e}")
        return False  # If location parsing fails, assume invalid

    scan_point = Point(lon, lat)

    # Calculate distance (50 meters threshold)
    return db_point.distance(scan_point) <= 0.00045  # approximately 50 meters


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r * 1000  # Convert to meters
