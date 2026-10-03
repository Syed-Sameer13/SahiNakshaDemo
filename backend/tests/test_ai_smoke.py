"""AI pipeline smoke tests.

The test intentionally uses three generated RGB aerial-like scenes so CI/local
smoke testing does not require proprietary imagery or large model checkpoints.
It verifies that the deterministic fallback can always produce a non-crashing,
reviewable result and that the pipeline contract is stable when optional models
are absent.
"""
from pathlib import Path

import cv2
import numpy as np

from app.services.analysis import analyze_image


def _scene(path: Path, variant: int) -> None:
    image = np.full((512, 512, 3), 150, dtype=np.uint8)
    # Vegetation strips.
    cv2.rectangle(image, (0, 0), (512, 70), (55, 115, 55), -1)
    cv2.rectangle(image, (0, 440), (512, 512), (60, 125, 60), -1)
    # Roads.
    cv2.rectangle(image, (220, 0), (292, 512), (105, 105, 105), -1)
    cv2.rectangle(image, (0, 235), (512, 275), (112, 112, 112), -1)
    # Building-like roofs.
    offsets = [(40, 105), (320, 105), (55, 320), (330, 325)]
    if variant == 2:
        offsets = [(25, 110), (300, 90), (80, 315), (350, 310), (170, 145)]
    if variant == 3:
        offsets = [(35, 105), (315, 110), (90, 330)]
    for x, y in offsets:
        cv2.rectangle(image, (x, y), (x + 105, y + 85), (205, 195, 180), -1)
        cv2.rectangle(image, (x + 8, y + 8), (x + 97, y + 77), (170, 160, 150), 2)
    cv2.imwrite(str(path), image)


def test_three_representative_rgb_scenes(tmp_path, monkeypatch):
    monkeypatch.setenv("SAHINAKSHA_DISABLE_AI", "1")
    for index in (1, 2, 3):
        image_path = tmp_path / f"scene-{index}.png"
        _scene(image_path, index)
        result = analyze_image(str(image_path))
        assert result["ai_engine"]["status"] == "FALLBACK_ACTIVE"
        assert result["ai_engine"]["fallback_provider"] == "opencv_deterministic"
        assert "buildings" in result
        assert "parcels" in result
