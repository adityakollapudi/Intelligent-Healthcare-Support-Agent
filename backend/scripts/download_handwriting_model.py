"""Downloads the handwriting model (about 600 MB) at a pinned revision. Run once:
python -m scripts.download_handwriting_model

An ONNX conversion of microsoft/trocr-base-handwritten (MIT). The files stay in backend/.models."""

from __future__ import annotations

from pathlib import Path

from huggingface_hub import hf_hub_download

REPOSITORY = "Xenova/trocr-base-handwritten"
REVISION = "e301d1c4c4d4ece88f164518eb7aee07062eaca2"
FILES = ("onnx/encoder_model.onnx", "onnx/decoder_model_merged_quantized.onnx", "tokenizer.json")
TARGET = Path(__file__).resolve().parents[1] / ".models" / "trocr-base-handwritten"


def main() -> None:
    for name in FILES:
        print(hf_hub_download(REPOSITORY, name, revision=REVISION, local_dir=TARGET))


if __name__ == "__main__":
    main()
