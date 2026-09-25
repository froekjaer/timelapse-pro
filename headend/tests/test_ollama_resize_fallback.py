from __future__ import annotations

import builtins
import logging

import ai.ollama_service as ollama_service


def test_missing_cv2_uses_pillow_without_warning(monkeypatch, caplog):
    service = object.__new__(ollama_service.OllamaVisionService)
    service.max_image_edge = 2048
    service.max_image_bytes = 4_000_000

    original_import = builtins.__import__

    def import_without_cv2(name, *args, **kwargs):
        if name == "cv2":
            raise ImportError("cv2 intentionally unavailable")
        return original_import(name, *args, **kwargs)

    sentinel = b"pil-resized"
    monkeypatch.setattr(builtins, "__import__", import_without_cv2)
    monkeypatch.setattr(
        ollama_service,
        "_resize_with_pil",
        lambda data, max_edge, max_bytes: sentinel,
    )

    with caplog.at_level(logging.WARNING):
        result = service._resize_image(b"jpeg-bytes")

    assert result == sentinel
    assert not any("cv2" in record.getMessage().lower() for record in caplog.records)
