"""Service-level unit tests that need no database."""

from datetime import date
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppError
from app.services import claim_service
from app.services.audit_service import AuditService


def test_cursor_round_trip():
    claim = SimpleNamespace(submission_date=date(2026, 8, 20), claim_number="SYN-CLM-2026-000101")
    cursor = claim_service._encode_cursor(claim)
    assert claim_service._decode_cursor(cursor) == (date(2026, 8, 20), "SYN-CLM-2026-000101")


@pytest.mark.parametrize("bad", ["!!!", "bm90LWEtY3Vyc29y", "MjAyNi0xMy00MHxYWVo"])
def test_invalid_cursor_is_a_validation_error(bad):
    with pytest.raises(AppError) as exc:
        claim_service._decode_cursor(bad)
    assert exc.value.status_code == 422


def test_audit_rejects_non_allowlisted_metadata_before_touching_the_database():
    with pytest.raises(ValueError, match="not allowlisted"):
        AuditService().record("CLAIM_LOOKUP", "SUCCESS", metadata={"message_text": "free text"})
