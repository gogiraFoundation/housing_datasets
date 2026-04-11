"""Emit processed_manifest.json listing tidy outputs and raw *.meta.json hashes for reproducibility."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

_REPO = Path(__file__).resolve().parents[1]

if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=_REPO / "data" / "processed" / "processed_manifest.json",
        help="Output JSON path.",
    )
    args = p.parse_args()

    processed = _REPO / "data" / "processed"
    raw = _REPO / "data" / "raw"

    files: list[dict] = []
    if processed.is_dir():
        for path in sorted(processed.glob("*.parquet")):
            st = path.stat()
            mtime_iso = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
            row: dict = {
                "path": str(path.relative_to(_REPO)),
                "kind": "parquet",
                "size_bytes": st.st_size,
                "mtime_utc": mtime_iso,
            }
            try:
                pf = pq.ParquetFile(path)
                row["columns"] = list(pf.schema.names)
                md = pf.metadata
                if md is not None:
                    row["num_rows"] = md.num_rows
                h = hashlib.sha256()
                with open(path, "rb") as f:
                    for chunk in iter(lambda: f.read(1024 * 1024), b""):
                        h.update(chunk)
                row["sha256_hex"] = h.hexdigest()
            except OSError:
                pass
            files.append(row)
    meta_files: list[dict] = []
    if raw.is_dir():
        for path in sorted(raw.glob("*.meta.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                sha = payload.get("sha256_hex") or payload.get("sha256")
            except (json.JSONDecodeError, OSError):
                payload = {}
                sha = None
            meta_files.append(
                {
                    "path": str(path.relative_to(_REPO)),
                    "sha256": sha,
                    "source_url": payload.get("source_url"),
                }
            )

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "open_government_licence": (
            "Contains public sector information licensed under the Open Government Licence v3.0. "
            "Source: Office for National Statistics where applicable."
        ),
        "processed_parquet": files,
        "raw_meta_json": meta_files,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")

    from housing_api.registry import build_registry

    reg = build_registry()
    api_snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "datasets": {
            k: {
                "id": v.id,
                "title": v.title,
                "family": v.family,
                "filename": v.filename,
            }
            for k, v in sorted(reg.items())
        },
        "processed_basenames": sorted({Path(r["path"]).name for r in files}),
    }
    reg_path = args.output.parent / "api_registry.json"
    reg_path.write_text(json.dumps(api_snapshot, indent=2), encoding="utf-8")
    print(f"Wrote {reg_path}")


if __name__ == "__main__":
    main()
