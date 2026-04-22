"""Download UK region + country boundaries as WGS84 GeoJSON from ONS ArcGIS.

Combines:
- England **Government Office Regions** (December 2022 EN BUC): ``RGN22CD`` / ``RGN22NM``
- **UK countries** (December 2022 UK BUC): ``CTRY22CD`` / ``CTRY22NM`` — Wales, Scotland, Northern Ireland only
  (England country polygon is omitted because regions already tile England).

Each feature gets ``region_code`` and ``region_name`` for joins with ``region_housing_market_snapshot.parquet``.
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

_DEFAULT_ENG = (
    "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
    "Regions_December_2022_EN_BUC/FeatureServer/0/query"
    "?where=1%3D1&outFields=RGN22CD,RGN22NM&outSR=4326&f=geojson&returnGeometry=true"
)
_DEFAULT_UK = (
    "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
    "Countries_December_2022_UK_BUC/FeatureServer/0/query"
    "?where=1%3D1&outFields=CTRY22CD,CTRY22NM&outSR=4326&f=geojson&returnGeometry=true"
)

_ENGLAND_COUNTRY = "E92000001"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _fetch_geojson(url: str, *, timeout: float = 120.0) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "housing_datasets/1.0 (ONS boundary download)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    data = json.loads(raw.decode("utf-8"))
    if data.get("type") != "FeatureCollection":
        raise SystemExit(f"Unexpected GeoJSON root: {data!r}")
    return data


def _norm_eng_features(fc: dict) -> list[dict]:
    out: list[dict] = []
    for feat in fc.get("features") or []:
        props = dict(feat.get("properties") or {})
        code = str(props.get("RGN22CD", "")).strip().upper()
        name = str(props.get("RGN22NM", "")).strip()
        if not code:
            continue
        props["region_code"] = code
        props["region_name"] = name
        props["lad_code"] = code  # alias for map join logic shared with LAD GeoJSON
        feat["properties"] = props
        out.append(feat)
    return out


def _norm_country_features(fc: dict) -> list[dict]:
    out: list[dict] = []
    for feat in fc.get("features") or []:
        props = dict(feat.get("properties") or {})
        code = str(props.get("CTRY22CD", "")).strip().upper()
        name = str(props.get("CTRY22NM", "")).strip()
        if not code or code == _ENGLAND_COUNTRY:
            continue
        props["region_code"] = code
        props["region_name"] = name
        props["lad_code"] = code
        feat["properties"] = props
        out.append(feat)
    return out


def download(*, eng_url: str, uk_url: str, dest: Path, timeout: float = 120.0) -> Path:
    eng = _fetch_geojson(eng_url, timeout=timeout)
    uk = _fetch_geojson(uk_url, timeout=timeout)
    feats = _norm_eng_features(eng) + _norm_country_features(uk)
    merged = {"type": "FeatureCollection", "features": feats}
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(merged, ensure_ascii=False), encoding="utf-8")
    return dest


def main() -> int:
    root = _repo_root()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=root / "data" / "geo" / "regions_uk_wgs84.geojson",
        help="Output GeoJSON path (default: data/geo/regions_uk_wgs84.geojson).",
    )
    p.add_argument("--eng-url", default=_DEFAULT_ENG, help="ArcGIS query URL for English regions BUC.")
    p.add_argument("--uk-url", default=_DEFAULT_UK, help="ArcGIS query URL for UK countries BUC.")
    args = p.parse_args()
    out = download(eng_url=args.eng_url, uk_url=args.uk_url, dest=args.output)
    n = len(json.loads(out.read_text(encoding="utf-8")).get("features") or [])
    print(f"Wrote {out} ({n} features).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
