"""
Quick verification script for /reverse endpoint.
Run this AFTER starting the FastAPI server with: python backend/main.py
"""
import requests
from io import BytesIO
from PIL import Image
import json

# Create a test image
img = Image.new("RGB", (512, 512), color=(100, 150, 200))
buffer = BytesIO()
img.save(buffer, format="PNG")
buffer.seek(0)

# Make request
print("Sending request to http://127.0.0.1:8000/reverse...")
response = requests.post(
    "http://127.0.0.1:8000/reverse",
    files={"image": ("test.png", buffer, "image/png")}
)

# Display results
print(f"\nStatus Code: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print("\n=== SUCCESS ===")
    print(f"ID: {data['id'][:16]}...")
    print(f"Caption: {data['caption']}")
    print(f"\nStructured Blocks: {list(data['structured'].keys())}")
    print(f"\nPrompt: {data['prompt']}")
    print(f"\nParams: {data['structured']['params']}")
    print(f"\nMeta: Model={data['meta']['model_used']}, "
          f"Confidence={data['meta']['confidence']}, "
          f"Time={data['meta']['processing_time_ms']}ms")
    print("\n=== FULL RESPONSE ===")
    print(json.dumps(data, indent=2, ensure_ascii=False))
else:
    print("\n=== ERROR ===")
    print(response.text)
