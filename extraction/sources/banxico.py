"""Banxico SIE API — USD/MXN FIX rate (series SF43718).

Free API token, no card, requested at:
https://www.banxico.org.mx/SieAPIRest/service/v1/token

Banxico marks non-business days (weekends/holidays) with "N/E" instead of
a value. We drop those rows here on purpose -- the gap is real and belongs
to the source, not something to paper over in extraction. It's filled
downstream in dbt (int_fx_gap_filled), where it's visible and testable.
"""
import os
from datetime import date

import pandas as pd
import requests

from extraction.retry import with_retries

SERIES = {"fx_usd_mxn": "SF43718"}

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS raw.banxico_fx (
    series VARCHAR,
    date DATE,
    value DOUBLE,
    extracted_at TIMESTAMP,
    PRIMARY KEY (series, date)
)
"""

BASE_URL = "https://www.banxico.org.mx/SieAPIRest/service/v1/series"


@with_retries(max_attempts=5, retry_exceptions=(requests.RequestException,))
def _fetch(serie_id: str, start: date, end: date, token: str) -> dict:
    url = f"{BASE_URL}/{serie_id}/datos/{start.isoformat()}/{end.isoformat()}"
    resp = requests.get(url, headers={"Bmx-Token": token}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def extract(start: date, end: date) -> pd.DataFrame:
    token = os.environ.get("BANXICO_TOKEN")
    if not token:
        raise RuntimeError(
            "BANXICO_TOKEN is not set. Get a free token at "
            "https://www.banxico.org.mx/SieAPIRest/service/v1/token and export it "
            "(locally in .env, in CI as a repo secret)."
        )

    now = pd.Timestamp.utcnow()
    rows = []
    for name, serie_id in SERIES.items():
        payload = _fetch(serie_id, start, end, token)
        datos = payload["bmx"]["series"][0].get("datos", [])
        for point in datos:
            raw_value = point["dato"]
            if raw_value in ("N/E", ""):
                continue
            rows.append(
                {
                    "series": name,
                    "date": pd.to_datetime(point["fecha"], dayfirst=True).date(),
                    "value": float(raw_value.replace(",", "")),
                    "extracted_at": now,
                }
            )
    return pd.DataFrame(rows)
