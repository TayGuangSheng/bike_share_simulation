from fastapi import APIRouter

from .routes import auth, bikes, rides, routes, analytics, payments, lab, pricing


def create_api_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    router.include_router(auth.router)
    router.include_router(bikes.router)
    router.include_router(rides.router)
    router.include_router(pricing.router)
    router.include_router(routes.router)
    router.include_router(analytics.router)
    router.include_router(payments.router)
    router.include_router(lab.router)
    return router

