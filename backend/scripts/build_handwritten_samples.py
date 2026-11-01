"""Builds fictional handwritten-style notes for testing handwriting OCR, with the expected text.

These use handwriting fonts plus slant and noise. They are NOT real doctors' handwriting, so results
on them only show that the pipeline works; they say nothing about accuracy on real prescriptions."""

from __future__ import annotations

import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "samples" / "documents" / "handwritten"
FONTS = {"ink": "Inkfree.ttf", "script": "segoesc.ttf", "print": "segoepr.ttf", "bradley": "BRADHITC.TTF"}
NOTES = {
    "knee_note": [
        "Patient: Aarav Sharma",
        "Date of service 03/14/2026",
        "Right knee pain for six weeks",
        "Physical therapy for four weeks",
        "Request MRI of the right knee",
    ],
    "prescription": [
        "Patient: Meera Iyer",
        "Date 02/20/2026",
        "Atorvastatin 20 mg once daily",
        "Metformin 500 mg twice daily",
        "Follow up in three months",
    ],
}


def _render(lines: list[str], font_file: str, seed: int) -> Image.Image:
    rng = random.Random(seed)  # noqa: S311 - repeatable layout, not security
    font = ImageFont.truetype(f"C:/Windows/Fonts/{font_file}", 44)
    page = Image.new("RGB", (1100, 110 * len(lines) + 80), (252, 250, 244))
    draw = ImageDraw.Draw(page)
    for index, line in enumerate(lines):
        x, y = 50 + rng.randint(-12, 24), 45 + index * 110 + rng.randint(-8, 8)
        draw.text((x, y), line, font=font, fill=(25, 35, 90))
    page = page.rotate(rng.uniform(-1.2, 1.2), resample=Image.Resampling.BICUBIC, fillcolor=(252, 250, 244))
    return page.filter(ImageFilter.GaussianBlur(0.5))


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    expected = {}
    for seed, (note, lines) in enumerate(NOTES.items()):
        for offset, (label, font_file) in enumerate(FONTS.items()):
            name = f"{note}_{label}.png"
            _render(lines, font_file, seed * 10 + offset).save(OUTPUT / name)
            expected[name] = lines
    (OUTPUT / "expected.json").write_text(json.dumps(expected, indent=2), encoding="utf-8")
    print(f"{len(expected)} samples in {OUTPUT}")


if __name__ == "__main__":
    main()
