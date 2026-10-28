"""
HealDeploy Flask Application Package
=====================================
Uses an application factory (create_app) so that tests can instantiate
the app with isolated configuration without side effects.
"""

from .app import create_app

__all__ = ["create_app"]
