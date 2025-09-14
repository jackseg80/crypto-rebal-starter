"""
ML module for unified prediction processing
"""

from .gating import get_gating_system, initialize_gating_system, GatingConfig

__all__ = [
    "get_gating_system",
    "initialize_gating_system",
    "GatingConfig"
]