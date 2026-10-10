from fastapi import APIRouter

from backend.api.routes import (
    applications,
    ats,
    designer_audits,
    pvn_auth,
    auth,
    candidates,
    categories,
    domains,
    health,
    invitations,
    profiles,
    regular_tasks,
    test_sessions,
    vacancies,
)

router = APIRouter()

router.include_router(health.router, tags=["health"])
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(pvn_auth.router, prefix="/auth", tags=["auth"])
router.include_router(profiles.router, tags=["profiles"])
router.include_router(categories.router, prefix="/employer", tags=["employer"])
router.include_router(domains.router, prefix="/employer", tags=["employer"])
router.include_router(candidates.router, prefix="/employer", tags=["employer"])
router.include_router(invitations.router, tags=["invitations"])
router.include_router(test_sessions.router, tags=["testing"])
router.include_router(vacancies.router, tags=["vacancies"])
router.include_router(applications.router, tags=["applications"])
router.include_router(ats.router, tags=["ats"])
router.include_router(designer_audits.router, tags=["designer-audits"])
router.include_router(regular_tasks.router, tags=["regular-tasks"])
