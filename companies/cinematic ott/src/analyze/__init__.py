"""Phase 3 — VLM call -> scene_analysis JSON for any image."""

from .analyzer import analyze_image, DEFAULT_MODEL  # noqa: F401

__all__ = ["analyze_image", "DEFAULT_MODEL"]
