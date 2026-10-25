"""Synthetic demonstration records (doc 05 §8). Every name, number and amount is fictional.

Stable natural keys (org name, email, member_number, plan_code, claim_number, benefit key) make the
seed idempotent. Claim number SYN-CLM-2026-999999 is intentionally absent for negative tests.
"""

from datetime import UTC, date, datetime

UTC = UTC

PROVIDER_ORG = "Maplestone Family Clinic (fictional)"
SUPPORT_ORG = "IHSA Synthetic Support Center"

ORGANIZATIONS = [
    {"name": PROVIDER_ORG, "org_type": "PROVIDER_PRACTICE"},
    {"name": SUPPORT_ORG, "org_type": "SUPPORT_CENTER"},
]

PLANS = [
    {
        "plan_code": "SYN-PLAN-GOLD-01",
        "plan_name": "Synthetic Gold Plan",
        "plan_year": 2026,
        "effective_start": date(2026, 1, 1),
        "effective_end": date(2026, 12, 31),
        "summary": "Fictional plan with lower cost sharing, used for demonstrations only.",
        "is_active": True,
    },
    {
        "plan_code": "SYN-PLAN-BRONZE-01",
        "plan_name": "Synthetic Bronze Plan",
        "plan_year": 2026,
        "effective_start": date(2026, 1, 1),
        "effective_end": date(2026, 12, 31),
        "summary": "Fictional plan with higher cost sharing, used for demonstrations only.",
        "is_active": True,
    },
    {
        "plan_code": "SYN-PLAN-SILVER-25",
        "plan_name": "Synthetic Silver Plan (2025, retired)",
        "plan_year": 2025,
        "effective_start": date(2025, 1, 1),
        "effective_end": date(2025, 12, 31),
        "summary": "Inactive fictional plan kept to test active-plan filtering.",
        "is_active": False,
    },
]


def _benefit(category, service, in_net, out_net, prior_auth=False, visit_limit=None, limitations=None):
    return {
        "benefit_category": category,
        "service_name": service,
        "in_network_cost_share": in_net,
        "out_of_network_cost_share": out_net,
        "prior_auth_required": prior_auth,
        "visit_limit": visit_limit,
        "limitations": limitations,
    }


PLAN_BENEFITS = {
    "SYN-PLAN-GOLD-01": [
        _benefit("PRIMARY_CARE", "Office visit", "$20 copay", "40% coinsurance"),
        _benefit("SPECIALIST", "Specialist office visit", "$40 copay", "40% coinsurance"),
        _benefit("IMAGING", "MRI (outpatient)", "20% coinsurance", "40% coinsurance", True,
                 limitations="Prior authorization listed in the synthetic imaging guide."),
        _benefit("IMAGING", "X-ray", "$0 copay", "30% coinsurance"),
        _benefit("PHYSICAL_THERAPY", "Outpatient physical therapy", "$25 copay", "40% coinsurance", True,
                 "20 visits per plan year", "Visits beyond the limit need prior authorization (synthetic rule)."),
        _benefit("EMERGENCY", "Emergency room visit", "$150 copay", "$150 copay"),
        _benefit("PREVENTIVE", "Annual preventive visit", "$0 copay", "Not covered"),
    ],
    "SYN-PLAN-BRONZE-01": [
        _benefit("PRIMARY_CARE", "Office visit", "$45 copay", "50% coinsurance"),
        _benefit("SPECIALIST", "Specialist office visit", "$80 copay", "50% coinsurance"),
        _benefit("IMAGING", "MRI (outpatient)", "40% coinsurance", "Not covered", True,
                 limitations="Prior authorization listed in the synthetic imaging guide."),
        _benefit("PHYSICAL_THERAPY", "Outpatient physical therapy", "$50 copay", "Not covered", True,
                 "12 visits per plan year"),
        _benefit("EMERGENCY", "Emergency room visit", "$350 copay", "$350 copay"),
        _benefit("PREVENTIVE", "Annual preventive visit", "$0 copay", "Not covered"),
    ],
    "SYN-PLAN-SILVER-25": [
        _benefit("PRIMARY_CARE", "Office visit", "$30 copay", "45% coinsurance"),
    ],
}

