#!/usr/bin/env python3
"""Download the official HOTOSM DINOv3 building-segmentation ONNX artifact."""
from pathlib import Path
from urllib.request import Request, urlopen

URL = "https://huggingface.co/hotosm/dinov3s-buildings/resolve/main/model.onnx"
ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "backend" / "models" / "hotosm_dinov3s_buildings.onnx"

def main():
    DEST.parent.mkdir(parents=True, exist_ok=True)
    if DEST.exists() and DEST.stat().st_size >= 128:
        print(f"HOTOSM model already present: {DEST} ({DEST.stat().st_size} bytes)")
        return
    print("Downloading HOTOSM DINOv3 building model (~220 MB)...")
    request = Request(URL, headers={"User-Agent": "SahiNaksha/1.0"})
    with urlopen(request, timeout=120) as response, DEST.with_suffix(".onnx.part").open("wb") as out:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    part = DEST.with_suffix(".onnx.part")
    if part.stat().st_size < 128:
        part.unlink(missing_ok=True)
        raise RuntimeError("Downloaded model is unexpectedly small.")
    part.replace(DEST)
    print(f"Saved: {DEST} ({DEST.stat().st_size} bytes)")

if __name__ == "__main__":
    main()
