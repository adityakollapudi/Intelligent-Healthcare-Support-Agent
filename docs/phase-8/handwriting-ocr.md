# Handwriting OCR

Customers can upload a photo or scan of a handwritten note. The system reads it on this machine, warns that it may be misread, and marks unclear words. **Accuracy on real doctors' handwriting has not been measured.**

## What was chosen

| Part | Project | Licence | Job |
|---|---|---|---|
| Line finding and printed text | [RapidOCR](https://github.com/RapidAI/RapidOCR) 3.10.0 | Apache-2.0 | Finds each line and reads it. Models ship inside the package. |
| Handwriting | [TrOCR base handwritten](https://huggingface.co/microsoft/trocr-base-handwritten) | MIT | Reads any line RapidOCR scored below 0.97. If that's at least a quarter of the page's lines, it reads the whole page, because RapidOCR can be confident and wrong on handwriting. |

The ONNX files come from [Xenova/trocr-base-handwritten](https://huggingface.co/Xenova/trocr-base-handwritten), pinned to revision `e301d1c`. That conversion has no licence tag of its own; the upstream model is MIT. Replace it with your own export before any use beyond this prototype.

## Options rejected

| Option | Reason |
|---|---|
| Prescription projects on GitHub, such as [Medical-Prescription-OCR](https://github.com/JonSnow1807/Medical-Prescription-OCR) | Small student or research projects. That one is trained on generated images and its README says not to use it on real prescriptions. Others publish no weights, licence or results. |
| [Surya](https://github.com/datalab-to/surya) | Weights are restricted for larger commercial use, and CPU use needs a separate llama.cpp backend. |
| Tesseract | Weak on handwriting and not installed here. Still selectable with `OCR_ENGINE=tesseract`. |
| GPU models (olmOCR, GOT-OCR 2.0) | This laptop has no suitable GPU. |
| Hosted OCR services | Would send patient documents outside the system, which needs an approved privacy and security design. |

## Measured results

Measured on 2026-11-01 on an Intel Core i5-1335U with no GPU. "Error" is mean character error rate.

| Test | Error | Time |
|---|---|---|
| 30 real handwritten English lines (IAM test set), full model, 1.3 GB | 6.0% | 3.3 s per line |
| Same lines, full encoder with quantized decoder, 594 MB (**used**) | 6.1% | not separately timed |
| Same lines, fully quantized model, 338 MB | 41% | 2.9 s per line |
| Same lines, RapidOCR alone | 55% | not timed |
| One page stacked from 8 of those lines, full model | 4.5% | 12.5 s |
| 8 fictional notes in handwriting fonts, RapidOCR only | Matching ratio 0.98 to 1.00 | about 2 s per page |

The stacked-page row used the full decoder and the earlier line-by-line routing, so its error rate wasn't re-measured for the final setup. An end-to-end run through the API with the final setup completed with mean confidence 93.75, and it corrected misreadings such as "thinu" for "think".

### What these numbers do not show

- IAM is neat English handwriting. Doctors' handwriting is much harder, with abbreviations and medicine names the model wasn't trained on. Expect far worse results.
- 30 lines is a small sample, and the 8 font samples are not real handwriting.
- No real prescriptions were tested. A proper test needs consented or synthetic handwritten prescriptions with checked transcriptions, and a clinician's review.

## Checking what was read

After analysis, the Documents screen shows "What we read from your document", with unclear words highlighted, so the customer can compare it with the original. It uses `GET /documents/{id}/text`, which follows the same access rule as `GET /documents/{id}` and is audited as `DOCUMENT_TEXT_VIEWED`. The text isn't stored, so scanned pages are read again each time the panel opens.

On a fictional handwritten prescription, the body came out well, including the symptoms, Naproxen 500 mg and the MRI order. It still misread short labels (C/C as "clc."), the procedure code and the registration number, which is why the customer needs to see the text.

## Safety behaviour

- A word's confidence is its least likely token. Words below `OCR_MIN_WORD_CONFIDENCE` are marked `[?]` in chat answers and treated as illegible by field extraction.
- Every page with handwriting gets a warning, `OCR_HANDWRITING_NEEDS_CHECK` or `OCR_LOW_CONFIDENCE`, even when confidence is high, because a confident reading can still be the wrong word.
- Chat answers tell the customer to check medicine names, doses and dates with a doctor or pharmacist. The Telugu and Hindi wording needs human review.
- Extracted text stays in memory only, as for other documents.
- This is not a clinical tool. It must not be used for dispensing or treatment decisions.

## Limits

- Chat reads the file again for each question, which took about 22 seconds on the 8-line test page.
- If one copy of a word is unclear, every copy on that page is marked, so common words like "a" can be marked needlessly.
- English only. Telugu and Hindi handwriting won't be read.
- Long pages can reach `OCR_PAGE_TIMEOUT_SECONDS` (90) on a CPU.
- The Docker image still uses Tesseract, because the model isn't included in the image.

## Setup

Run once from `backend/`. It downloads about 600 MB into `.models/`, which git ignores.

```bash
python -m scripts.download_handwriting_model
```

Set `OCR_ENGINE=local` in `.env`. Without the model, scanned pages are reported as unreadable and nothing is guessed.

Rebuild the sample notes on Windows with `python -m scripts.build_handwritten_samples`.
