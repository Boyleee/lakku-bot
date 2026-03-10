"""Validate that runtime Python dependencies are importable inside the image."""

from __future__ import annotations

import importlib
import sys

MODULES = [
    "torch",
    "torchvision",
    "numpy",
    "PIL",
    "diffusers",
    "transformers",
    "accelerate",
    "peft",
    "safetensors",
    "sentencepiece",
    "ftfy",
    "imageio",
    "imageio_ffmpeg",
    "cv2",
    "torchao",
    "huggingface_hub",
    "spaces",
    "spaces.zero.torch.aoti",
    "runpod",
    "pydantic",
    "tqdm",
]


def main() -> int:
    missing: list[tuple[str, str]] = []
    for name in MODULES:
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001
            missing.append((name, str(exc)))

    if missing:
        print("Missing/failed imports after dependency install:")
        for name, err in missing:
            print(f" - {name}: {err}")
        return 1

    print("Dependency smoke check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
