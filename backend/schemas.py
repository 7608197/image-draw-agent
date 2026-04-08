"""
Pydantic schemas for API request/response validation.
"""
from typing import List, Optional, Dict, Any, Union, Literal
from pydantic import BaseModel, Field


class WeightedTerm(BaseModel):
    """Negative term with individual weight."""
    term: str = Field(..., description="Negative prompt term")
    weight: float = Field(1.0, ge=0.1, le=2.0, description="Weight for this term")


class SubjectBlock(BaseModel):
    """Subject block: primary entities and attributes."""
    entities: List[str] = Field(default_factory=list, description="Detected entities")
    label: str = Field("", description="Main subject label")
    attributes: Union[Dict[str, str], List[str]] = Field(
        default_factory=dict,
        description="Attributes for subject"
    )
    count: Optional[int] = Field(None, ge=1, description="Entity count")
    weight: Optional[float] = Field(None, ge=0.8, le=1.2, description="Subject weight")


class SceneBlock(BaseModel):
    """Scene block: environment and composition."""
    environment: List[str] = Field(default_factory=list)
    background: List[str] = Field(default_factory=list)
    time_weather: List[str] = Field(default_factory=list)
    composition: List[str] = Field(default_factory=list)


class StyleBlock(BaseModel):
    """Style block: medium and aesthetics."""
    medium: List[str] = Field(default_factory=list)
    artist_style: List[str] = Field(default_factory=list)
    aesthetic: List[str] = Field(default_factory=list)
    quality: List[str] = Field(default_factory=list)


class TechBlock(BaseModel):
    """Tech block: lighting and camera details."""
    lighting: List[str] = Field(default_factory=list)
    camera: List[str] = Field(default_factory=list)
    color_tone: List[str] = Field(default_factory=list)
    render: List[str] = Field(default_factory=list)


class NegativeBlock(BaseModel):
    """Negative block: terms with overall severity and weights."""
    terms: List[str] = Field(default_factory=list)
    severity: Literal["weak", "medium", "strong"] = Field("medium")
    term_weights: List[WeightedTerm] = Field(default_factory=list)


class ParamsBlock(BaseModel):
    """Suggested generation params."""
    size: str = Field("512x512", description="Image dimensions WxH")
    steps: int = Field(30, ge=1, le=150)
    cfg: float = Field(7.0, ge=1.0, le=30.0)
    sampler: str = Field("DPM++ 2M Karras", description="Recommended sampler")
    seed: Optional[int] = Field(None, description="Suggested seed")


class StructuredPrompt(BaseModel):
    """Structured prompt with 6 blocks."""
    subject: SubjectBlock
    scene: SceneBlock
    style: StyleBlock
    tech: TechBlock
    negative: NegativeBlock
    params: ParamsBlock


class ReverseMeta(BaseModel):
    """Metadata about the reverse operation."""
    model_used: str = Field(..., description="Model used for image analysis")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")


class ReverseResponse(BaseModel):
    """Complete response schema for POST /reverse endpoint."""
    schema_version: str = Field("2.0.0", description="API schema version")
    id: str = Field(..., description="Unique identifier (SHA256 of image)")
    caption: str = Field(..., description="Natural language description of the image")
    structured: StructuredPrompt = Field(
        ...,
        description="Structured prompt blocks"
    )
    prompt: str = Field(..., description="Compiled prompt ready for SD/MJ")
    meta: ReverseMeta = Field(..., description="Processing metadata")
    raw: Optional[Dict[str, Any]] = Field(None, description="Raw model output for debugging")


class GenerateRequest(BaseModel):
    """Request schema for POST /generate endpoint."""
    schema_version: Optional[str] = Field("1.0.0", description="Request schema version")
    prompt: Optional[str] = Field(None, description="Positive prompt for generation")
    caption: Optional[str] = Field(None, description="Fallback caption for generation")


class GenerateMeta(BaseModel):
    """Metadata about the generation operation."""
    model_used: str = Field(..., description="Model or backend used")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")


class GenerateResponse(BaseModel):
    """Response schema for POST /generate endpoint."""
    schema_version: str = Field("1.0.0", description="API schema version")
    id: str = Field(..., description="Unique identifier for the generation")
    prompt: str = Field(..., description="Prompt used for generation")
    image_url: str = Field(..., description="Public URL for generated image")
    meta: GenerateMeta = Field(..., description="Generation metadata")
    raw: Optional[Dict[str, Any]] = Field(None, description="Raw model output for debugging")


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str
    error_code: Optional[str] = None
