"""Reusable Streamlit UI fragments for dashboard pages."""

from __future__ import annotations

import streamlit as st

from ons_epc_config import OGL_ATTRIBUTION


def ogl_attribution_expander() -> None:
    """ONS Open Government Licence text in a collapsible block (avoids a full-width st.info banner)."""
    with st.expander("Open Government Licence and attribution"):
        st.markdown(OGL_ATTRIBUTION)
