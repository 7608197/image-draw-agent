"""
毕业设计后端主入口（FastAPI）。

职责概览：
1) 暴露图生文接口 /reverse（上传图片 -> 返回 caption + structured + prompt）
2) 暴露文生图接口 /generate（上传 JSON -> 生成图片 -> 返回 image_url）
3) 统一进行输入校验、参数归一化、错误映射与响应组装
4) 挂载 outputs 静态目录，便于前端直接访问生成产物
"""
from typing import Any, Dict, Optional, List

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
import time
import uuid
import json as jsonlib

# Pydantic 响应模型（约束 API 输出结构）
from schemas import ReverseResponse, ErrorResponse, GenerateResponse, GenerateMeta, ParamsBlock
# 图生文核心服务（图片分析、结构化构建、prompt 编译）
from services.reverse_service import reverse_service
# 文生图核心服务（支持 sd / gemini / proxy 三种生成模式）
from services.banana_service_flow2 import banana_service

# ------------------------------
# FastAPI 应用初始化
# ------------------------------
# title / description / version 会展示在 Swagger 文档页（/docs）中。
app = FastAPI(
    title="Image Generation Service API",
    description="Graduation project backend for AI image generation and analysis",
    version="1.1.0"
)

# outputs 目录用于保存运行产物（reverse 结果、generate 图片）。
# 这里把它挂载到 /outputs 静态路由，前端可通过 URL 直接访问文件。
OUTPUTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "outputs"))
os.makedirs(OUTPUTS_DIR, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")

# CORS 跨域配置：允许前端开发端口（5173）访问本服务。
# 这里保留了 "*"，开发阶段方便联调；生产环境通常应收敛白名单。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 支持的文生图后端模式：
# - sd: 本地 Stable Diffusion
# - gemini: Google Gemini 图片生成
# - proxy: 远程代理（OpenAI 兼容接口）
VALID_MODES = {"sd", "gemini", "proxy"}

# 当请求未给出参数时使用的默认生成参数。
DEFAULT_GENERATE_PARAMS = {
    "size": "512x512",
    "steps": 30,
    "cfg": 7.0,
    "sampler": "DPM++ 2M Karras",
    "seed": None,
}

# 风格预设：用于在生成阶段对 structured prompt 或 legacy prompt 注入额外风格词。
# 每个预设包含：
# - blocks: 往 structured 的 style/tech 等块中追加词条
# - prompt_suffix: legacy（纯文本 prompt）场景下追加到正向词尾部
# - negative_terms: 推荐负向词
STYLE_PRESETS: Dict[str, Dict[str, Any]] = {
    "photoreal": {
        "blocks": {
            "style": {
                "medium": ["photo"],
                "aesthetic": ["photorealistic"],
                "quality": ["high detail", "sharp focus"],
            },
            "tech": {
                "lighting": ["natural light"],
                "camera": ["35mm lens"],
                "render": ["realistic textures"],
            },
        },
        "prompt_suffix": "photorealistic, high detail, realistic lighting",
        "negative_terms": ["cartoon", "anime", "3d render"],
    },
    "anime": {
        "blocks": {
            "style": {
                "medium": ["anime illustration"],
                "aesthetic": ["clean lineart"],
                "quality": ["vibrant colors"],
            },
            "tech": {
                "lighting": ["soft cinematic light"],
                "render": ["cel shading"],
            },
        },
        "prompt_suffix": "anime illustration, clean lineart, vibrant colors",
        "negative_terms": ["photorealistic", "grainy", "lowres"],
    },
    "watercolor": {
        "blocks": {
            "style": {
                "medium": ["watercolor painting"],
                "aesthetic": ["soft brush strokes"],
                "quality": ["paper texture"],
            },
            "tech": {
                "color_tone": ["pastel tones"],
                "render": ["traditional media look"],
            },
        },
        "prompt_suffix": "watercolor painting, soft brush strokes, textured paper",
        "negative_terms": ["3d", "hard edges", "oversaturated"],
    },
    "cyberpunk": {
        "blocks": {
            "style": {
                "aesthetic": ["cyberpunk"],
                "quality": ["neon atmosphere"],
            },
            "tech": {
                "lighting": ["neon rim lighting"],
                "color_tone": ["neon magenta and cyan"],
                "render": ["high contrast"],
            },
        },
        "prompt_suffix": "cyberpunk, neon lights, high contrast, futuristic city",
        "negative_terms": ["flat lighting", "washed colors", "monochrome"],
    },
    "ink": {
        "blocks": {
            "style": {
                "medium": ["ink drawing"],
                "aesthetic": ["bold strokes"],
                "quality": ["high contrast black and white"],
            },
            "tech": {
                "render": ["clean contours"],
            },
        },
        "prompt_suffix": "ink drawing, bold strokes, high contrast monochrome",
        "negative_terms": ["blurry", "soft focus", "color noise"],
    },
}


def _ensure_int(value: Any, field_name: str, min_value: int, max_value: int, default: int) -> int:
    """将输入归一化为 int，并做范围校验；空值时回退默认值。"""
    if value is None or value == "":
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}: must be an integer")
    if parsed < min_value or parsed > max_value:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}: must be between {min_value} and {max_value}")
    return parsed


