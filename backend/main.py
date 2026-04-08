"""
FastAPI Backend for Graduation Project Image Generation Service.
Provides endpoints for image generation and reverse prompt engineering.
"""
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
import time
import uuid
import json as jsonlib

from schemas import ReverseResponse, ErrorResponse, GenerateResponse, GenerateMeta
from services.reverse_service import reverse_service
from services.banana_service_flow2 import banana_service

# Initialize FastAPI app
app = FastAPI(
    title="Image Generation Service API",
    description="Graduation project backend for AI image generation and analysis",
    version="1.1.0"
)

OUTPUTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "outputs"))
os.makedirs(OUTPUTS_DIR, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Health Check Endpoint ---
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "image-generation-api"}


# --- POST /reverse Endpoint ---
@app.post(
    "/reverse",
    response_model=ReverseResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input"},
        413: {"model": ErrorResponse, "description": "File too large"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Reverse engineer image to prompt",
    description="Upload an image to generate a descriptive prompt and metadata"
)
async def reverse_image(
    image: UploadFile = File(..., description="Image file (max 10MB, jpg/png/webp)")
):
    """
    Reverse engineer an uploaded image into a structured prompt.

    **Input**: multipart/form-data with 'image' file
    **Output**: JSON with caption, structured prompt, prompt, and metadata
    """
    # Validate file size (10MB limit)
    MAX_SIZE = 10 * 1024 * 1024  # 10MB

    # Read file
    try:
        image_bytes = await image.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    # Check size
    if len(image_bytes) > MAX_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {len(image_bytes)} bytes (max {MAX_SIZE} bytes)"
        )

    # Validate content type
    allowed_types = ["image/jpeg", "image/png", "image/webp", "image/jpg"]
    if image.content_type and image.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {image.content_type}. Allowed: {allowed_types}"
        )

    # Process image
    try:
        result = await reverse_service.reverse_image(image_bytes)
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal processing error: {str(e)}"
        )


# --- POST /generate Endpoint ---
@app.post(
    "/generate",
    response_model=GenerateResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input"},
        413: {"model": ErrorResponse, "description": "File too large"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Generate image from prompt JSON",
    description="Upload JSON to generate an image and return the hosted image URL"
)
async def generate_image(
    json_file: UploadFile = File(..., description="Prompt JSON file (max 1MB)", alias="json"),
    strict_json: bool = False,
):
    """
    Generate an image from uploaded JSON.
    """
    MAX_SIZE = 1 * 1024 * 1024

    if json_file.content_type and json_file.content_type not in ["application/json", "text/json"]:
        raise HTTPException(status_code=400, detail="Unsupported file type. Please upload JSON.")

    try:
        raw_bytes = await json_file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    if len(raw_bytes) > MAX_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large: {len(raw_bytes)} bytes (max {MAX_SIZE} bytes)")

    try:
        data = jsonlib.loads(raw_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON content")

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="JSON root must be an object")

    prompt = (data.get("prompt") or data.get("caption") or "").strip()
    prompt_for_response = prompt or "[json-spec]"
    json_spec_compact = jsonlib.dumps(data, ensure_ascii=False, separators=(",", ":"))

    if strict_json:
        model_prompt = json_spec_compact
    else:
        model_prompt = (
            "Generate one image strictly based on this JSON specification. "
            "Use all fields as constraints when present.\nJSON:\n"
            f"{json_spec_compact}"
        )

    output_dir = os.path.abspath(os.path.join(OUTPUTS_DIR, "generate"))
    os.makedirs(output_dir, exist_ok=True)
    generation_id = uuid.uuid4().hex
    output_path = os.path.join(output_dir, f"{generation_id}.png")

    start_time = time.time()
    try:
        result = banana_service.generate(model_prompt, output_path, mode="proxy")
        if not result:
            raise RuntimeError("No image generated")
        mode_info = banana_service.get_mode_info(mode="proxy")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation error: {str(e)}")

    processing_time_ms = max(1, int((time.time() - start_time) * 1000))
    image_url = f"/outputs/generate/{generation_id}.png"

    response = GenerateResponse(
        id=generation_id,
        prompt=prompt_for_response,
        image_url=image_url,
        meta=GenerateMeta(
            model_used=mode_info["model_used"],
            processing_time_ms=processing_time_ms,
        ),
    )
    return response


# --- Main Entry Point ---
if __name__ == "__main__":
    print("Starting Image Generation Service API...")
    print("Server will run at: http://127.0.0.1:8001")
    print("API docs available at: http://127.0.0.1:8001/docs")

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8001,
        reload=True,  # Auto-reload during development
        log_level="info"
    )
