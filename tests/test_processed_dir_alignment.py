"""Ensure ETL default output dirs match what Streamlit pages read (avoids silent empty dashboards)."""

from __future__ import annotations

from pathlib import Path

import streamlit_io
import uk_local_authority_housing_data as la


def test_la_starts_default_output_dir_matches_streamlit_processed() -> None:
    """CLI default ``-o`` must be the same tree ``streamlit_io.PROCESSED_DIR`` uses."""
    pipeline_default = Path(la.__file__).resolve().parent / "data" / "processed"
    assert streamlit_io.PROCESSED_DIR.resolve() == pipeline_default.resolve()
