"""Regenerates data/knowledge/provider-admin-faq.pdf, the corpus's PDF sample (two pages, so page
citations can be tested). Run: python -m scripts.build_sample_pdf"""

from pathlib import Path

import pymupdf

PAGES = [
    (
        "Synthetic Provider Administrative FAQ",
        [
            "SYNTHETIC DEMONSTRATION DOCUMENT. Fictional provider guidance for the IHSA prototype.",
            "Submitting prior authorization requests",
            "Provider staff submit prior authorization requests through the synthetic provider portal. "
            "Each request must list the procedure code, such as SYN-PROC-MRI-LUMBAR, and attach the "
            "documents listed in the matching prior authorization guide.",
            "Checking request status",
            "The provider portal shows whether a request is Submitted, In review or Decided. The IHSA "
            "assistant does not report authorization decisions.",
        ],
    ),
    (
        "Provider claim submission",
        [
            "Claim submission deadline",
            "In-network providers must submit claims within 90 days of the service date. Claims received "
            "after 90 days are denied as late unless the provider shows good cause.",
            "Corrected claims",
            "A corrected claim must reference the original claim number and is due within 60 days of the "
            "original claim's processing date.",
        ],
    ),
]


def build(path: Path) -> None:
    doc = pymupdf.open()
    for title, paragraphs in PAGES:
        page = doc.new_page()
        text = title + "\n\n" + "\n\n".join(paragraphs)
        page.insert_textbox(pymupdf.Rect(56, 56, 540, 790), text, fontsize=11, fontname="helv")
    doc.set_metadata({"title": "Synthetic Provider Administrative FAQ", "subject": "synthetic"})
    doc.save(path)


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "data" / "knowledge" / "provider-admin-faq.pdf"
    build(out)
    print(f"wrote {out.name}")
