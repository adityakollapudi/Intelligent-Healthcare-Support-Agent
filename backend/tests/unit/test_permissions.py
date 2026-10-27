from app.authz.permissions import ROLE_PERMISSIONS, Permission, permissions_for
from app.models.enums import Role


def test_catalogue_matches_phase1_doc03():
    assert len(Permission) == 27


def test_every_role_has_a_permission_set():
    assert set(ROLE_PERMISSIONS) == set(Role)


def test_only_members_read_own_claims():
    holders = {role for role, perms in ROLE_PERMISSIONS.items() if Permission.CLAIMS_READ_OWN in perms}
    assert holders == {Role.MEMBER}


def test_providers_have_no_member_record_access():
    provider = ROLE_PERMISSIONS[Role.PROVIDER]
    assert Permission.CLAIMS_READ_OWN not in provider
    assert Permission.CLAIMS_READ_CASE_LINKED not in provider
    assert Permission.BENEFITS_READ_OWN not in provider


def test_admin_has_no_content_permissions():
    admin = ROLE_PERMISSIONS[Role.ADMIN]
    for perm in (Permission.CLAIMS_READ_OWN, Permission.CLAIMS_READ_CASE_LINKED,
                 Permission.DOCUMENTS_READ_OWN, Permission.DOCUMENTS_READ_CASE_LINKED):
        assert perm not in admin


def test_audit_read_is_admin_only():
    assert {r for r, p in ROLE_PERMISSIONS.items() if Permission.AUDIT_READ in p} == {Role.ADMIN}


def test_unknown_role_gets_nothing():
    assert permissions_for("SUPERUSER") == frozenset()

def test_every_role_can_rate_answers():
    # doc 03 §2 matrix row `feedback:create`: ✔ for all four roles.
    assert all(Permission.FEEDBACK_CREATE in perms for perms in ROLE_PERMISSIONS.values())
