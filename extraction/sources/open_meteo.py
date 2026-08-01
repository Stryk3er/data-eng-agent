"""Open-Meteo archive API. No API key required.

Freshness caveat (real, not hypothetical): the archive endpoint lags a few
days behind "today" because it's backed by reanalysis/QA'd station data,
not live readings. extract.py accounts for this via freshness_lag_days.
"""
from datetime import date

import pandas as pd
import requests

from extraction.retry import with_retries

LOCATIONS = {
    "cdmx": {"lat": 19.4326, "lon": -99.1332},
    "monterrey": {"lat": 25.6866, "lon": -100.3161},
}

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS raw.open_meteo_daily (
    location VARCHAR,
    date DATE,
    temp_max_c DOUBLE,
    temp_min_c DOUBLE,
    precipitation_mm DOUBLE,
    extracted_at TIMESTAMP,
    PRIMARY KEY (location, date)
)
"""


@with_retries(max_attempts=5, retry_exceptions=(requests.RequestException,))
def _fetch(lat: float, lon: float, start: date, end: date) -> dict:
    resp = requests.get(
        "https://archive-api.open-meteo.com/v1/archive",
        params={
            "latitude": lat,
            "longitude": lon,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "America/Mexico_City",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def extract(start: date, end: date) -> pd.DataFrame:
    rows = []
    now = pd.Timestamp.utcnow()
    for loc_name, coords in LOCATIONS.items():
        payload = _fetch(coords["lat"], coords["lon"], start, end)
        daily = payload.get("daily", {})
        for d, tmax, tmin, precip in zip(
            daily.get("time", []),
            daily.get("temperature_2m_max", []),
            daily.get("temperature_2m_min", []),
            daily.get("precipitation_sum", []),
        ):
            rows.append(
                {
                    "location": loc_name,
                    "date": d,
                    "temp_max_c": tmax,
                    "temp_min_c": tmin,
                    "precipitation_mm": precip,
                    "extracted_at": now,
                }
            )
    return pd.DataFrame(rows)
