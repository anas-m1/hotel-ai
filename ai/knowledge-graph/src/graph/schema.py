"""
Neo4j graph schema — node and relationship type definitions.

Graph structure:
  (:Hotel)-[:IN_CITY]->(:City)
  (:Hotel)-[:HAS_AMENITY]->(:Amenity)
  (:Hotel)-[:NEAR_ATTRACTION {distance_km}]->(:Attraction)
  (:City)-[:IN_COUNTRY]->(:Country)
"""

from __future__ import annotations

from pydantic import BaseModel


class HotelNode(BaseModel):
    hotel_code: str
    name: str
    star_rating: float = 0.0
    description: str = ""
    address: str = ""
    check_in_time: str = ""
    check_out_time: str = ""


class CityNode(BaseModel):
    code: str       # IATA city code e.g. "DXB"
    name: str
    country: str = ""
    region: str = ""


class AmenityNode(BaseModel):
    name: str
    category: str = "general"   # "recreation", "wellness", "dining", "business"


class AttractionNode(BaseModel):
    name: str
    category: str = "landmark"  # "landmark", "nature", "culture", "shopping"
    city_code: str = ""


class NearAttractionRel(BaseModel):
    distance_km: float = 0.0


# Static attraction seed data keyed by city code.
# In production this would come from a places API or be curated data.
CITY_ATTRACTIONS: dict[str, list[dict]] = {
    "DXB": [
        {"name": "Burj Khalifa", "category": "landmark"},
        {"name": "Dubai Mall", "category": "shopping"},
        {"name": "Dubai Creek", "category": "culture"},
        {"name": "Palm Jumeirah", "category": "nature"},
    ],
    "LHR": [
        {"name": "Big Ben", "category": "landmark"},
        {"name": "British Museum", "category": "culture"},
        {"name": "Hyde Park", "category": "nature"},
        {"name": "Buckingham Palace", "category": "landmark"},
    ],
    "CDG": [
        {"name": "Eiffel Tower", "category": "landmark"},
        {"name": "The Louvre", "category": "culture"},
        {"name": "Champs-Élysées", "category": "shopping"},
        {"name": "Notre-Dame Cathedral", "category": "culture"},
    ],
    "JFK": [
        {"name": "Central Park", "category": "nature"},
        {"name": "Times Square", "category": "landmark"},
        {"name": "Metropolitan Museum of Art", "category": "culture"},
        {"name": "Brooklyn Bridge", "category": "landmark"},
    ],
    "SIN": [
        {"name": "Gardens by the Bay", "category": "nature"},
        {"name": "Marina Bay Sands", "category": "landmark"},
        {"name": "Sentosa Island", "category": "nature"},
        {"name": "Orchard Road", "category": "shopping"},
    ],
}

# Amenity category mapping
AMENITY_CATEGORIES: dict[str, str] = {
    "pool": "recreation",
    "swimming pool": "recreation",
    "gym": "recreation",
    "fitness center": "recreation",
    "spa": "wellness",
    "sauna": "wellness",
    "massage": "wellness",
    "restaurant": "dining",
    "bar": "dining",
    "rooftop bar": "dining",
    "business center": "business",
    "meeting rooms": "business",
    "conference room": "business",
    "wifi": "connectivity",
    "parking": "transport",
    "airport shuttle": "transport",
    "beach access": "recreation",
    "beachfront": "recreation",
}


def categorise_amenity(name: str) -> str:
    return AMENITY_CATEGORIES.get(name.lower(), "general")
