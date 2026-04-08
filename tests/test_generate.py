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


def _mock_generate_factory(calls: Dict[str, Any]):
    def _mock_generate(prompt: str, output_path: str, **kwargs):
        calls["prompt"] = prompt
        calls["output_path"] = output_path
        calls["kwargs"] = kwargs
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(b"fake-image-bytes")
        return output_path

    return _mock_generate


def test_generate_legacy_json_compatibility(monkeypatch):
    calls: Dict[str, Any] = {}
    monkeypatch.setattr(banana_service, "generate", _mock_generate_factory(calls))
    monkeypatch.setattr(
        banana_service,
        "get_mode_info",
        lambda mode=None: {"mode": mode or "proxy", "model_used": "mock-proxy-model"},
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
    assert meta["prompt_source"] == "legacy"
    assert meta["reproducibility"] == "best_effort"

    effective = meta["effective_params"]
    assert effective["steps"] == 30
    assert effective["cfg"] == 7.0
    assert effective["size"] == "512x512"

    assert calls["kwargs"]["mode"] is None
    assert calls["kwargs"]["negative_prompt"] is None


def test_generate_form_overrides_structured_params(monkeypatch):
    calls: Dict[str, Any] = {}
    monkeypatch.setattr(banana_service, "generate", _mock_generate_factory(calls))
    monkeypatch.setattr(
        banana_service,
        "get_mode_info",
        lambda mode=None: {"mode": mode or "proxy", "model_used": "mock-sd-model"},
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
    assert meta["reproducibility"] == "strong"
    assert meta["style_applied"] == "anime"
    assert meta["prompt_source"] == "structured"

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
