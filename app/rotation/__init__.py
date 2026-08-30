"""Analytical capital-rotation comparisons; no signal, sizing, or execution capability."""

from .engine import CapitalRotationEngine
from .models import PortfolioRotationEvaluation, RotationCandidate, RotationConfig

__all__ = ["CapitalRotationEngine", "PortfolioRotationEvaluation", "RotationCandidate", "RotationConfig"]
