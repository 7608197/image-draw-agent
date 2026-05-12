import os
import requests
import json
import traceback
import socket
from pathlib import Path
from PIL import Image
from io import BytesIO
import base64

# Dual-mode imports
try:
    import torch
except ImportError:
    torch = None

try:
    from diffusers import StableDiffusionPipeline
except ImportError:
    StableDiffusionPipeline = None

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

import io
from typing import Any, Dict, Optional, Set, Tuple
from requests.exceptions import ConnectionError as RequestsConnectionError, ConnectTimeout, ReadTimeout

try:
    from .image_response_parser import extract_image_source, extract_urls_from_text
except ImportError:
    from services.image_response_parser import extract_image_source, extract_urls_from_text

# --- 配置区域 ---
# 模式选择: "sd" (本地Stable Diffusion), "gemini" (Google Gemini API), "proxy" (远程代理)
DEFAULT_MODE = os.getenv("IMAGE_GEN_MODE", "sd")  # 默认使用本地SD

# Google Gemini API 配置
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "imagen-3.0-generate-001")

# 远程代理配置
IMAGE_GEN_MODEL = os.getenv("IMAGE_GEN_MODEL", "gemini-3.0-pro-image-landscape-2k")
IMAGE_GEN_BASE_URL = os.getenv("IMAGE_GEN_BASE_URL", "http://127.0.0.1:38000/v1")
IMAGE_GEN_API_KEY = os.getenv("IMAGE_GEN_API_KEY", "")

PROXY_URL = os.getenv("PROXY_URL", f"{IMAGE_GEN_BASE_URL.rstrip('/')}/chat/completions")
PROXY_API_KEY = os.getenv("PROXY_API_KEY", IMAGE_GEN_API_KEY)
REMOTE_MODEL_NAME = os.getenv("REMOTE_MODEL_NAME", IMAGE_GEN_MODEL)

# 本地 Stable Diffusion 配置
SD_MODEL_ID = os.getenv("SD_MODEL_ID", "stabilityai/sd-turbo")
SD_TURBO_RECOMMENDED_SIZE = os.getenv("SD_TURBO_RECOMMENDED_SIZE", "512x512")
SD_TURBO_RECOMMENDED_STEPS = int(os.getenv("SD_TURBO_RECOMMENDED_STEPS", "4"))
SD_TURBO_RECOMMENDED_CFG = float(os.getenv("SD_TURBO_RECOMMENDED_CFG", "1.5"))
HUGGINGFACE_HUB_CACHE = Path(os.getenv("HUGGINGFACE_HUB_CACHE", Path.home() / ".cache" / "huggingface" / "hub"))

