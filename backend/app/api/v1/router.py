from fastapi import APIRouter

from app.api.v1.routes import admin, auth, benefits, chat, claims, documents, health, requirements, support_cases

api_router = APIRouter()
api_router.include_router(admin.router)
api_router.include_router(documents.router)
api_router.include_router(support_cases.router)
api_router.include_router(requirements.router)
api_router.include_router(chat.router)
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(claims.router)
api_router.include_router(benefits.router)
