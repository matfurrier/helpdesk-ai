from fastapi import APIRouter

from app.api.v1.endpoints import admin, attachments, auth, chat, csat, health, tickets

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(auth.router)
router.include_router(chat.router)
router.include_router(tickets.router)
router.include_router(attachments.router)
router.include_router(csat.router)
router.include_router(admin.router)
router.include_router(admin.kb_router)
