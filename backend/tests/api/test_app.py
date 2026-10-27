import pytest
from fastapi.routing import APIRoute

from app.authz.dependencies import get_current_principal

pytestmark = pytest.mark.postgres

PUBLIC_ROUTES = {("GET", "/api/v1/health"), ("POST", "/api/v1/auth/login")}


def _flatten(dependant):
    for dep in dependant.dependencies:
        yield dep.call
        yield from _flatten(dep)


def _walk(routes, prefix=""):
    # FastAPI >= 0.16x wraps included routers instead of copying their routes onto the app.
    for route in routes:
        if isinstance(route, APIRoute):
            yield prefix + route.path, route
        elif hasattr(route, "original_router"):
            yield from _walk(route.original_router.routes, prefix + route.include_context.prefix)


def _api_routes(app):
    routes = list(_walk(app.routes))
    assert routes, "route discovery found nothing; FastAPI internals changed"
    return routes


def test_all_routes_use_the_versioned_prefix(app):
    assert all(path.startswith("/api/v1/") for path, _ in _api_routes(app))


def test_implemented_routes_match_the_contract(app):
    implemented = {(m, path) for path, r in _api_routes(app) for m in r.methods}
    assert implemented == PUBLIC_ROUTES | {
        ("POST", "/api/v1/auth/logout"), ("GET", "/api/v1/auth/me"), ("GET", "/api/v1/claims"),
        ("GET", "/api/v1/claims/{claim_number}"), ("GET", "/api/v1/benefits/{plan_code}"),
        ("POST", "/api/v1/chat"), ("GET", "/api/v1/chat/sessions"), ("GET", "/api/v1/chat/sessions/{session_id}"),
        ("POST", "/api/v1/support-cases"), ("GET", "/api/v1/support-cases"),
        ("GET", "/api/v1/support-cases/{case_id}"), ("GET", "/api/v1/authorization/requirements/{procedure_code}"),
        ("POST", "/api/v1/documents"), ("GET", "/api/v1/documents"), ("GET", "/api/v1/documents/{document_id}"),
        ("POST", "/api/v1/documents/{document_id}/analyze"), ("GET", "/api/v1/authorization/requirement-sets"),
        ("POST", "/api/v1/authorization/readiness"), ("GET", "/api/v1/authorization/checklists"),
        ("GET", "/api/v1/authorization/checklists/{checklist_id}"),
        ("PATCH", "/api/v1/support-cases/{case_id}"), ("GET", "/api/v1/admin/metrics"),
        ("GET", "/api/v1/admin/audit-events"), ("GET", "/api/v1/admin/knowledge-gaps"),
        ("GET", "/api/v1/admin/support-agents"), ("POST", "/api/v1/chat/messages/{message_id}/feedback"),
    }


def test_every_non_public_route_requires_authentication(app):
    """Route inventory (NFR-001/SEC-02): a new route without an auth dependency fails this test."""
    checked = 0
    for path, route in _api_routes(app):
        for method in route.methods:
            if (method, path) in PUBLIC_ROUTES:
                continue
            assert get_current_principal in set(_flatten(route.dependant)), f"{method} {path} lacks auth"
            checked += 1
    assert checked == 26


def test_openapi_documents_the_response_schemas(client):
    spec = client.get("/api/v1/openapi.json").json()
    for name in ("HealthResponse", "LoginResponse", "MeResponse", "ClaimDetail", "ClaimPage",
                 "BenefitsResponse", "ErrorResponse", "CaseDetail", "CasePage", "RequirementSetResponse"):
        assert name in spec["components"]["schemas"]
    assert "/api/v1/claims/{claim_number}" in spec["paths"]


def test_unknown_route_uses_standard_error_format(client):
    from tests.helpers import assert_error

    assert_error(client.get("/api/v1/does-not-exist"), 404, "RESOURCE_NOT_FOUND")
