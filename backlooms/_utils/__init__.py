"""
Utility subpackage for the Backlooms framework.

This package contains small, self‑contained helpers used by higher‑level
components. Utilities here must remain free of heavy runtime dependencies
and avoid side effects on import. The goal is to provide narrowly scoped
building blocks (e.g., CLI command constructors) that can be safely reused
across the framework without introducing coupling.

Notes:
- Keep functions minimal and deterministic; prefer pure functions where possible.
- Avoid importing application modules from here to prevent cycles; treat this
  package as a low‑level layer.
- Public utilities should have precise type hints and clear docstrings so they
  are self‑describing and easy to compose.

Author: Vladimir Perekladov
Email: gleero@gmail.com
"""