# Users: all emails use the reserved example.test domain; passwords come from SEED_USER_PASSWORD.
USERS = [
    {"email": "priya.member@example.test", "display_name": "Priya Synthetic", "role": "MEMBER", "org": None},
    {"email": "lee.member@example.test", "display_name": "Lee Sample", "role": "MEMBER", "org": None},
    {"email": "robin.member@example.test", "display_name": "Robin Testcase", "role": "MEMBER", "org": None},
    {"email": "jordan.provider@example.test", "display_name": "Jordan Example", "role": "PROVIDER", "org": PROVIDER_ORG},
    {"email": "casey.provider@example.test", "display_name": "Casey Placeholder", "role": "PROVIDER", "org": PROVIDER_ORG},
    {"email": "sam.agent@example.test", "display_name": "Sam Reviewer", "role": "SUPPORT_AGENT", "org": SUPPORT_ORG},
    {"email": "taylor.agent@example.test", "display_name": "Taylor Queue", "role": "SUPPORT_AGENT", "org": SUPPORT_ORG},
    {"email": "alex.admin@example.test", "display_name": "Alex Operator", "role": "ADMIN", "org": None},
]

MEMBERS = [
    {"member_number": "SYN-M-000001", "email": "priya.member@example.test", "plan_code": "SYN-PLAN-GOLD-01",
     "coverage_start": date(2026, 1, 1), "coverage_end": None},
    {"member_number": "SYN-M-000002", "email": "lee.member@example.test", "plan_code": "SYN-PLAN-BRONZE-01",
     "coverage_start": date(2026, 1, 1), "coverage_end": None},
    {"member_number": "SYN-M-000003", "email": "robin.member@example.test", "plan_code": "SYN-PLAN-GOLD-01",
     "coverage_start": date(2026, 3, 1), "coverage_end": None},
]


def _claim(number, member, service, submitted, status, reason, description, amount, changed):
    return {
        "claim_number": number,
        "member_number": member,
        "service_date": service,
        "submission_date": submitted,
        "status": status,
        "status_reason_code": reason,
        "status_description": description,
        "billed_amount": amount,
        "last_status_change_at": changed,
    }


CLAIMS = [
    # Member SYN-M-000001 — one claim in every status.
    _claim("SYN-CLM-2026-000101", "SYN-M-000001", date(2026, 8, 14), date(2026, 8, 20), "PENDING_INFORMATION",
           "PI-01", "Additional itemized bill requested (synthetic).", "412.50",
           datetime(2026, 9, 2, 10, 15, tzinfo=UTC)),
    _claim("SYN-CLM-2026-000102", "SYN-M-000001", date(2026, 9, 3), date(2026, 9, 5), "RECEIVED",
           None, "Claim received and awaiting processing (synthetic).", "95.00",
           datetime(2026, 9, 5, 14, 0, tzinfo=UTC)),
    _claim("SYN-CLM-2026-000103", "SYN-M-000001", date(2026, 7, 21), date(2026, 7, 24), "UNDER_PROCESSING",
           None, "Claim is being processed (synthetic).", "230.00",
           datetime(2026, 8, 1, 9, 30, tzinfo=UTC)),
    _claim("SYN-CLM-2026-000104", "SYN-M-000001", date(2026, 5, 9), date(2026, 5, 12), "PROCESSED_PAID",
           "PD-00", "Processed; payment issued to provider (synthetic).", "140.00",
           datetime(2026, 5, 30, 16, 45, tzinfo=UTC)),
    _claim("SYN-CLM-2026-000105", "SYN-M-000001", date(2026, 4, 2), date(2026, 4, 10), "PROCESSED_DENIED",
           "DN-04", "Service not listed in synthetic plan benefits.", "610.00",
           datetime(2026, 4, 28, 11, 5, tzinfo=UTC)),
    # Member SYN-M-000002 — used for cross-member access tests.
    _claim("SYN-CLM-2026-000201", "SYN-M-000002", date(2026, 8, 30), date(2026, 9, 1), "UNDER_PROCESSING",
           None, "Claim is being processed (synthetic).", "180.00",
           datetime(2026, 9, 10, 8, 0, tzinfo=UTC)),
    _claim("SYN-CLM-2026-000202", "SYN-M-000002", date(2026, 6, 15), date(2026, 6, 18), "PROCESSED_PAID",
           "PD-00", "Processed; payment issued to provider (synthetic).", "75.00",
           datetime(2026, 7, 2, 13, 20, tzinfo=UTC)),
    _claim("SYN-CLM-2026-000203", "SYN-M-000002", date(2026, 10, 1), date(2026, 10, 3), "RECEIVED",
           None, "Claim received and awaiting processing (synthetic).", "52.00",
           datetime(2026, 10, 3, 17, 10, tzinfo=UTC)),
    # Member SYN-M-000003.
    _claim("SYN-CLM-2026-000301", "SYN-M-000003", date(2026, 9, 12), date(2026, 9, 15), "PENDING_INFORMATION",
           "PI-02", "Referral documentation requested (synthetic).", "320.00",
           datetime(2026, 9, 25, 12, 0, tzinfo=UTC)),
    _claim("SYN-CLM-2026-000302", "SYN-M-000003", date(2026, 3, 18), date(2026, 3, 20), "PROCESSED_PAID",
           "PD-00", "Processed; payment issued to provider (synthetic).", "110.00",
           datetime(2026, 4, 6, 10, 40, tzinfo=UTC)),
]

