"""
Facade module for tests: re-export core security_hardening from src.security_core
This file allows tests that import `security_hardening` at top-level to work
without changing test imports.
"""
from src.security_core.security_hardening import *  # noqa: F401,F403

__all__ = [name for name in dir() if not name.startswith("_")]