def _ensure_float(value: Any, field_name: str, min_value: float, max_value: float, default: float) -> float:
    """将输入归一化为 float，并做范围校验；空值时回退默认值。"""
    if value is None or value == "":
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}: must be a number")
    if parsed < min_value or parsed > max_value:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}: must be between {min_value} and {max_value}")
    return parsed


def _ensure_size(value: Any, default: str) -> str:
    """
    解析并校验尺寸字符串（WxH）。
    约束：宽高必须是整数且在 [128, 2048] 范围内。
    """
    raw = value if value is not None and value != "" else default
    if not isinstance(raw, str):
        raw = str(raw)

    parts = raw.lower().split("x")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Invalid size: expected format WxH, e.g. 512x512")

    try:
        width = int(parts[0])
        height = int(parts[1])
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid size: width and height must be integers")

    if width < 128 or width > 2048 or height < 128 or height > 2048:
        raise HTTPException(status_code=400, detail="Invalid size: width and height must be between 128 and 2048")

    return f"{width}x{height}"


def _ensure_seed(value: Any) -> Optional[int]:
    """校验随机种子；允许空值（表示不固定 seed）。"""
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid seed: must be an integer")
    if parsed < 0 or parsed > 2 ** 32 - 1:
        raise HTTPException(status_code=400, detail="Invalid seed: must be between 0 and 4294967295")
    return parsed


def _clone_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """深拷贝字典，避免在原结构上原地修改。"""
    return jsonlib.loads(jsonlib.dumps(data, ensure_ascii=False))


def _merge_unique(items: List[str], extra_items: List[str]) -> List[str]:
    """合并两个字符串列表，并保持原顺序去重。"""
    seen = {item for item in items}
    merged = list(items)
    for item in extra_items:
        if item not in seen:
            merged.append(item)
            seen.add(item)
    return merged


