"""
Reverse image-to-prompt service.
Supports STUB and Gemini Vision modes.
"""
import base64
import hashlib
import json
import logging
import os
import time
from typing import List, Dict, Any, Optional
from io import BytesIO
from PIL import Image
import requests

logger = logging.getLogger(__name__)

try:
    from google import genai
    from google.genai import types
except Exception:
    genai = None
    types = None

from schemas import (
    ReverseResponse,
    StructuredPrompt,
    SubjectBlock,
    SceneBlock,
    StyleBlock,
    TechBlock,
    NegativeBlock,
    WeightedTerm,
    ParamsBlock,
    ReverseMeta,
)


class ReverseService:
    """Service for analyzing images and generating prompts."""

    def __init__(self):
        self.mode = "cliproxy"
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.gemini_model = os.getenv("GEMINI_VISION_MODEL", "gemini-2.0-flash")
        self.gemini_client = None
        self.cliproxy_base_url = "http://121.43.226.149:8317/v1"
        self.cliproxy_api_key = "cc-silKI2FHUOGZfeJk9"
        self.cliproxy_model = "gpt-5.2"
        self.cliproxy_image_format = os.getenv("CLIPROXY_IMAGE_FORMAT", "auto").lower()
        self.stub_model_name = "STUB-Vision-v2"
        print(f"Initialized ReverseService with mode: {self.mode}")

    def calculate_sha256(self, image_bytes: bytes) -> str:
        """Calculate SHA256 hash of image bytes."""
        return hashlib.sha256(image_bytes).hexdigest()

    def _get_image_mime(self, image: Image.Image) -> str:
        if image.format:
            return Image.MIME.get(image.format, "image/png")
        return "image/png"

    def _get_gemini_client(self):
        if genai is None or types is None:
            raise RuntimeError("google.genai is not available")
        if not self.gemini_client:
            if not self.gemini_api_key or "你的_API_KEY" in self.gemini_api_key:
                raise ValueError("GEMINI_API_KEY is not set")
            self.gemini_client = genai.Client(api_key=self.gemini_api_key)
        return self.gemini_client

    def _extract_json_object(self, text: str) -> Dict[str, Any]:
        start = text.find("{")
        if start == -1:
            raise ValueError("No JSON object found in model response")
        depth = 0
        for idx in range(start, len(text)):
            ch = text[idx]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start:idx + 1]
                    return json.loads(candidate)
        raise ValueError("Incomplete JSON object in model response")

    def _extract_responses_text(self, data: Dict[str, Any]) -> str:
        if not isinstance(data, dict):
            return ""
        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text:
            return output_text
        output = data.get("output", [])
        if isinstance(output, list):
            for item in output:
                if isinstance(item, dict):
                    content = item.get("content", [])
                    if isinstance(content, list):
                        for part in content:
                            if isinstance(part, dict):
                                if part.get("type") in {"output_text", "text"}:
                                    text = part.get("text") or part.get("output_text")
                                    if text:
                                        return text
        return ""

    def _ensure_list(self, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item is not None]
        if isinstance(value, str):
            return [value]
        return [str(value)]

    def _normalize_attributes(self, value: Any) -> Any:
        if value is None:
            return {}
        if isinstance(value, dict):
            return {str(k): str(v) for k, v in value.items()}
        if isinstance(value, list):
            return [str(item) for item in value if item is not None]
        if isinstance(value, str):
            return [value]
        return [str(value)]

    def _clamp_float(self, value: float, min_value: float, max_value: float) -> float:
        return max(min_value, min(max_value, value))

    def _normalize_term_weights(self, value: Any, terms: List[str]) -> List[WeightedTerm]:
        items: List[WeightedTerm] = []
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and "term" in item:
                    raw_weight = item.get("weight", 1.0)
                    try:
                        weight = float(raw_weight)
                    except (TypeError, ValueError):
                        weight = 1.0
                    weight = self._clamp_float(weight, 0.1, 2.0)
                    items.append(WeightedTerm(term=str(item["term"]), weight=weight))
                elif isinstance(item, str):
                    items.append(WeightedTerm(term=item, weight=1.0))
        if not items and terms:
            items = [WeightedTerm(term=term, weight=1.1) for term in terms]
        return items

    def _normalize_count(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            count = int(value)
        except (TypeError, ValueError):
            return None
        if count < 1:
            return None
        return count

    def _normalize_subject_weight(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            weight = float(value)
        except (TypeError, ValueError):
            return None
        return self._clamp_float(weight, 0.8, 1.2)

    def _normalize_severity(self, value: Any) -> str:
        if isinstance(value, str):
            if value in {"weak", "medium", "strong"}:
                return value
            severity_map = {"low": "weak", "high": "strong", "critical": "strong"}
            if value.lower() in severity_map:
                return severity_map[value.lower()]
        return "medium"

    def _build_structured_prompt(self, structured_data: Dict[str, Any], params: ParamsBlock) -> StructuredPrompt:
        subject_data = structured_data.get("subject", {}) if isinstance(structured_data, dict) else {}
        scene_data = structured_data.get("scene", {}) if isinstance(structured_data, dict) else {}
        style_data = structured_data.get("style", {}) if isinstance(structured_data, dict) else {}
        tech_data = structured_data.get("tech", {}) if isinstance(structured_data, dict) else {}
        negative_data = structured_data.get("negative", {}) if isinstance(structured_data, dict) else {}

        subject = SubjectBlock(
            entities=self._ensure_list(subject_data.get("entities")),
            label=str(subject_data.get("label", "")),
            attributes=self._normalize_attributes(subject_data.get("attributes")),
            count=self._normalize_count(subject_data.get("count")),
            weight=self._normalize_subject_weight(subject_data.get("weight")),
        )

        scene = SceneBlock(
            environment=self._ensure_list(scene_data.get("environment")),
            background=self._ensure_list(scene_data.get("background")),
            time_weather=self._ensure_list(scene_data.get("time_weather")),
            composition=self._ensure_list(scene_data.get("composition")),
        )

        style = StyleBlock(
            medium=self._ensure_list(style_data.get("medium")),
            artist_style=self._ensure_list(style_data.get("artist_style")),
            aesthetic=self._ensure_list(style_data.get("aesthetic")),
            quality=self._ensure_list(style_data.get("quality")),
        )

        tech = TechBlock(
            lighting=self._ensure_list(tech_data.get("lighting")),
            camera=self._ensure_list(tech_data.get("camera")),
            color_tone=self._ensure_list(tech_data.get("color_tone")),
            render=self._ensure_list(tech_data.get("render")),
        )

        negative_terms = self._ensure_list(negative_data.get("terms"))
        negative = NegativeBlock(
            terms=negative_terms,
            severity=self._normalize_severity(negative_data.get("severity")),
            term_weights=self._normalize_term_weights(negative_data.get("term_weights"), negative_terms),
        )

        return StructuredPrompt(
            subject=subject,
            scene=scene,
            style=style,
            tech=tech,
            negative=negative,
            params=params,
        )

    def _format_weight(self, text: str, weight: Optional[float]) -> str:
        if weight is not None and weight != 1.0:
            return f"({text}:{weight:.1f})"
        return text

    def compile_structured_prompt(self, structured: StructuredPrompt) -> Dict[str, str]:
        """Compile structured prompt into positive and negative strings."""
        parts: List[str] = []
        subject = structured.subject

        if subject.label:
            parts.append(self._format_weight(subject.label, subject.weight))
        if subject.entities:
            parts.extend(subject.entities)
        if isinstance(subject.attributes, dict):
            parts.extend([f"{k} {v}" for k, v in subject.attributes.items()])
        elif isinstance(subject.attributes, list):
            parts.extend(subject.attributes)

        scene = structured.scene
        parts.extend(scene.environment)
        parts.extend(scene.background)
        parts.extend(scene.time_weather)
        parts.extend(scene.composition)

        style = structured.style
        parts.extend(style.medium)
        parts.extend(style.artist_style)
        parts.extend(style.aesthetic)
        parts.extend(style.quality)

        tech = structured.tech
        parts.extend(tech.lighting)
        parts.extend(tech.camera)
        parts.extend(tech.color_tone)
        parts.extend(tech.render)

        positive = ", ".join([p for p in parts if p])

        negative_parts: List[str] = []
        negative = structured.negative
        for item in negative.term_weights:
            if item.term:
                negative_parts.append(self._format_weight(item.term, item.weight))
        existing = {item.term for item in negative.term_weights}
        for term in negative.terms:
            if term and term not in existing:
                negative_parts.append(term)

        negative_text = ", ".join(negative_parts)
        return {"positive": positive, "negative": negative_text}

    def _suggest_params(self, image: Image.Image) -> ParamsBlock:
        width, height = image.size
        if height > width:
            size = "512x768"
        elif width > height:
            size = "768x512"
        else:
            size = "512x512"
        return ParamsBlock(
            size=size,
            steps=30,
            cfg=7.0,
            sampler="DPM++ 2M Karras",
            seed=123456,
        )

    def analyze_image_stub(self, image: Image.Image) -> Dict[str, Any]:
        """STUB: Analyze image and return dummy structured data."""
        width, height = image.size
        aspect = "portrait" if height > width else "landscape" if width > height else "square"

        caption = (
            f"A {aspect} digital artwork with dimensions {width}x{height}. "
            "The composition features balanced elements with professional lighting."
        )

        structured = {
            "subject": {
                "label": "digital artwork",
                "entities": ["main subject"],
                "attributes": {"detail": "highly detailed"},
                "count": 1,
                "weight": 1.1,
            },
            "scene": {
                "environment": ["studio setting"],
                "background": ["clean background"],
                "time_weather": ["soft light"],
                "composition": [f"{aspect} composition"],
            },
            "style": {
                "medium": ["digital art"],
                "artist_style": ["concept art"],
                "aesthetic": ["cinematic"],
                "quality": ["masterpiece", "best quality"],
            },
            "tech": {
                "lighting": ["professional lighting"],
                "camera": ["50mm lens"],
                "color_tone": ["vivid colors"],
                "render": ["8k"],
            },
            "negative": {
                "terms": ["blurry", "low quality", "artifacts"],
                "severity": "medium",
                "term_weights": [
                    {"term": "blurry", "weight": 1.2},
                    {"term": "low quality", "weight": 1.1},
                ],
            },
        }

        return {
            "caption": caption,
            "structured": structured,
            "confidence": 0.85,
            "model_used": self.stub_model_name,
            "raw": {
                "stub_mode": True,
                "image_size": image.size,
                "image_mode": image.mode,
            },
        }

    def _get_base_schema_prompt(self) -> str:
        return (
            "You are an image analysis model. Return ONLY valid JSON with this schema:\n"
            "{\n"
            "  \"caption\": \"...\",\n"
            "  \"confidence\": 0.0,\n"
            "  \"structured\": {\n"
            "    \"subject\": {\"entities\": [\"\"], \"label\": \"\", \"attributes\": {}, \"count\": 1, \"weight\": 1.0},\n"
            "    \"scene\": {\"environment\": [], \"background\": [], \"time_weather\": [], \"composition\": []},\n"
            "    \"style\": {\"medium\": [], \"artist_style\": [], \"aesthetic\": [], \"quality\": []},\n"
            "    \"tech\": {\"lighting\": [], \"camera\": [], \"color_tone\": [], \"render\": []},\n"
            "    \"negative\": {\"terms\": [], \"severity\": \"medium\", \"term_weights\": [{\"term\": \"\", \"weight\": 1.0}]}\n"
            "  }\n"
            "}\n"
            "Rules: JSON only, no code fences. Use short English prompt terms."
        )

    def analyze_image_gemini(self, image_bytes: bytes, mime_type: str) -> Dict[str, Any]:
        """Analyze image with Gemini Vision and return parsed JSON."""
        client = self._get_gemini_client()
        prompt = self._get_base_schema_prompt()

        response = client.models.generate_content(
            model=self.gemini_model,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(prompt),
                        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    ],
                )
            ],
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=2048,
            ),
        )

        text = response.text or ""
        payload = self._extract_json_object(text)
        return {
            "caption": str(payload.get("caption", "")),
            "structured": payload.get("structured", {}),
            "confidence": float(payload.get("confidence", 0.75)) if payload.get("confidence") is not None else 0.75,
            "model_used": self.gemini_model,
            "raw": {
                "model_response": text,
                "parsed": payload,
            },
        }

    def _build_image_payloads(self, image_bytes: bytes, mime_type: str) -> List[Dict[str, Any]]:
        b64 = base64.b64encode(image_bytes).decode()
        data_url = f"data:{mime_type};base64,{b64}"

        prompt = self._get_base_schema_prompt()
        return [
            {
                "name": "openai_image_url",
                "payload": {
                    "model": self.cliproxy_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": data_url},
                                },
                            ],
                        }
                    ],
                },
            },
            {
                "name": "openai_image_url_string",
                "payload": {
                    "model": self.cliproxy_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": data_url,
                                },
                            ],
                        }
                    ],
                },
            },
            {
                "name": "content_image_base64",
                "payload": {
                    "model": self.cliproxy_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image", "image": b64},
                            ],
                        }
                    ],
                },
            },
            {
                "name": "content_input_image_dataurl",
                "payload": {
                    "model": self.cliproxy_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "input_image", "image_url": data_url},
                            ],
                        }
                    ],
                },
            },
            {
                "name": "top_level_images",
                "payload": {
                    "model": self.cliproxy_model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "images": [b64],
                },
            },
        ]

    def analyze_image_cliproxy(self, image_bytes: bytes, mime_type: str) -> Dict[str, Any]:
        """Analyze image with OpenAI-compatible proxy using multiple image formats."""
        if not self.cliproxy_base_url:
            raise ValueError("CLIPROXY_BASE_URL is not set")
        if not self.cliproxy_api_key:
            raise ValueError("CLIPROXY_API_KEY is not set")

        base_url = self.cliproxy_base_url.rstrip("/")
        responses_endpoint = base_url + "/responses"
        chat_endpoint = base_url + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.cliproxy_api_key}",
            "Content-Type": "application/json",
        }

        payloads = self._build_image_payloads(image_bytes, mime_type)
        if self.cliproxy_image_format != "auto":
            payloads = [p for p in payloads if p["name"] == self.cliproxy_image_format]
            if not payloads:
                raise ValueError("Unsupported CLIPROXY_IMAGE_FORMAT")

        last_error: Optional[str] = None
        for item in payloads:
            prompt = self._get_base_schema_prompt()
            responses_payload = {
                "model": self.cliproxy_model,
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {"type": "input_image", "image_url": item["payload"]["messages"][0]["content"][1]["image_url"] if isinstance(item["payload"]["messages"][0]["content"][1].get("image_url"), str) else item["payload"]["messages"][0]["content"][1]["image_url"]["url"]},
                        ],
                    }
                ],
            }

            response = requests.post(responses_endpoint, headers=headers, json=responses_payload, timeout=60)
            if response.status_code == 200:
                data = response.json()
                content = self._extract_responses_text(data)
                if not content:
                    last_error = f"{item['name']}: empty response"
                    continue
                payload = self._extract_json_object(content)
                return {
                    "caption": str(payload.get("caption", "")),
                    "structured": payload.get("structured", {}),
                    "confidence": float(payload.get("confidence", 0.75)) if payload.get("confidence") is not None else 0.75,
                    "model_used": self.cliproxy_model,
                    "raw": {
                        "model_response": content,
                        "parsed": payload,
                        "image_format": item["name"],
                        "endpoint": "responses",
                    },
                }

            last_error = f"responses {item['name']}: {response.status_code} {response.text}"

            response = requests.post(chat_endpoint, headers=headers, json=item["payload"], timeout=60)
            if response.status_code != 200:
                last_error = f"chat {item['name']}: {response.status_code} {response.text}"
                continue
            data = response.json()
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            if not content:
                last_error = f"chat {item['name']}: empty response"
                continue

            payload = self._extract_json_object(content)
            return {
                "caption": str(payload.get("caption", "")),
                "structured": payload.get("structured", {}),
                "confidence": float(payload.get("confidence", 0.75)) if payload.get("confidence") is not None else 0.75,
                "model_used": self.cliproxy_model,
                "raw": {
                    "model_response": content,
                    "parsed": payload,
                    "image_format": item["name"],
                    "endpoint": "chat",
                },
            }

        raise RuntimeError(last_error or "Cliproxy request failed")

    def _serialize_response(self, response: ReverseResponse) -> Dict[str, Any]:
        if hasattr(response, "model_dump"):
            return response.model_dump()
        return response.dict()

    def _save_outputs(self, image_id: str, response: ReverseResponse, compiled: Dict[str, str]) -> None:
        output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "outputs", "reverse"))
        os.makedirs(output_dir, exist_ok=True)
        json_path = os.path.join(output_dir, f"{image_id}.json")
        txt_path = os.path.join(output_dir, f"{image_id}.txt")

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self._serialize_response(response), f, ensure_ascii=False, indent=2)

        text_lines = [f"Positive prompt:\n{compiled['positive']}"]
        if compiled["negative"]:
            text_lines.append(f"\nNegative prompt:\n{compiled['negative']}")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(text_lines))

    async def reverse_image(self, image_bytes: bytes) -> ReverseResponse:
        """
        Main entry point: analyze image and return full reverse response.

        Args:
            image_bytes: Raw image file bytes

        Returns:
            ReverseResponse with all fields populated

        Raises:
            ValueError: If image cannot be processed
        """
        start_time = time.time()

        try:
            image = Image.open(BytesIO(image_bytes))
            image.verify()
            image = Image.open(BytesIO(image_bytes))
        except Exception as e:
            raise ValueError(f"Invalid image file: {str(e)}")

        image_id = self.calculate_sha256(image_bytes)
        mime_type = self._get_image_mime(image)

        if self.mode == "gemini":
            if not self.gemini_api_key or "你的_API_KEY" in self.gemini_api_key:
                logger.warning("Gemini API key not configured, falling back to STUB mode")
                analysis = self.analyze_image_stub(image)
            else:
                try:
                    analysis = self.analyze_image_gemini(image_bytes, mime_type)
                except Exception as e:
                    logger.error("Gemini analysis failed, falling back to STUB: %s", e, exc_info=True)
                    analysis = self.analyze_image_stub(image)
        elif self.mode == "cliproxy":
            if not self.cliproxy_api_key:
                logger.warning("Cliproxy API key not configured, falling back to STUB mode")
                analysis = self.analyze_image_stub(image)
            else:
                try:
                    analysis = self.analyze_image_cliproxy(image_bytes, mime_type)
                except Exception as e:
                    logger.error("Cliproxy analysis failed, falling back to STUB: %s", e, exc_info=True)
                    analysis = self.analyze_image_stub(image)
                    raw = analysis.get("raw")
                    if isinstance(raw, dict):
                        raw["cliproxy_error"] = str(e)
                    else:
                        analysis["raw"] = {"cliproxy_error": str(e)}
        else:
            analysis = self.analyze_image_stub(image)

        params = self._suggest_params(image)
        structured = self._build_structured_prompt(analysis.get("structured", {}), params)
        compiled = self.compile_structured_prompt(structured)

        processing_time_ms = max(1, int((time.time() - start_time) * 1000))
        meta = ReverseMeta(
            model_used=analysis.get("model_used", self.stub_model_name),
            confidence=analysis.get("confidence", 0.0),
            processing_time_ms=processing_time_ms,
        )

        caption = analysis.get("caption", "") or "Image analysis result."

        response = ReverseResponse(
            schema_version="2.0.0",
            id=image_id,
            caption=caption,
            structured=structured,
            prompt=compiled["positive"],
            meta=meta,
            raw=analysis.get("raw"),
        )

        self._save_outputs(image_id, response, compiled)
        return response


# Singleton instance
reverse_service = ReverseService()
