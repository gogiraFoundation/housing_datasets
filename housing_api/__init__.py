"""FastAPI service: versioned read-only API for processed housing datasets."""

from housing_api.app import create_app
from housing_api.constants import API_PREFIX

__all__ = ["API_PREFIX", "create_app"]
