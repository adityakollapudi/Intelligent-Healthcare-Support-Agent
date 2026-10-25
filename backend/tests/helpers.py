from sqlalchemy import select

from app.db.session import get_session_factory
from app.models import AuditLog


def latest_audit(action: str | None = None, resource_ref: str | None = None) -> AuditLog | None:
    with get_session_factory()() as session:
        query = select(AuditLog).order_by(AuditLog.id.desc())
        if action:
            query = query.where(AuditLog.action == action)
        if resource_ref:
            query = query.where(AuditLog.resource_ref == resource_ref)
        return session.scalars(query.limit(1)).first()


def assert_error(response, status: int, code: str) -> dict:
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == code
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]
    return body["error"]
