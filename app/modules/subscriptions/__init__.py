"""
Subscriptions Module

Manages service subscriptions (internet, voice, bundles),
payment subscriptions, and tariff management.
"""
from app.modules.subscriptions.routes import router
from app.modules.subscriptions.tariff_routes import router as tariff_router
from app.modules.subscriptions.payment_routes import router as payment_router

__all__ = ["router", "tariff_router", "payment_router"]
