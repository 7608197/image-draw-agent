# Test Commands for POST /reverse Endpoint

## Prerequisites
1. Start the FastAPI server:
   ```bash
   python backend/main.py
   ```
   Server will run at http://127.0.0.1:8000
   API docs: http://127.0.0.1:8000/docs

## Windows (PowerShell)

### Health Check
```powershell
curl http://127.0.0.1:8000/health
```

### Test /reverse with existing image
```powershell
curl -X POST "http://127.0.0.1:8000/reverse" `
  -F "image=@tests\images\test_output_1770050178.png" `
  -H "accept: application/json"
```

### Test with Python verification script
```powershell
python tests\verify_reverse.py
```

### Run pytest suite
```powershell
pytest tests\test_reverse.py -v -s
```

## Linux/Mac (Bash)

### Health Check
```bash
curl http://127.0.0.1:8000/health
```

### Test /reverse with existing image
```bash
curl -X POST "http://127.0.0.1:8000/reverse" \
  -F "image=@tests/images/test_output_1770050178.png" \
  -H "accept: application/json"
```

### Test with Python verification script
```bash
python tests/verify_reverse.py
```

### Run pytest suite
```bash
pytest tests/test_reverse.py -v -s
```

## Expected Response

```json
{
  "schema_version": "2.0.0",
  "id": "abc123...def789",
  "caption": "A landscape digital artwork with dimensions 1024x768...",
  "structured": {
    "subject": {
      "entities": ["main subject"],
      "label": "digital artwork",
      "attributes": {"detail": "highly detailed"},
      "count": 1,
      "weight": 1.1
    },
    "scene": {
      "environment": ["studio setting"],
      "background": ["clean background"],
      "time_weather": ["soft light"],
      "composition": ["landscape composition"]
    },
    "style": {
      "medium": ["digital art"],
      "artist_style": ["concept art"],
      "aesthetic": ["cinematic"],
      "quality": ["masterpiece", "best quality"]
    },
    "tech": {
      "lighting": ["professional lighting"],
      "camera": ["50mm lens"],
      "color_tone": ["vivid colors"],
      "render": ["8k"]
    },
    "negative": {
      "terms": ["blurry", "low quality"],
      "severity": "medium",
      "term_weights": [
        {"term": "blurry", "weight": 1.2},
        {"term": "low quality", "weight": 1.1}
      ]
    },
    "params": {
      "size": "1024x768",
      "steps": 30,
      "cfg": 7.0,
      "sampler": "DPM++ 2M Karras",
      "seed": 123456
    }
  },
  "prompt": "(digital artwork:1.1), main subject, detail highly detailed, studio setting, clean background, soft light, landscape composition, digital art, concept art, cinematic, masterpiece, best quality, professional lighting, 50mm lens, vivid colors, 8k",
  "meta": {
    "model_used": "STUB-Vision-v2",
    "confidence": 0.85,
    "processing_time_ms": 42
  },
  "raw": {
    "stub_mode": true,
    "image_size": [1024, 768],
    "image_mode": "RGB"
  }
}
```

## Troubleshooting

### Port already in use
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:8000 | xargs kill -9
```

### Import errors
```bash
# Ensure you're in the project root
cd G:\Dev\repos\bishe

# Install dependencies
pip install fastapi uvicorn pillow pydantic pytest requests
```

### File not found
- Ensure you use the correct path separator for your OS
- Windows: backslash `\` or forward slash `/`
- Linux/Mac: forward slash `/`
