import os
import requests
import json
import traceback
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

try:
    from .image_response_parser import extract_image_source, extract_urls_from_text
except ImportError:
    from services.image_response_parser import extract_image_source, extract_urls_from_text

# --- 配置区域 ---
# 模式选择: "sd" (本地Stable Diffusion), "gemini" (Google Gemini API), "proxy" (远程代理)
DEFAULT_MODE = os.getenv("IMAGE_GEN_MODE", "sd")  # 默认使用本地SD

# Google Gemini API 配置
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "你的_API_KEY_填在这里")
GEMINI_MODEL = "imagen-3.0-generate-001"

# 远程代理配置 (Flow2 写死)
IMAGE_GEN_MODEL = "gemini-3.0-pro-image-landscape-2k"
IMAGE_GEN_BASE_URL = "http://192.168.1.110:38000/v1"
IMAGE_GEN_API_KEY = "han1234"

PROXY_URL = "http://192.168.1.110:38000/v1/chat/completions"
PROXY_API_KEY = "han1234"
REMOTE_MODEL_NAME = "gemini-3.0-pro-image-landscape-2k"

# 本地 Stable Diffusion 配置
SD_MODEL_ID = os.getenv("SD_MODEL_ID", "runwayml/stable-diffusion-v1-5")


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

    def load_sd_model(self):
        """加载本地 Stable Diffusion 模型 (懒加载)"""
        if self.sd_pipe is not None:
            return self.sd_pipe

        if torch is None or StableDiffusionPipeline is None:
            raise ImportError("SD 模式需要安装 torch 和 diffusers 依赖")

        print(f"[BananaService] 正在加载本地 Stable Diffusion 模型: {SD_MODEL_ID}")
        self.sd_pipe = StableDiffusionPipeline.from_pretrained(
            SD_MODEL_ID,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32
        )
        self.sd_pipe.to(self.device)
        print(f"[BananaService] 本地 SD 模型加载完毕！(设备: {self.device})")
        return self.sd_pipe

    def generate_with_sd(self, prompt: str, output_path: str):
        """使用本地 Stable Diffusion 生成图片"""
        print(f"[BananaService] [SD模式] 开始生成")
        print(f"[BananaService] Prompt: {prompt}")

        try:
            pipe = self.load_sd_model()
            image = pipe(prompt).images[0]

            # 确保目录存在
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            image.save(output_path)
            print(f"[BananaService] [SUCCESS] SD生成完成: {output_path}")
            return output_path

        except Exception as e:
            print(f"[BananaService] [ERROR] SD生成失败: {e}")
            print(traceback.format_exc())
            raise

    def generate_with_gemini(self, prompt: str, output_path: str):
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

    def generate(self, prompt: str, output_path: str, mode: str = None):
        """
        统一生成接口 (支持三种模式)
        :param prompt: 生成提示词
        :param output_path: 输出图片路径
        :param mode: 'sd' (本地), 'gemini' (Google API), 'proxy' (远程代理), None (使用默认模式)
        :return: 生成的图片路径
        """
        # 使用指定模式或默认模式
        active_mode = mode or self.mode

        print(f"\n[BananaService] ========== 开始生成任务 ==========")
        print(f"[BananaService] 模式: {active_mode}")
        print(f"[BananaService] Prompt: {prompt}")
        print(f"[BananaService] 输出路径: {output_path}")

        try:
            if active_mode == "sd":
                return self.generate_with_sd(prompt, output_path)
            if active_mode == "gemini":
                return self.generate_with_gemini(prompt, output_path)
            if active_mode == "proxy":
                return self.generate_with_proxy(prompt, output_path)
            raise ValueError(f"不支持的生成模式: {active_mode}。支持的模式: 'sd', 'gemini', 'proxy'")

        except Exception as e:
            print(f"[BananaService] [FATAL] 生成任务失败: {str(e)}")
            raise

    def get_mode_info(self, mode: str = None) -> dict:
        """Return active mode and model identifier."""
        active_mode = mode or self.mode
        if active_mode == "sd":
            model_name = SD_MODEL_ID
        elif active_mode == "gemini":
            model_name = GEMINI_MODEL
        else:
            model_name = REMOTE_MODEL_NAME
        return {
            "mode": active_mode,
            "model_used": model_name,
        }

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

    def generate_with_proxy(self, prompt: str, output_path: str):
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
                response = requests.post(responses_url, headers=headers, json=responses_payload, timeout=480)
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
            except Exception as responses_err:
                print(f"[BananaService] [WARN] /responses 调用异常，回退到 /chat/completions: {responses_err}")

            print(f"[BananaService] 回退请求 /chat/completions (stream): {chat_url}")
            response = requests.post(chat_url, headers=headers, json=chat_payload, timeout=480, stream=True)
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
            raise


# 全局单例 (默认使用环境变量配置的模式)
banana_service = BananaService()
