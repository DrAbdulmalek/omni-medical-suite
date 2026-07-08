# app/routers/__init__.py
"""API Routers - lazy-loaded to avoid import errors for missing packages"""
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router

# Define available routers (only auth exists as full implementation)
__all__ = ['auth', 'health', 'pipeline', 'ocr', 'jobs', 'datasets', 'models', 'admin']