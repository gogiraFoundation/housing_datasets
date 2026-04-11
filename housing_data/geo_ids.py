"""Normalised geography identifiers (e.g. LAD GSS codes)."""

from __future__ import annotations


def norm_lad(x: object) -> str:
    return str(x).strip().upper()