NONEXISTENT_CLAIM_NUMBER = "SYN-CLM-2026-999999"


def _req(code, description, rule_type, params, phrase, mandatory=True):
    return {"requirement_code": code, "description": description, "rule_type": rule_type, "rule_params": params,
            "source_phrase": phrase, "is_mandatory": mandatory}


# Fictional documentation-requirement sets (doc 07 §6.2). `source_phrase` must appear verbatim in the
# ACTIVE version of `source_document_key`; the requirements service verifies it at query time.
PA_REQUIREMENT_SETS = [
    {
        "procedure_code": "SYN-PROC-MRI-LUMBAR",
        "display_name": "Lumbar spine MRI (fictional requirement set)",
        "aliases": ["lumbar mri", "lumbar spine mri", "back mri", "lumbar scan", "mri of the lower back", "spine mri"],
        "version": "2.0",
        "source_document_key": "pa-imaging-guide",
        "requirements": [
            _req("REQ-MRI-01", "Requested service date present", "FIELD_PRESENT",
                 {"field": "requested_service_date"}, "The requested service date."),
            _req("REQ-MRI-02", "Ordering provider identifier present in synthetic format", "FIELD_PATTERN",
                 {"field": "ordering_provider_npi", "regex": "^\\d{10}$"}, "ordering provider's 10-digit identifier"),
            _req("REQ-MRI-03", "Conservative therapy duration is documented", "FIELD_PRESENT",
                 {"field": "conservative_therapy_duration"}, "Documentation of the duration of conservative therapy"),
            _req("REQ-MRI-04", "Member number present in synthetic format", "FIELD_PATTERN",
                 {"field": "member_number", "regex": "^SYN-M-\\d{6}$"}, "The member number in the format SYN-M-000000"),
            _req("REQ-MRI-05", "Referral letter included", "DOCUMENT_TYPE_PRESENT",
                 {"document_type": "REFERRAL_LETTER"}, "A referral letter from the referring provider"),
            _req("REQ-MRI-06", "Supporting rationale reviewed by authorized staff", "MANUAL_ONLY", {},
                 "A supporting rationale, which an authorized staff member reviews manually"),
        ],
    },
    {
        "procedure_code": "SYN-PROC-PT-EXTENDED",
        "display_name": "Extended physical therapy (fictional requirement set)",
        "aliases": ["extended physical therapy", "physical therapy extension", "more physical therapy visits",
                    "additional physical therapy", "pt extension", "extra pt visits", "physical therapy beyond the limit"],
        "version": "1.0",
        "source_document_key": "pa-physical-therapy-guide",
        "requirements": [
            _req("REQ-PT-01", "Member number present", "FIELD_PATTERN",
                 {"field": "member_number", "regex": "^SYN-M-\\d{6}$"}, "The member number."),
            _req("REQ-PT-02", "Referral dated within 30 days before request", "DATE_WITHIN_DAYS",
                 {"field": "referral_date", "reference_field": "request_date", "max_days_before": 30},
                 "A referral dated within 30 days before the request date"),
            _req("REQ-PT-03", "Clinical note summary included", "DOCUMENT_TYPE_PRESENT",
                 {"document_type": "CLINICAL_NOTE_SUMMARY"}, "A clinical note summary describing progress so far"),
            _req("REQ-PT-04", "Visit history reviewed by authorized staff", "MANUAL_ONLY", {},
                 "The visit history for the current plan year"),
        ],
    },
]
