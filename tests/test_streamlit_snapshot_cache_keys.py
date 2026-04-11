"""Guardrail: Streamlit omits leading-underscore params from @st.cache_data keys (see Streamlit docs)."""

from __future__ import annotations

import ast
from pathlib import Path


def _func_param_names(path: Path, func_name: str) -> list[str]:
    """Positional + keyword-only names (Streamlit hashes both; ``*``, ``_`` snapshot pitfalls apply)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            return [a.arg for a in node.args.args + node.args.kwonlyargs]
    raise AssertionError(f"Function {func_name!r} not found in {path}")


def test_load_tidy_sources_snapshot_is_cache_key_not_excluded() -> None:
    """``sources_snapshot`` is forwarded to ``load_processed_*`` as ``inputs_snapshot`` (hashed there)."""
    root = Path(__file__).resolve().parents[1]
    names = _func_param_names(root / "pages" / "1_Housing_starts.py", "load_tidy")
    assert "sources_snapshot" in names, "use sources_snapshot, not _sources_snapshot (Streamlit skips leading _)"
    assert "_sources_snapshot" not in names


def test_summary_payload_inputs_snapshot_is_cache_key_not_excluded() -> None:
    root = Path(__file__).resolve().parents[1]
    names = _func_param_names(root / "pages" / "0_UK_housing_summary.py", "_summary_payload")
    assert "inputs_snapshot" in names, "snapshot must be hashed — use inputs_snapshot, not _inputs_snapshot"
    assert "_inputs_snapshot" not in names


def test_streamlit_io_load_processed_snapshot_kwonly_is_hashed() -> None:
    """``load_processed_*`` use keyword-only ``inputs_snapshot``; underscore prefix would skip hashing."""
    root = Path(__file__).resolve().parents[1]
    for fn in ("load_processed_parquet", "load_processed_csv"):
        names = _func_param_names(root / "streamlit_io.py", fn)
        assert "inputs_snapshot" in names, f"{fn}: use inputs_snapshot (kwonly), not _inputs_snapshot"
        assert "_inputs_snapshot" not in names
