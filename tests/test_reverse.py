"""
Test suite for POST /reverse endpoint.
"""
import pytest
import hashlib
from pathlib import Path
from io import BytesIO
from PIL import Image
from fastapi.testclient import TestClient

import sys
import os

os.environ.setdefault("REVERSE_MODE", "stub")

# Add backend directory to sys.path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend'))

from main import app
from schemas import ReverseResponse


# Initialize test client
client = TestClient(app)


@pytest.fixture
def test_image_bytes():
    """Create a simple test image in memory."""
    img = Image.new("RGB", (512, 512), color=(73, 109, 137))
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()


@pytest.fixture
def test_image_sha256(test_image_bytes):
    """Calculate expected SHA256 of test image."""
    return hashlib.sha256(test_image_bytes).hexdigest()


def test_health_check():
    """Test that health check endpoint works."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_reverse_endpoint_success(test_image_bytes, test_image_sha256):
    """Test successful reverse image request."""
    # Prepare multipart form data
    files = {
        "image": ("test.png", BytesIO(test_image_bytes), "image/png")
    }

    # Make request
    response = client.post("/reverse", files=files)

    # Assert response
    assert response.status_code == 200, f"Failed with: {response.text}"

    # Parse response
    data = response.json()

    # Validate schema fields exist
    assert "schema_version" in data
    assert "id" in data
    assert "caption" in data
    assert "structured" in data
    assert "prompt" in data
    assert "meta" in data

    # Validate ID is correct SHA256
    assert data["id"] == test_image_sha256

    # Validate schema version
    assert data["schema_version"] == "2.0.0"

    # Validate structured is object with 6 blocks
    assert isinstance(data["structured"], dict)
    for key in ["subject", "scene", "style", "tech", "negative", "params"]:
        assert key in data["structured"]

    negative = data["structured"]["negative"]
    assert "severity" in negative
    assert "term_weights" in negative

    # Validate prompt is non-empty string
    assert isinstance(data["prompt"], str)
    assert len(data["prompt"]) > 0

    # Validate params block
    params = data["structured"]["params"]
    assert "steps" in params
    assert "cfg" in params
    assert "sampler" in params
    assert "size" in params

    # Validate meta
    meta = data["meta"]
    assert "model_used" in meta
    assert "confidence" in meta
    assert "processing_time_ms" in meta
    assert 0.0 <= meta["confidence"] <= 1.0
    assert meta["processing_time_ms"] > 0

    print(f"\nTest passed! Response ID: {data['id'][:16]}...")
    print(f"Caption: {data['caption'][:80]}...")
    print(f"Prompt: {data['prompt'][:80]}...")


def test_reverse_file_too_large():
    """Test that files over 10MB are rejected."""
    # Create a 11MB fake file
    large_data = b"0" * (11 * 1024 * 1024)
    files = {
        "image": ("large.png", BytesIO(large_data), "image/png")
    }

    response = client.post("/reverse", files=files)
    assert response.status_code == 413


def test_reverse_invalid_content_type():
    """Test that non-image files are rejected."""
    files = {
        "image": ("test.txt", BytesIO(b"not an image"), "text/plain")
    }

    response = client.post("/reverse", files=files)
    assert response.status_code == 400


def test_reverse_invalid_image_data():
    """Test that corrupted image data is handled."""
    files = {
        "image": ("corrupt.png", BytesIO(b"corrupted data"), "image/png")
    }

    response = client.post("/reverse", files=files)
    # Should return 400 or 500, depending on error handling
    assert response.status_code in [400, 500]


def test_prompt_has_weights(test_image_bytes):
    """Test that prompt correctly formats weights."""
    files = {
        "image": ("test.png", BytesIO(test_image_bytes), "image/png")
    }

    response = client.post("/reverse", files=files)
    assert response.status_code == 200

    data = response.json()
    prompt = data["prompt"]

    # Subject weight should be formatted
    assert "(digital artwork:1.1)" in prompt

    # Non-weighted elements should appear without parentheses
    assert "digital art" in prompt

    print(f"\nPrompt format validated: {prompt}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
