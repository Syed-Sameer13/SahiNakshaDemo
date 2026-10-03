#!/usr/bin/env python3
"""Download the official Meta SAM ViT-B checkpoint used by SahiNaksha."""
from pathlib import Path
from urllib.request import urlretrieve

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "models" / "sam_vit_b_01ec64.pth"
URL = "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

if OUTPUT.exists() and OUTPUT.stat().st_size > 300_000_000:
    print(f"SAM checkpoint already exists: {OUTPUT}")
else:
    print(f"Downloading SAM ViT-B checkpoint to {OUTPUT} ...")
    urlretrieve(URL, OUTPUT)
    print(f"Downloaded {OUTPUT.stat().st_size / (1024**2):.1f} MB")
