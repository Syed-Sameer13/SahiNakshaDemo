"""Run the SahiNaksha AI pipeline against three real representative images.

Usage:
  python scripts/smoke_test_ai.py image1.jpg image2.jpg image3.png

This script does not decide cadastral accuracy. It verifies that each image can
complete the analysis contract and reports the selected model/fallback.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.analysis import analyze_image


def main() -> int:
    paths = sys.argv[1:]
    if len(paths) != 3:
        print("Provide exactly three representative RGB/orthomosaic image paths.")
        return 2

    failed = 0
    for path in paths:
        try:
            result = analyze_image(path)
            ai = result.get("ai_engine", {})
            print(
                f"{path}: status={ai.get('status')} provider={ai.get('model_provider', ai.get('provider'))} "
                f"fallback={ai.get('fallback_used', False)} "
                f"buildings={len(result.get('buildings', {}).get('features', []))} "
                f"parcels={len(result.get('parcels', {}).get('features', []))}"
            )
        except Exception as exc:
            failed += 1
            print(f"{path}: FAILED: {exc}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
