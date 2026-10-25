from fastapi import APIRouter

from app.api.v1.routes import auth, benefits, claims, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(claims.router)
api_router.include_router(benefits.router)
