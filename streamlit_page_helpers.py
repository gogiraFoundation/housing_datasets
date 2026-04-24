"""Reusable Streamlit UI fragments for dashboard pages."""

from __future__ import annotations

from typing import Mapping, Sequence

import streamlit as st

from ons_epc_config import OGL_ATTRIBUTION


def ogl_attribution_expander() -> None:
    """ONS Open Government Licence text in a collapsible block (avoids a full-width st.info banner)."""
    with st.expander("Open Government Licence and attribution"):
        st.markdown(OGL_ATTRIBUTION)


def render_missing_or_empty(
    missing_by_tab: Mapping[str, Sequence[str]],
    tab_key: str,
    *,
    is_empty: bool,
    empty_message: str,
) -> bool:
    """Render normalized tab state message and return whether content is blocked.

    Priority:
    1) Missing source files -> blocking error.
    2) Empty result for current selection -> informational message.
    """
    missing_files = missing_by_tab.get(tab_key) or []
    if missing_files:
        st.error(f"Missing source file(s): {', '.join(missing_files)}")
        return True
    if is_empty:
        st.info(empty_message)
        return True
    return False
