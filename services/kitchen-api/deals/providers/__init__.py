"""
Providers package for deals module.
"""
from .base import DealsProvider
from .mock_ca import MockCAProvider

__all__ = ["DealsProvider", "MockCAProvider"]