# 失败回退配置
IMAGE_GEN_FALLBACK_ENABLED = os.getenv("IMAGE_GEN_FALLBACK_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}
IMAGE_GEN_FALLBACK_TARGET = os.getenv("IMAGE_GEN_FALLBACK_TARGET", "sd").strip().lower() or "sd"
IMAGE_GEN_FALLBACK_FROM = {
    item.strip().lower()
    for item in os.getenv("IMAGE_GEN_FALLBACK_FROM", "gemini,proxy").split(",")
    if item.strip()
}
PROXY_CONNECT_TIMEOUT_SECONDS = float(os.getenv("PROXY_CONNECT_TIMEOUT_SECONDS", "5"))
PROXY_READ_TIMEOUT_SECONDS = float(os.getenv("PROXY_READ_TIMEOUT_SECONDS", "20"))


class BananaService:
    def __init__(self, default_mode: str = None):
        """
        初始化 BananaService (支持三种模式)
        :param default_mode: 'sd', 'gemini', 'proxy' 或 None (使用环境变量)
        """
        self.mode = default_mode or DEFAULT_MODE
        self.device = "cuda" if (torch is not None and torch.cuda.is_available()) else "cpu"

        # 懒加载模型
        self.sd_pipe = None
        self.gemini_client = None

        print(f"[BananaService] 初始化完成")
        print(f"[BananaService] 默认模式: {self.mode}")
        print(f"[BananaService] 计算设备: {self.device}")

    def _resolve_cached_model_path(self) -> Optional[Path]:
        repo_dir = HUGGINGFACE_HUB_CACHE / f"models--{SD_MODEL_ID.replace('/', '--')}"
        snapshots_dir = repo_dir / "snapshots"
        if not snapshots_dir.exists():
            return None

        snapshots = sorted((p for p in snapshots_dir.iterdir() if p.is_dir()), reverse=True)
        for snapshot in snapshots:
            required_paths = [
                snapshot / "model_index.json",
                snapshot / "text_encoder",
                snapshot / "tokenizer",
                snapshot / "unet",
                snapshot / "vae",
            ]
            if all(path.exists() for path in required_paths):
                return snapshot
        return None

    def load_sd_model(self):
        """加载本地 Stable Diffusion 模型 (懒加载)"""
        if self.sd_pipe is not None:
            return self.sd_pipe

        if torch is None or StableDiffusionPipeline is None:
            raise ImportError("SD 模式需要安装 torch 和 diffusers 依赖")

        print(f"[BananaService] 正在加载本地 Stable Diffusion 模型: {SD_MODEL_ID}")
        cached_model_path = self._resolve_cached_model_path()
        if cached_model_path is None:
            raise RuntimeError(
                f"本地 SD 模型不可用：未找到 {SD_MODEL_ID} 的本地缓存。"
                "当前不会再尝试联网下载，请先恢复 Hugging Face 缓存或改用可用模式。"
            )

        print(f"[BananaService] 使用本地缓存模型: {cached_model_path}")
        try:
            self.sd_pipe = StableDiffusionPipeline.from_pretrained(
                str(cached_model_path),
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                local_files_only=True,
            )
        except Exception as exc:
            message = str(exc)
            timeout_like = isinstance(exc, TimeoutError) or isinstance(exc, socket.timeout) or 'ConnectTimeout' in message or 'timed out' in message
            if timeout_like:
                raise RuntimeError(
                    f"本地 SD 模型加载失败：无法连接到 Hugging Face 下载 {SD_MODEL_ID}。"
                    "如果你之前能本地生图，通常说明当前网络不可达，或模型缓存已丢失。"
                ) from exc
            raise RuntimeError(f"本地 SD 模型加载失败：{message}") from exc
        self.sd_pipe.to(self.device)
        print(f"[BananaService] 本地 SD 模型加载完毕！(设备: {self.device})")
        return self.sd_pipe

    def _parse_size(self, size: Optional[str]) -> Optional[Tuple[int, int]]:
        if not size:
            return None
        parts = str(size).lower().split("x")
        if len(parts) != 2:
            raise ValueError("size 格式必须为 WxH，例如 512x512")
        width = int(parts[0])
        height = int(parts[1])
        if width <= 0 or height <= 0:
            raise ValueError("size 宽高必须为正整数")
        return width, height

    def generate_with_sd(
        self,
        prompt: str,
        output_path: str,
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        steps: Optional[int] = None,
        cfg: Optional[float] = None,
        sampler: Optional[str] = None,
        size: Optional[str] = None,
    ):
        """使用本地 Stable Diffusion 生成图片"""
        print(f"[BananaService] [SD模式] 开始生成")
        print(f"[BananaService] Prompt: {prompt}")

        try:
            pipe = self.load_sd_model()
            call_kwargs = {}
            is_sd_turbo = SD_MODEL_ID.strip().lower() == "stabilityai/sd-turbo"

            if negative_prompt:
                call_kwargs["negative_prompt"] = negative_prompt
            if seed is not None and torch is not None:
                call_kwargs["generator"] = torch.Generator(device=self.device).manual_seed(int(seed))

            effective_steps = int(steps) if steps is not None else None
            effective_cfg = float(cfg) if cfg is not None else None
            effective_size = size

            if is_sd_turbo:
                effective_steps = effective_steps if effective_steps is not None and effective_steps <= 8 else SD_TURBO_RECOMMENDED_STEPS
                effective_cfg = effective_cfg if effective_cfg is not None and effective_cfg <= 3.0 else SD_TURBO_RECOMMENDED_CFG
                effective_size = effective_size or SD_TURBO_RECOMMENDED_SIZE
                print(
                    f"[BananaService] [SD模式] 检测到 sd-turbo，使用兼容参数: "
                    f"steps={effective_steps}, cfg={effective_cfg}, size={effective_size}"
                )

            if effective_steps is not None:
                call_kwargs["num_inference_steps"] = effective_steps
            if effective_cfg is not None:
                call_kwargs["guidance_scale"] = effective_cfg

            parsed_size = self._parse_size(effective_size)
            if parsed_size:
                call_kwargs["width"], call_kwargs["height"] = parsed_size

            if sampler:
                print(f"[BananaService] [SD模式] 当前调度器: {pipe.scheduler.__class__.__name__} (请求 sampler={sampler}，本地 SD 暂未切换 scheduler)")

            image = pipe(prompt, **call_kwargs).images[0]

            # 确保目录存在
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            image.save(output_path)
            print(f"[BananaService] [SUCCESS] SD生成完成: {output_path}")
            return output_path

        except Exception as e:
            print(f"[BananaService] [ERROR] SD生成失败: {e}")
            print(traceback.format_exc())
            raise RuntimeError(f"本地 SD 生成失败：{e}") from e

    def generate_with_gemini(
        self,
        prompt: str,
        output_path: str,
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        steps: Optional[int] = None,
        cfg: Optional[float] = None,
        sampler: Optional[str] = None,
        size: Optional[str] = None,
    ):
        """使用 Google Gemini API 生成图片"""
        print(f"[BananaService] [Gemini模式] 开始生成")
        print(f"[BananaService] Prompt: {prompt}")

        try:
            if genai is None or types is None:
                raise ImportError("Gemini 模式需要安装 google-genai 依赖")

            # 初始化 Gemini 客户端
            if not self.gemini_client:
                if "你的_API_KEY" in GEMINI_API_KEY:
                    raise ValueError("请先设置 GEMINI_API_KEY 环境变量或在代码中填入有效的 API Key！")
                self.gemini_client = genai.Client(api_key=GEMINI_API_KEY)
                print(f"[BananaService] Gemini 客户端初始化完成")

            # 调用 Gemini Imagen API
            print(f"[BananaService] 正在调用 Gemini API (模型: {GEMINI_MODEL})...")
            response = self.gemini_client.models.generate_image(
                model=GEMINI_MODEL,
                prompt=prompt,
                config=types.GenerateImageConfig(
                    number_of_images=1,
                )
            )

            if response.generated_images:
                generated_image = response.generated_images[0]
                image = Image.open(io.BytesIO(generated_image.image.image_bytes))

                # 确保目录存在
                os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                image.save(output_path)
                print(f"[BananaService] [SUCCESS] Gemini生成完成: {output_path}")
                return output_path
            else:
                raise ValueError("Gemini API 未返回任何图片")

        except Exception as e:
            print(f"[BananaService] [ERROR] Gemini生成失败: {e}")
            print(traceback.format_exc())
            raise

    def _resolve_model_name(self, mode: str) -> str:
        if mode == "sd":
            return SD_MODEL_ID
        if mode == "gemini":
            return GEMINI_MODEL
        if mode == "proxy":
            return REMOTE_MODEL_NAME
        raise ValueError(f"不支持的生成模式: {mode}")

    def _run_mode(
        self,
        active_mode: str,
        prompt: str,
        output_path: str,
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        steps: Optional[int] = None,
        cfg: Optional[float] = None,
        sampler: Optional[str] = None,
        size: Optional[str] = None,
    ) -> str:
        if active_mode == "sd":
            return self.generate_with_sd(
                prompt,
                output_path,
                negative_prompt=negative_prompt,
                seed=seed,
                steps=steps,
                cfg=cfg,
                sampler=sampler,
                size=size,
            )
        if active_mode == "gemini":
            return self.generate_with_gemini(
                prompt,
                output_path,
                negative_prompt=negative_prompt,
                seed=seed,
                steps=steps,
                cfg=cfg,
                sampler=sampler,
                size=size,
            )
        if active_mode == "proxy":
            return self.generate_with_proxy(
                prompt,
                output_path,
                negative_prompt=negative_prompt,
                seed=seed,
                steps=steps,
                cfg=cfg,
                sampler=sampler,
                size=size,
            )
        raise ValueError(f"不支持的生成模式: {active_mode}。支持的模式: 'sd', 'gemini', 'proxy'")

    def get_mode_info(self, mode: str = None) -> dict:
        """Return active mode and model identifier."""
        active_mode = mode or self.mode
        return {
            "mode": active_mode,
            "model_used": self._resolve_model_name(active_mode),
        }

    def generate(
        self,
        prompt: str,
        output_path: str,
        mode: str = None,
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        steps: Optional[int] = None,
        cfg: Optional[float] = None,
        sampler: Optional[str] = None,
        size: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        统一生成接口 (支持三种模式)
        :param prompt: 生成提示词
        :param output_path: 输出图片路径
        :param mode: 'sd' (本地), 'gemini' (Google API), 'proxy' (远程代理), None (使用默认模式)
        :return: 生成结果及实际后端元信息
        """
        requested_mode = mode
        active_mode = requested_mode or self.mode

        print(f"\n[BananaService] ========== 开始生成任务 ==========")
        print(f"[BananaService] 模式: {active_mode}")
        print(f"[BananaService] Prompt: {prompt}")
        print(f"[BananaService] 输出路径: {output_path}")

        try:
            result_path = self._run_mode(
                active_mode,
                prompt,
                output_path,
                negative_prompt=negative_prompt,
                seed=seed,
                steps=steps,
                cfg=cfg,
                sampler=sampler,
                size=size,
            )
            return {
                "output_path": result_path,
                "requested_mode": requested_mode,
                "actual_mode": active_mode,
                "model_used": self._resolve_model_name(active_mode),
                "fallback_used": False,
                "fallback_from": None,
            }
        except Exception as primary_error:
            fallback_allowed = (
                IMAGE_GEN_FALLBACK_ENABLED
                and active_mode in IMAGE_GEN_FALLBACK_FROM
                and active_mode != IMAGE_GEN_FALLBACK_TARGET
            )
            if not fallback_allowed:
                print(f"[BananaService] [FATAL] 生成任务失败: {str(primary_error)}")
                raise

            print(
                f"[BananaService] [WARN] {active_mode} 生成失败，尝试回退到 {IMAGE_GEN_FALLBACK_TARGET}: {primary_error}"
            )
            try:
                result_path = self._run_mode(
                    IMAGE_GEN_FALLBACK_TARGET,
                    prompt,
                    output_path,
                    negative_prompt=negative_prompt,
                    seed=seed,
                    steps=steps,
                    cfg=cfg,
                    sampler=sampler,
                    size=size,
                )
                return {
                    "output_path": result_path,
                    "requested_mode": requested_mode,
                    "actual_mode": IMAGE_GEN_FALLBACK_TARGET,
                    "model_used": self._resolve_model_name(IMAGE_GEN_FALLBACK_TARGET),
                    "fallback_used": True,
                    "fallback_from": active_mode,
                }
            except Exception as fallback_error:
                print(f"[BananaService] [FATAL] 回退生成失败: {fallback_error}")
                raise fallback_error from primary_error

    def _save_data_url(self, data_url: str, output_path: str):
        if not isinstance(data_url, str) or not data_url.startswith("data:image"):
            raise ValueError("无效的 data URL 图片数据")
        try:
            _, encoded = data_url.split(",", 1)
            binary = base64.b64decode(encoded)
            image = Image.open(BytesIO(binary))
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            image.save(output_path)
            print(f"[BananaService] [SUCCESS] Base64图片已保存至: {output_path}")
            return output_path
        except Exception as e:
            raise RuntimeError(f"Base64 图片保存失败: {e}") from e

    def _download_or_save(self, image_source: str, output_path: str):
        if not isinstance(image_source, str) or not image_source:
            raise ValueError("图片来源为空")
        if image_source.startswith("data:image"):
            return self._save_data_url(image_source, output_path)

        print(f"[BananaService] 正在下载图片: {image_source[:200]}")
        img_res = requests.get(image_source, timeout=60)
        if img_res.status_code != 200:
            raise RuntimeError(f"图片下载失败: {img_res.status_code}")

        image = Image.open(BytesIO(img_res.content))
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        image.save(output_path)
        print(f"[BananaService] [SUCCESS] 图片已下载并保存至: {output_path}")
        return output_path

    def _extract_stream_image_source(self, delta: dict):
        if not isinstance(delta, dict):
            return None

        images = delta.get("images")
        if isinstance(images, list):
            for image_data in images:
                if not isinstance(image_data, dict):
                    continue

                image_url = image_data.get("image_url")
                if isinstance(image_url, dict):
                    url = image_url.get("url")
                    if isinstance(url, str):
                        return url
                elif isinstance(image_url, str):
                    return image_url

                image_obj = image_data.get("image")
                if isinstance(image_obj, dict):
                    url = image_obj.get("url")
                    if isinstance(url, str):
                        return url
                    b64_json = image_obj.get("b64_json") or image_obj.get("base64")
                    if isinstance(b64_json, str):
                        return f"data:image/png;base64,{b64_json}"

                b64_json = image_data.get("b64_json") or image_data.get("base64")
                if isinstance(b64_json, str):
                    return f"data:image/png;base64,{b64_json}"

        wrapped = {
            "choices": [
                {
                    "message": {
                        "images": delta.get("images"),
                        "content": delta.get("content"),
                    }
                }
            ]
        }
        return extract_image_source(wrapped)

    def _write_debug_response(self, output_path: str, payload):
        try:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            debug_path = os.path.join(os.path.dirname(output_path), "last_response.json")
            with open(debug_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"[BananaService] 已保存原始响应: {debug_path}")
        except Exception as debug_err:
            print(f"[BananaService] [WARN] 保存响应失败: {debug_err}")

    def generate_with_proxy(
        self,
        prompt: str,
        output_path: str,
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        steps: Optional[int] = None,
        cfg: Optional[float] = None,
        sampler: Optional[str] = None,
        size: Optional[str] = None,
    ):
        """使用远程代理 (OpenAI API 兼容) 生成图片"""
        print(f"[BananaService] [Proxy模式] 开始生成")

        headers = {
            "Authorization": f"Bearer {PROXY_API_KEY}",
            "Content-Type": "application/json",
        }

        chat_url = PROXY_URL.rstrip("/")
        if chat_url.endswith("/chat/completions"):
            base_url = chat_url[: -len("/chat/completions")]
        else:
            base_url = IMAGE_GEN_BASE_URL.rstrip("/")
            chat_url = f"{base_url}/chat/completions"
        responses_url = f"{base_url}/responses"

        user_content = f"Draw an image of: {prompt}"
        if negative_prompt:
            user_content += f"\nNegative prompt: {negative_prompt}"
        if size:
            user_content += f"\nSize: {size}"
        if seed is not None:
            user_content += f"\nSeed: {seed}"
        if steps is not None:
            user_content += f"\nSteps: {steps}"
        if cfg is not None:
            user_content += f"\nCFG: {cfg}"
        if sampler:
            user_content += f"\nSampler: {sampler}"

        responses_payload = {
            "model": REMOTE_MODEL_NAME,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": user_content}
                    ],
                }
            ],
        }

        chat_payload = {
            "model": REMOTE_MODEL_NAME,
            "messages": [
                {"role": "user", "content": user_content}
            ],
            "stream": True,
        }

        responses_status = None
        responses_preview = ""
        responses_result = None
        chat_status = None
        stream_preview = ""
        stream_events = []

        try:
            print(f"[BananaService] 优先请求 /responses: {responses_url}")
            try:
                response = requests.post(
                    responses_url,
                    headers=headers,
                    json=responses_payload,
                    timeout=(PROXY_CONNECT_TIMEOUT_SECONDS, PROXY_READ_TIMEOUT_SECONDS),
                )
                responses_status = response.status_code
                responses_preview = (response.text or "")[:4000]
                print(f"[BananaService] /responses 状态码: {responses_status}")

                if responses_status == 200:
                    responses_result = response.json()
                    image_source = extract_image_source(responses_result)
                    if image_source:
                        print("[BananaService] /responses 提取到结构化图片来源")
                        return self._download_or_save(image_source, output_path)

                    output_text = responses_result.get("output_text") if isinstance(responses_result, dict) else ""
                    urls = extract_urls_from_text(output_text or "")
                    if urls:
                        print("[BananaService] /responses 从 output_text 提取到 URL")
                        return self._download_or_save(urls[0], output_path)

                    print("[BananaService] [WARN] /responses 返回成功但无可用图片，回退到 /chat/completions")
                else:
                    print("[BananaService] [WARN] /responses endpoint 不支持或请求失败，回退到 /chat/completions")
            except (RequestsConnectionError, ConnectTimeout, ReadTimeout) as responses_err:
                print(f"[BananaService] [WARN] /responses 调用异常，回退到 /chat/completions: {responses_err}")
                responses_preview = f"proxy_unreachable: {responses_err}"
            except Exception as responses_err:
                print(f"[BananaService] [WARN] /responses 调用异常，回退到 /chat/completions: {responses_err}")

            print(f"[BananaService] 回退请求 /chat/completions (stream): {chat_url}")
            try:
                response = requests.post(
                    chat_url,
                    headers=headers,
                    json=chat_payload,
                    timeout=(PROXY_CONNECT_TIMEOUT_SECONDS, PROXY_READ_TIMEOUT_SECONDS),
                    stream=True,
                )
            except (RequestsConnectionError, ConnectTimeout, ReadTimeout) as exc:
                raise RuntimeError(
                    f"远程 proxy 不可用：无法连接到 {chat_url}。"
                    "请先启动代理服务，或在前端把生成模式切到默认/本地 sd。"
                ) from exc
            chat_status = response.status_code
            print(f"[BananaService] /chat/completions 状态码: {chat_status}")

            if chat_status != 200:
                err_preview = (response.text or "")[:4000]
                self._write_debug_response(output_path, {
                    "error": "chat endpoint unavailable",
                    "responses_status": responses_status,
                    "responses_preview": responses_preview,
                    "chat_status": chat_status,
                    "chat_preview": err_preview,
                })
                raise RuntimeError(f"chat/completions endpoint 不可用: {chat_status}")

            full_content_parts = []
            print("[BananaService] 正在接收流式响应...")
            for line in response.iter_lines():
                if not line:
                    continue

                try:
                    decoded_line = line.decode("utf-8").strip()
                except UnicodeDecodeError:
                    continue

                if decoded_line.startswith("data: "):
                    data_str = decoded_line[6:]
                    if data_str == "[DONE]":
                        break

                    try:
                        data_json = json.loads(data_str)
                    except json.JSONDecodeError:
                        if "data: [DONE]" in data_str:
                            data_prefix = data_str.split("data: [DONE]", 1)[0].strip()
                            try:
                                data_json = json.loads(data_prefix)
                            except json.JSONDecodeError:
                                continue
                        else:
                            continue

                    if len(stream_events) < 200:
                        stream_events.append(data_json)

                    if isinstance(data_json, dict) and "error" in data_json:
                        err_msg = data_json.get("error", {}).get("message", "未知错误")
                        self._write_debug_response(output_path, {
                            "error": "stream data error payload",
                            "responses_status": responses_status,
                            "responses_preview": responses_preview,
                            "responses_result": responses_result,
                            "chat_status": chat_status,
                            "stream_preview": "".join(full_content_parts),
                            "stream_error": data_json,
                        })
                        raise ValueError(f"服务端错误: {err_msg}")

                    source = extract_image_source(data_json)
                    if source:
                        print("[BananaService] 在 stream 事件中提取到结构化图片来源")
                        return self._download_or_save(source, output_path)

                    choices = data_json.get("choices")
                    if isinstance(choices, list) and choices:
                        first = choices[0] if isinstance(choices[0], dict) else {}
                        delta = first.get("delta", {}) if isinstance(first, dict) else {}

                        stream_source = self._extract_stream_image_source(delta)
                        if stream_source:
                            print("[BananaService] 在 stream delta.images 中提取到图片来源")
                            return self._download_or_save(stream_source, output_path)

                        content_part = delta.get("content") if isinstance(delta, dict) else None
                        if isinstance(content_part, str):
                            full_content_parts.append(content_part)
                        elif isinstance(content_part, list):
                            for part in content_part:
                                if isinstance(part, dict):
                                    text = part.get("text")
                                    if isinstance(text, str):
                                        full_content_parts.append(text)

                        reasoning = delta.get("reasoning_content") if isinstance(delta, dict) else None
                        if isinstance(reasoning, str) and "Failed to obtain reCAPTCHA token" in reasoning:
                            self._write_debug_response(output_path, {
                                "error": "stream reasoning recaptcha",
                                "responses_status": responses_status,
                                "responses_preview": responses_preview,
                                "responses_result": responses_result,
                                "chat_status": chat_status,
                                "stream_preview": "".join(full_content_parts),
                                "last_stream_event": data_json,
                            })
                            raise ValueError("服务端错误: Failed to obtain reCAPTCHA token")

                elif decoded_line.startswith('{"error":'):
                    err_line = decoded_line
                    if "data: [DONE]" in err_line:
                        err_line = err_line.split("data: [DONE]", 1)[0].strip()
                    try:
                        err_json = json.loads(err_line)
                    except json.JSONDecodeError:
                        self._write_debug_response(output_path, {
                            "error": "stream error payload parse failed",
                            "responses_status": responses_status,
                            "responses_preview": responses_preview,
                            "responses_result": responses_result,
                            "chat_status": chat_status,
                            "stream_preview": "".join(full_content_parts),
                            "raw_stream_error_line": decoded_line,
                        })
                        raise ValueError("服务端错误: 流式错误载荷解析失败")

                    err_msg = err_json.get("error", {}).get("message", "未知错误")
                    self._write_debug_response(output_path, {
                        "error": "stream error payload",
                        "responses_status": responses_status,
                        "responses_preview": responses_preview,
                        "responses_result": responses_result,
                        "chat_status": chat_status,
                        "stream_preview": "".join(full_content_parts),
                        "stream_error": err_json,
                    })
                    raise ValueError(f"服务端错误: {err_msg}")

            stream_preview = "".join(full_content_parts)
            urls = extract_urls_from_text(stream_preview)
            if urls:
                print("[BananaService] 从 stream 文本中提取到 URL")
                return self._download_or_save(urls[0], output_path)

            self._write_debug_response(output_path, {
                "error": "stream no image",
                "responses_status": responses_status,
                "responses_preview": responses_preview,
                "responses_result": responses_result,
                "chat_status": chat_status,
                "stream_preview": stream_preview,
                "stream_events": stream_events,
            })
            raise ValueError("stream 内容无图或返回结构变更，未提取到可用图片")

        except Exception as e:
            print(f"[BananaService] [EXCEPTION] 发生异常: {str(e)}")
            print(traceback.format_exc())
            raise RuntimeError(f"远程 proxy 生成失败：{e}") from e


# 全局单例 (默认使用环境变量配置的模式)
banana_service = BananaService()
