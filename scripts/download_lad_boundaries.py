"""Download UK Local Authority District boundaries as WGS84 GeoJSON from ONS ArcGIS.

Saves to data/geo/lad_uk_wgs84.geojson (Local Authority Districts December 2022 UK BUC).
Each feature includes LAD22CD and a duplicate lad_code for joins with ONS Local Authority Code.
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

_DEFAULT_URL = (
    "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
    "Local_Authority_Districts_December_2022_UK_BUC_V2/FeatureServer/0/query"
    "?where=1%3D1&outFields=LAD22CD,LAD22NM&outSR=4326&f=geojson&returnGeometry=true"
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def download(*, url: str, dest: Path, timeout: float = 120.0) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "housing_datasets/1.0 (ONS boundary download)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    data = json.loads(raw.decode("utf-8"))
    if data.get("type") != "FeatureCollection":
        raise SystemExit(f"Unexpected GeoJSON root: {data!r}")
    for feat in data.get("features") or []:
        props = feat.get("properties") or {}
        code = str(props.get("LAD22CD", "")).strip().upper()
        if code:
            props["lad_code"] = code
        feat["properties"] = props
    dest.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return dest


def main() -> int:
    root = _repo_root()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=root / "data" / "geo" / "lad_uk_wgs84.geojson",
        help="Output GeoJSON path (default: data/geo/lad_uk_wgs84.geojson).",
    )
    p.add_argument("--url", default=_DEFAULT_URL, help="ArcGIS query URL (default: ONS LAD Dec 2022 UK BUC).")
    args = p.parse_args()
    out = download(url=args.url, dest=args.output)
    n = len(json.loads(out.read_text(encoding="utf-8")).get("features") or [])
    print(f"Wrote {out} ({n} features).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