def _apply_style_preset_to_structured(structured_data: Dict[str, Any], style_name: Optional[str]):
    """
    将风格预设融合到 structured 数据中。

    处理规则：
    1) 未传 style_name：直接返回原 structured
    2) 预设不存在：抛 400
    3) 对 blocks（style/tech/...）按字段追加并去重
    4) negative.terms 追加预设负向词并去重
    5) params 中仅在原值缺失时补默认
    """
    if not style_name:
        return structured_data, None

    preset = STYLE_PRESETS.get(style_name)
    if not preset:
        raise HTTPException(status_code=400, detail=f"Unsupported style_preset: {style_name}")

    merged = _clone_dict(structured_data)

    # 1) 合并 blocks：把预设词条并入 structured 对应块。
    blocks = preset.get("blocks", {})
    for block_name, block_fields in blocks.items():
        block = merged.get(block_name)
        if not isinstance(block, dict):
            block = {}
            merged[block_name] = block

        for field_name, preset_items in block_fields.items():
            existing = block.get(field_name)
            if isinstance(existing, list):
                block[field_name] = _merge_unique([str(x) for x in existing], [str(x) for x in preset_items])
            elif existing:
                block[field_name] = _merge_unique([str(existing)], [str(x) for x in preset_items])
            else:
                block[field_name] = [str(x) for x in preset_items]

    # 2) 合并负向词。
    negative_terms = [str(x) for x in preset.get("negative_terms", [])]
    negative_block = merged.get("negative")
    if not isinstance(negative_block, dict):
        negative_block = {}
        merged["negative"] = negative_block

    existing_negative = negative_block.get("terms")
    if isinstance(existing_negative, list):
        negative_block["terms"] = _merge_unique([str(x) for x in existing_negative], negative_terms)
    elif existing_negative:
        negative_block["terms"] = _merge_unique([str(existing_negative)], negative_terms)
    else:
        negative_block["terms"] = negative_terms

    # 3) 按“缺省补全”方式合并参数。
    params_block = merged.get("params")
    if not isinstance(params_block, dict):
        params_block = {}
        merged["params"] = params_block

    for key, value in preset.get("params", {}).items():
        if key not in params_block or params_block.get(key) in (None, ""):
            params_block[key] = value

    return merged, style_name


# ------------------------------
# 健康检查接口
# ------------------------------
@app.get("/health")
async def health_check():
    """用于容器探活/服务状态检查。"""
    return {"status": "healthy", "service": "image-generation-api"}


