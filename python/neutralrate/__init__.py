"""
neutralrate - replication of the six estimation methods for Japan's natural
rate of interest surveyed by the Bank of Japan (Nakano, Sugioka & Yamamoto
2024, BOJ WP 24-E-12; BOJ Review 2026-E-4).
"""
from . import config, data  # noqa: F401
from .methods import METHOD_REGISTRY  # noqa: F401

__version__ = "1.0.0"
__all__ = ["config", "data", "METHOD_REGISTRY", "run_all"]
