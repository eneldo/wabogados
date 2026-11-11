from fastapi import APIRouter

from app.api.v1.actions import router as actions_router
from app.api.v1.admin import router as admin_router
from app.api.v1.admin_metrics import router as admin_metrics_router
from app.api.v1.admin_settings import router as admin_settings_router
from app.api.v1.analyses import router as analyses_router
from app.api.v1.auth import router as auth_router
from app.api.v1.billing import router as billing_router
from app.api.v1.calendar import router as calendar_router
from app.api.v1.case_milestones import router as case_milestones_router
from app.api.v1.cases import router as cases_router
from app.api.v1.client_requests import router as client_requests_router
from app.api.v1.clients import router as clients_router
from app.api.v1.consultations import router as consultations_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.documents import router as documents_router
from app.api.v1.evidences import router as evidences_router
from app.api.v1.health import router as health_router
from app.api.v1.lawyers import router as lawyers_router
from app.api.v1.legal_ai import router as legal_ai_router
from app.api.v1.media import router as media_router
from app.api.v1.messages import router as messages_router
from app.api.v1.public import router as public_router
from app.api.v1.website_analytics import router as website_analytics_router

router = APIRouter(prefix="/api/v1")
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(admin_router)
router.include_router(analyses_router)
router.include_router(clients_router)
router.include_router(lawyers_router)
router.include_router(cases_router)
router.include_router(actions_router)
router.include_router(calendar_router)
router.include_router(documents_router)
router.include_router(evidences_router)
router.include_router(messages_router)
router.include_router(client_requests_router)
router.include_router(case_milestones_router)
router.include_router(dashboard_router)
router.include_router(admin_settings_router)
router.include_router(admin_metrics_router)
router.include_router(consultations_router)
router.include_router(media_router)
router.include_router(billing_router)
router.include_router(legal_ai_router)
router.include_router(public_router)
router.include_router(website_analytics_router)
