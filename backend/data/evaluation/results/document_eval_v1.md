# Document AI evaluation (synthetic corpus v1.0)

- Run: 2026-10-25T17:54:45+00:00 · documents: 13 · scenarios: 10
- OCR engine: `tesseract` · available: **False**

## Extraction (documents scored: 10)

| Metric | Result |
|---|---|
| Document type accuracy | 100.0% (10/10) |
| Field validation-status accuracy | 100.0% (65/65) |
| Field exact match (status + normalized value) | 100.0% (65/65) |
| VALID-field precision | 100.0% (53/53) |
| VALID-field recall | 100.0% (53/53) |
| Missing-field (ABSENT) detection precision | 100.0% (10/10) |
| Missing-field (ABSENT) detection recall | 100.0% (10/10) |

## Readiness checklist

| Metric | Result |
|---|---|
| Checklist item status accuracy | 100.0% (48/48) |
| Overall readiness status accuracy | 100.0% (9/9) |
| Expected SATISFIED classified correctly | 100.0% (25/25) |
| Expected MISSING classified correctly | 100.0% (9/9) |
| Expected UNREADABLE classified correctly | 100.0% (1/1) |
| Expected NEEDS_MANUAL_REVIEW classified correctly | 100.0% (13/13) |

## Not scored (need OCR, engine unavailable)

- `pa_request_mri_mixed.pdf`: observed type PA_REQUEST_FORM, field statuses ['ILLEGIBLE', 'VALID']
- `pa_request_mri_scanned.pdf`: observed type UNRECOGNIZED, field statuses ['(none)']
- `pa_request_mri_scanned.png`: observed type UNRECOGNIZED, field statuses ['(none)']

## Processing time (local CPU)

| Document | Bytes | Pages | ms |
|---|---|---|---|
| pa_request_mri_complete.pdf | 3255 | 1 | 62.1 |
| referral_letter_mri.pdf | 1889 | 1 | 9.4 |
| pa_request_mri_incomplete.pdf | 2819 | 1 | 8.9 |
| pa_request_mri_conflict.pdf | 4025 | 2 | 19.5 |
| pa_request_mri_scanned.png | 116185 | 1 | 101.4 |
| pa_request_mri_scanned.pdf | 113615 | 1 | 848.3 |
| pa_request_mri_mixed.pdf | 43725 | 2 | 708.3 |
| pt_request_form.pdf | 1919 | 1 | 8.3 |
| pt_referral_letter.pdf | 1899 | 1 | 8.2 |
| pt_referral_letter_late.pdf | 1902 | 1 | 9.1 |
| clinical_note_summary.pdf | 1678 | 1 | 10.5 |
| unrecognized_letter.pdf | 1320 | 1 | 8.8 |
| pa_request_mri_injection.pdf | 3318 | 1 | 11.4 |

## Mismatches

| Where | Expected | Actual |
|---|---|---|