# ------------------------------
# 图生文接口：POST /reverse
# ------------------------------
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
    上传图片并反推出结构化提示词。

    输入：multipart/form-data，字段名 image
    输出：ReverseResponse（caption + structured + prompt + meta）
    """
    # 文件大小上限：10MB。
    max_size = 10 * 1024 * 1024

    # 1) 读取上传内容。
    try:
        image_bytes = await image.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    # 2) 大小校验（过大直接拒绝）。
    if len(image_bytes) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {len(image_bytes)} bytes (max {max_size} bytes)"
        )

    # 3) MIME 类型校验（仅允许常见图片类型）。
    allowed_types = ["image/jpeg", "image/png", "image/webp", "image/jpg"]
    if image.content_type and image.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {image.content_type}. Allowed: {allowed_types}"
        )

    # 4) 调用图生文核心服务。
    try:
        result = await reverse_service.reverse_image(image_bytes)
        return result

    # 输入不合法 -> 400。
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 其他异常 -> 500。
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal processing error: {str(e)}"
        )


# ------------------------------
# 文生图接口：POST /generate
# ------------------------------
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
    strict_json: bool = Form(False),
    mode: Optional[str] = Form(None),
    style_preset: Optional[str] = Form(None),
    seed: Optional[int] = Form(None),
    steps: Optional[int] = Form(None),
    cfg: Optional[float] = Form(None),
    sampler: Optional[str] = Form(None),
    size: Optional[str] = Form(None),
    negative_prompt: Optional[str] = Form(None),
):
    """
    上传 JSON 规范并生成图片。

    入参来源：
    1) json 文件（主输入）
    2) 表单参数（可覆盖 JSON 中的同名配置）

    主要逻辑：
    - 校验上传文件与 JSON
    - 合并并归一化生成参数（size/steps/cfg/sampler/seed/mode/style）
    - 选择 prompt 来源（structured / legacy / json_spec）
    - 调用 banana_service 生成图片
    - 组装标准化响应（包含可复现性和生效参数）
    """
    # JSON 上传大小上限：1MB。
    max_size = 1 * 1024 * 1024

    # 1) 基础文件类型校验。
    if json_file.content_type and json_file.content_type not in ["application/json", "text/json"]:
        raise HTTPException(status_code=400, detail="Unsupported file type. Please upload JSON.")

    # 2) 读取上传内容。
    try:
        raw_bytes = await json_file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    # 3) 文件大小校验。
    if len(raw_bytes) > max_size:
        raise HTTPException(status_code=413, detail=f"File too large: {len(raw_bytes)} bytes (max {max_size} bytes)")

    # 4) 解析 JSON。
    try:
        data = jsonlib.loads(raw_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON content")

    # 根节点必须是对象，便于后续按键读取。
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="JSON root must be an object")

    # structured 若存在，必须是对象。
    structured_input = data.get("structured")
    if structured_input is not None and not isinstance(structured_input, dict):
        raise HTTPException(status_code=400, detail="structured must be an object when provided")

    # mode 优先级：表单 > JSON > None。
    effective_mode = (mode or data.get("mode") or "").strip().lower() or None
    if effective_mode and effective_mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Unsupported mode: {effective_mode}. Allowed: {sorted(VALID_MODES)}")

    # style 优先级：表单 style_preset > JSON style_preset/stylePreset。
    style_from_json = data.get("style_preset") or data.get("stylePreset")
    effective_style = (style_preset or style_from_json or "").strip() or None
    if effective_style and effective_style not in STYLE_PRESETS:
        raise HTTPException(status_code=400, detail=f"Unsupported style_preset: {effective_style}")

    # 从 structured.params 提取候选参数（若存在）。
    structured_params: Dict[str, Any] = {}
    if isinstance(structured_input, dict):
        raw_params = structured_input.get("params")
        if isinstance(raw_params, dict):
            structured_params = raw_params

    # 5) 参数归一化（表单覆盖 structured.params，再回退默认值）。
    effective_size = _ensure_size(size if size is not None else structured_params.get("size"), DEFAULT_GENERATE_PARAMS["size"])
    effective_steps = _ensure_int(steps if steps is not None else structured_params.get("steps"), "steps", 1, 150, DEFAULT_GENERATE_PARAMS["steps"])
    effective_cfg = _ensure_float(cfg if cfg is not None else structured_params.get("cfg"), "cfg", 1.0, 30.0, DEFAULT_GENERATE_PARAMS["cfg"])
    effective_sampler = (sampler if sampler is not None else structured_params.get("sampler") or DEFAULT_GENERATE_PARAMS["sampler"])
    effective_sampler = str(effective_sampler).strip() or DEFAULT_GENERATE_PARAMS["sampler"]
    effective_seed = _ensure_seed(seed if seed is not None else structured_params.get("seed"))

    # prompt_source 用于告诉前端“这次生成到底用了哪种 prompt 来源”。
    prompt_source = "legacy"
    style_applied = None
    compiled_negative = ""

    # 6) 生成正向词：structured 模式优先。
    if isinstance(structured_input, dict):
        # 6.1 把风格预设融合进 structured。
        structured_for_compile, style_applied = _apply_style_preset_to_structured(structured_input, effective_style)
        # 6.2 用当前生效参数构造 ParamsBlock，确保编译链路参数一致。
        params_obj = ParamsBlock(
            size=effective_size,
            steps=effective_steps,
            cfg=effective_cfg,
            sampler=effective_sampler,
            seed=effective_seed,
        )
        # 6.3 借用 reverse_service 的结构化构建与编译能力（复用一套规则）。
        structured_obj = reverse_service._build_structured_prompt(structured_for_compile, params_obj)
        compiled = reverse_service.compile_structured_prompt(structured_obj)
        positive_prompt = (compiled.get("positive") or "").strip()
        compiled_negative = (compiled.get("negative") or "").strip()
        prompt_source = "structured"
    else:
        # legacy：直接用 prompt 或 caption。
        positive_prompt = (data.get("prompt") or data.get("caption") or "").strip()
        # 若设置风格预设，在 legacy 下通过 suffix + negative_terms 注入。
        if effective_style:
            preset = STYLE_PRESETS[effective_style]
            style_applied = effective_style
            suffix = str(preset.get("prompt_suffix", "")).strip()
            if suffix:
                positive_prompt = f"{positive_prompt}, {suffix}" if positive_prompt else suffix
            negative_terms = [str(x) for x in preset.get("negative_terms", [])]
            compiled_negative = ", ".join(negative_terms)

    # 7) 负向词优先级：表单 negative_prompt > JSON negative_prompt > 编译结果。
    json_negative = data.get("negative_prompt")
    if json_negative is not None and not isinstance(json_negative, str):
        json_negative = str(json_negative)

    effective_negative = (negative_prompt if negative_prompt is not None else json_negative if json_negative is not None else compiled_negative)
    effective_negative = (effective_negative or "").strip()

    # 8) 如果仍没有正向 prompt：退化为“按 JSON 规范生成”的指令提示。
    # strict_json=True 时直接把 JSON 当 prompt；否则包一层自然语言指令。
    if not positive_prompt:
        json_spec_compact = jsonlib.dumps(data, ensure_ascii=False, separators=(",", ":"))
        if strict_json:
            positive_prompt = json_spec_compact
        else:
            positive_prompt = (
                "Generate one image strictly based on this JSON specification. "
                "Use all fields as constraints when present.\nJSON:\n"
                f"{json_spec_compact}"
            )
        prompt_source = "json_spec"

    # 9) 生成输出路径（按 uuid 命名，避免冲突）。
    output_dir = os.path.abspath(os.path.join(OUTPUTS_DIR, "generate"))
    os.makedirs(output_dir, exist_ok=True)
    generation_id = uuid.uuid4().hex
    output_path = os.path.join(output_dir, f"{generation_id}.png")

    # 10) 调用底层生成服务。
    start_time = time.time()
    try:
        result = banana_service.generate(
            positive_prompt,
            output_path,
            mode=effective_mode,
            negative_prompt=effective_negative or None,
            seed=effective_seed,
            steps=effective_steps,
            cfg=effective_cfg,
            sampler=effective_sampler,
            size=effective_size,
        )
        if not result:
            raise RuntimeError("No image generated")
        mode_info = banana_service.get_mode_info(mode=effective_mode)
    except HTTPException:
        # 已经是标准 HTTP 异常，直接透传。
        raise
    except ValueError as e:
        # 参数/业务校验错误统一映射为 400。
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # 其余异常统一映射为 500。
        raise HTTPException(status_code=500, detail=f"Generation error: {str(e)}")

    # 11) 构造返回元信息。
    processing_time_ms = max(1, int((time.time() - start_time) * 1000))
    image_url = f"/outputs/generate/{generation_id}.png"

    # 复现等级：只有 SD 且固定了 seed 时，可认为强复现。
    reproducibility = "best_effort"
    if mode_info.get("mode") == "sd" and effective_seed is not None:
        reproducibility = "strong"

    # 12) 按约定 schema 返回。
    response = GenerateResponse(
        id=generation_id,
        prompt=positive_prompt or "[json-spec]",
        image_url=image_url,
        meta=GenerateMeta(
            model_used=mode_info["model_used"],
            processing_time_ms=processing_time_ms,
            mode=mode_info.get("mode"),
            reproducibility=reproducibility,
            style_applied=style_applied,
            effective_params={
                "mode": mode_info.get("mode"),
                "size": effective_size,
                "steps": effective_steps,
                "cfg": effective_cfg,
                "sampler": effective_sampler,
                "seed": effective_seed,
                "has_negative_prompt": bool(effective_negative),
            },
            prompt_source=prompt_source,
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
