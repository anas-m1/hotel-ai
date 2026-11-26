"""Verify the seeded catalog before scoring facts; does not verify the vector index."""

import hashlib
import json

from scoring import json_differences


def verify_catalog(base_url, expected, get_json):
    listed = get_json(base_url.rstrip("/") + "/v1/hotels?limit=100")
    if sorted(h["hotel_code"] for h in listed) != sorted(
        h["hotel_code"] for h in expected["hotels"]
    ):
        raise ValueError("Catalog hotel codes differ from the evaluation fixture")
    snapshot = {"hotels": []}
    for fixture in expected["hotels"]:
        code = fixture["hotel_code"]
        hotel = get_json(base_url.rstrip("/") + "/v1/hotels/" + code)
        row = {k: hotel[k] for k in fixture if k not in {"rooms", "facilities"}}
        facilities = hotel.get("facilities", "")
        row["facilities"] = sorted(x.strip() for x in facilities.split(",") if x.strip())
        rooms = get_json(base_url.rstrip("/") + f"/v1/hotels/{code}/rooms")
        row["rooms"] = sorted(
            [
                {
                    "room_number": str(r["room_number"]),
                    "room_type": r["room_type"],
                    "capacity": r["capacity"],
                    "base_price": float(r["base_price"]),
                    "currency": r["currency"],
                }
                for r in rooms
            ],
            key=lambda r: r["room_number"],
        )
        snapshot["hotels"].append(row)
    differences = json_differences(expected, snapshot)
    if differences:
        raise ValueError("Catalog fixture mismatch: " + "; ".join(differences[:5]))
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
