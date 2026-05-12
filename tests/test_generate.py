"""
Test suite for POST /generate endpoint.
"""

import json
import os
import sys
from io import BytesIO
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient


# Add backend directory to sys.path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend"))

from main import app, banana_service  # noqa: E402


client = TestClient(app)


def _json_upload(payload: Dict[str, Any]):
    return {
        "json": (
            "prompt.json",
            BytesIO(json.dumps(payload, ensure_ascii=False).encode("utf-8")),
            "application/json",
        )
    }


_UNSET = object()


def _mock_generate_factory(
    calls: Dict[str, Any],
    *,
    actual_mode: str = "proxy",
    model_used: str = "mock-proxy-model",
    fallback_used: bool = False,
    fallback_from: str | None = None,
    requested_mode: Any = _UNSET,
):
    def _mock_generate(prompt: str, output_path: str, **kwargs):
        calls["prompt"] = prompt
        calls["output_path"] = output_path
        calls["kwargs"] = kwargs
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(b"fake-image-bytes")
        resolved_requested_mode = kwargs.get("mode") or actual_mode
        if requested_mode is not _UNSET:
            resolved_requested_mode = requested_mode
        return {
            "output_path": output_path,
            "requested_mode": resolved_requested_mode,
            "actual_mode": actual_mode,
            "model_used": model_used,
            "fallback_used": fallback_used,
            "fallback_from": fallback_from,
        }

    return _mock_generate


def test_generate_legacy_json_compatibility(monkeypatch):
    calls: Dict[str, Any] = {}
    monkeypatch.setattr(
        banana_service,
        "generate",
        _mock_generate_factory(calls, requested_mode=None),
    )

    payload = {"prompt": "a red fox in forest"}
    response = client.post("/generate", files=_json_upload(payload))

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["prompt"] == "a red fox in forest"
    assert data["image_url"].startswith("/outputs/generate/")

    meta = data["meta"]
    assert meta["model_used"] == "mock-proxy-model"
    assert meta["mode"] == "proxy"
    assert meta["requested_mode"] is None
    assert meta["fallback_used"] is False
    assert meta["fallback_from"] is None
    assert meta["prompt_source"] == "legacy"
    assert meta["reproducibility"] == "best_effort"

    effective = meta["effective_params"]
    assert effective["mode"] == "proxy"
    assert effective["steps"] == 30
    assert effective["cfg"] == 7.0
    assert effective["size"] == "512x512"

    assert calls["kwargs"]["mode"] is None
    assert calls["kwargs"]["negative_prompt"] is None


def test_generate_form_overrides_structured_params(monkeypatch):
    calls: Dict[str, Any] = {}
    monkeypatch.setattr(
        banana_service,
        "generate",
        _mock_generate_factory(calls, actual_mode="sd", model_used="mock-sd-model"),
    )

    payload = {
        "structured": {
            "subject": {"label": "cat", "entities": ["cat"], "attributes": {"color": "white"}},
            "scene": {"environment": ["street"]},
            "style": {"medium": ["illustration"]},
            "tech": {"lighting": ["cinematic light"]},
            "negative": {"terms": ["blurry"], "severity": "medium"},
            "params": {
                "size": "512x512",
                "steps": 20,
                "cfg": 6.0,
                "sampler": "Euler a",
                "seed": 111,
            },
        }
    }

    form_data = {
        "mode": "sd",
        "style_preset": "anime",
        "seed": "222",
        "steps": "40",
        "cfg": "9",
        "sampler": "DPM++ 2M Karras",
        "size": "640x640",
        "negative_prompt": "bad hands, deformed",
    }

    response = client.post("/generate", files=_json_upload(payload), data=form_data)

    assert response.status_code == 200, response.text
    data = response.json()
    meta = data["meta"]
    effective = meta["effective_params"]

    assert meta["mode"] == "sd"
    assert meta["requested_mode"] == "sd"
    assert meta["fallback_used"] is False
    assert meta["fallback_from"] is None
    assert meta["reproducibility"] == "strong"
    assert meta["style_applied"] == "anime"
    assert meta["prompt_source"] == "structured"

    assert effective["mode"] == "sd"
    assert effective["seed"] == 222
    assert effective["steps"] == 40
    assert effective["cfg"] == 9.0
    assert effective["size"] == "640x640"
    assert effective["sampler"] == "DPM++ 2M Karras"
    assert effective["has_negative_prompt"] is True

    assert calls["kwargs"]["mode"] == "sd"
    assert calls["kwargs"]["seed"] == 222
    assert calls["kwargs"]["steps"] == 40
    assert calls["kwargs"]["cfg"] == 9.0
    assert calls["kwargs"]["size"] == "640x640"
    assert calls["kwargs"]["negative_prompt"] == "bad hands, deformed"


def test_generate_omits_mode_when_unset(monkeypatch):
    calls: Dict[str, Any] = {}
    monkeypatch.setattr(
        banana_service,
        "generate",
        _mock_generate_factory(calls, actual_mode="sd", model_used="mock-sd-model", requested_mode=None),
    )

    payload = {"prompt": "a moonlit forest"}
    response = client.post("/generate", files=_json_upload(payload))

    assert response.status_code == 200, response.text
    meta = response.json()["meta"]
    assert meta["requested_mode"] is None
    assert meta["mode"] == "sd"
    assert calls["kwargs"]["mode"] is None


def test_generate_fallback_to_sd_updates_metadata(monkeypatch):
    calls: Dict[str, Any] = {}
    monkeypatch.setattr(
        banana_service,
        "generate",
        _mock_generate_factory(
            calls,
            actual_mode="sd",
            model_used="mock-sd-model",
            fallback_used=True,
            fallback_from="gemini",
        ),
    )

    payload = {"prompt": "a moonlit forest"}
    response = client.post(
        "/generate",
        files=_json_upload(payload),
        data={"mode": "gemini", "seed": "123"},
    )

    assert response.status_code == 200, response.text
    meta = response.json()["meta"]
    effective = meta["effective_params"]

    assert meta["mode"] == "sd"
    assert meta["requested_mode"] == "gemini"
    assert meta["fallback_used"] is True
    assert meta["fallback_from"] == "gemini"
    assert meta["model_used"] == "mock-sd-model"
    assert meta["reproducibility"] == "strong"
    assert effective["mode"] == "sd"
    assert calls["kwargs"]["mode"] == "gemini"


def test_generate_returns_error_when_fallback_disabled(monkeypatch):
    def _raise_error(prompt: str, output_path: str, **kwargs):
        raise RuntimeError("remote backend unavailable")

    monkeypatch.setattr(banana_service, "generate", _raise_error)

    payload = {"prompt": "test prompt"}
    response = client.post(
        "/generate",
        files=_json_upload(payload),
        data={"mode": "gemini"},
    )

    assert response.status_code == 500
    assert "remote backend unavailable" in response.json().get("detail", "")


@pytest.mark.parametrize(
    "form_data, expected_message",
    [
        ({"size": "bad-size"}, "Invalid size"),
        ({"steps": "0"}, "Invalid steps"),
        ({"cfg": "35"}, "Invalid cfg"),
    ],
)
def test_generate_invalid_param_boundaries(form_data, expected_message):
    payload = {"prompt": "test prompt"}
    response = client.post("/generate", files=_json_upload(payload), data=form_data)

    assert response.status_code == 400
    assert expected_message in response.json().get("detail", "")
