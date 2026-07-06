# app/routers/__init__.py
"""API Routers - lazy-loaded to avoid import errors for missing packages"""
from app.routers.auth import router as auth_router

# Define available routers (only auth exists as full implementation)
__all__ = ['auth', 'pipeline', 'ocr', 'jobs', 'datasets', 'models', 'admin']