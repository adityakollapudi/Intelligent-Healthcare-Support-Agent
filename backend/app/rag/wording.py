"""Customers' everyday words, swapped for the words the plan documents use before searching them.

This changes only what is searched for. Answers are still quoted from the documents, and the customer's
own words are what gets stored and shown. A phrase belongs here only if it means the same thing."""

from __future__ import annotations

import re

_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern, re.I), plain) for pattern, plain in (
        (r"\bhow much do i (owe|pay) before (the|my) plan (starts?|begins?) (paying|to pay)\b",
         "what is my deductible"),
        (r"\b(is there|what is) (a|the) (cap|limit|maximum) on\b", "how many"),
        (r"\b(pt|physio|physiotherapy)\b", "physical therapy"),
        (r"\bsessions?\b", "visits"),
        (r"\bevery year\b|\ba year\b|\bper year\b", "covered per plan year"),
        (r"\b(rejected|turned down|refused)\b", "denied"),
        (r"\b(dispute|challenge|fight)\b", "appeal"),
        (r"\btime limit\b", "deadline"),
        (r"\b(says? )?(they )?needs? more info(rmation)?\b", "pending information"),
        (r"\b(lost|replace|another|new)\b.{0,20}\b(insurance|id|member) card\b",
         "request a replacement printed member ID card"),
        (r"(?<!member )\b(insurance|id) card\b", "member ID card"),
        (r"\bmoney back\b|\bpaid? back\b|\brefund\b", "reimbursement claim"),
        (r"\b(paid|pay) (the|my) doctor myself\b", "paid a provider directly"),
        (r"\bpaperwork\b", "documents"),
        (r"\b(proves?|proof)\b.{0,12}\bpaid\b", "itemized bill or receipt for a reimbursement claim"),
        (r"\b(main|family|regular|usual) doctor\b", "primary care provider"),
        (r"\b(how (do|can) i )?(find|choose|pick|select|change)( a| my)? (primary care provider|doctor)\b",
         "a primary care provider can be selected or changed in the member portal"),
        (r"\b(how (do|can) i )?(file|submit|send in|make) a claim\b",
         "when a member paid a provider directly and asks for reimbursement, the claim must include"),
        (r"\b(ticket|complaint)\b", "support case"),
        (r"\b(phone number|contact number|call)\b.{0,20}\bsupport\b", "member support line hours"),
        (r"\bcontact support\b", "member support line hours"),
        (r"\bpre-?auth\w*|\bprior auth\b", "prior authorization"),
        (r"\bclinics?\b", "providers"),
        (r"\bback (mri|scan)\b", "lumbar spine MRI"),
    )
)


def plain_words(question: str) -> str:
    for pattern, plain in _REPLACEMENTS:
        question = pattern.sub(plain, question)
    return question
