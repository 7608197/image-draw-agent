import os
import requests
import json
import re
import traceback
from PIL import Image
from io import BytesIO

import base64

from services.image_response_parser import extract_image_source, extract_urls_from_text

# --- 配置区域 ---
IMAGE_GEN_MODEL = os.getenv("IMAGE_GEN_MODEL", "gemini-3.0-pro-image-landsczaiape-2k")
IMAGE_GEN_BASE_URL = os.getenv("IMAGE_GEN_BASE_URL", "http://127.0.0.1:38000/v1")
IMAGE_GEN_API_KEY = os.getenv("IMAGE_GEN_API_KEY", "")

CLIPROXY_BASE_URL = os.getenv("CLIPROXY_BASE_URL", "")
CLIPROXY_API_KEY = os.getenv("CLIPROXY_API_KEY", "")

class BananaService:
    def __init__(self):
        self.model_name = IMAGE_GEN_MODEL or os.getenv("CLIPROXY_MODEL", "gemini-3-pro-image-preview")
        self.base_url = IMAGE_GEN_BASE_URL or CLIPROXY_BASE_URL
        self.api_key = IMAGE_GEN_API_KEY or CLIPROXY_API_KEY
        if not self.model_name:
            raise ValueError("IMAGE_GEN_MODEL is not set")
        if not self.base_url:
            raise ValueError("IMAGE_GEN_BASE_URL or CLIPROXY_BASE_URL is not set")
        if not self.api_key:
            raise ValueError("IMAGE_GEN_API_KEY or CLIPROXY_API_KEY is not set")

        print("[BananaService] 初始化完成 (Proxy Mode)")
        print(f"[BananaService] 目标 URL: {self.base_url}")
        print(f"[BananaService] 使用模型: {self.model_name}")

    def _save_data_url(self, data_url: str, output_path: str):
        if data_url.startswith("data:image"):
            header, encoded = data_url.split(",", 1)
            data = base64.b64decode(encoded)
            image = Image.open(BytesIO(data))
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            image.save(output_path)
            print(f"[BananaService] [SUCCESS] Base64图片已保存至: {output_path}")
            return output_path
        return self._download_or_save(data_url, output_path)

    def _download_or_save(self, image_url: str, output_path: str):
        if image_url.startswith("data:image"):
            return self._save_data_url(image_url, output_path)
        print(f"[BananaService] 正在下载图片...")
        img_res = requests.get(image_url, timeout=60)
        if img_res.status_code != 200:
            raise RuntimeError(f"图片下载失败: {img_res.status_code}")
        image = Image.open(BytesIO(img_res.content))
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        image.save(output_path)
        print(f"[BananaService] [SUCCESS] 图片已下载并保存至: {output_path}")
        return output_path

    def generate(self, prompt: str, output_path: str):
        print(f"\n[BananaService] 开始生成任务 (Proxy Mode)")
        print(f"[BananaService] Prompt: {prompt}")
        print(f"[BananaService] 输出路径: {output_path}")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        base_url = self.base_url.rstrip("/")
        responses_url = f"{base_url}/responses"
        chat_url = f"{base_url}/chat/completions"

        user_content = f"Draw an image of: {prompt}"

        responses_payload = {
            "model": self.model_name,
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
            "model": self.model_name,
            "messages": [
                {"role": "user", "content": user_content}
            ],
            "stream": True,
        }

        print("[BananaService] 发送 POST 请求...")
        print(f"[BananaService] Payload: {json.dumps(responses_payload, indent=2)}")

        try:
            result = None
            response = requests.post(responses_url, headers=headers, json=responses_payload, timeout=480)
            print(f"[BananaService] responses 状态码: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
            else:
                print(f"[BananaService] [WARN] responses 请求失败: {response.text}")

            if result is None:
                print("[BananaService] 切换到 chat/completions (stream)...")
                response = requests.post(chat_url, headers=headers, json=chat_payload, timeout=480, stream=True)
                print(f"[BananaService] chat 状态码: {response.status_code}")
                if response.status_code != 200:
                    print(f"[BananaService] [ERROR] 请求失败")
                    print(f"[BananaService] Response Text: {response.text}")
                    response.raise_for_status()

                full_content = ""
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
                            if "choices" in data_json and len(data_json["choices"]) > 0:
                                delta = data_json["choices"][0].get("delta", {})
                                content_part = delta.get("content")
                                if content_part:
                                    full_content += content_part
                                images = delta.get("images")
                                if images and isinstance(images, list) and len(images) > 0:
                                    image_data = images[0]
                                    if isinstance(image_data, dict) and "image_url" in image_data and "url" in image_data["image_url"]:
                                        return self._download_or_save(image_data["image_url"]["url"], output_path)
                        except json.JSONDecodeError:
                            continue
                if full_content:
                    urls = extract_urls_from_text(full_content)
                    if urls:
                        return self._download_or_save(urls[0], output_path)
                result = None

            if result is None:
                raise ValueError("Empty response from proxy")

            image_source = extract_image_source(result)
            if image_source:
                return self._download_or_save(image_source, output_path)

            output_text = result.get("output_text") if isinstance(result, dict) else ""
            urls = extract_urls_from_text(output_text or "")
            if urls:
                return self._download_or_save(urls[0], output_path)

            if isinstance(result, dict) and "choices" in result:
                message = result.get("choices", [{}])[0].get("message", {})
                content = ""
                if isinstance(message, dict):
                    raw = message.get("content")
                    if isinstance(raw, str):
                        content = raw
                    elif isinstance(raw, list):
                        content = "".join([str(part.get("text", "")) for part in raw if isinstance(part, dict)])
                if content:
                    urls = extract_urls_from_text(content)
                    if urls:
                        return self._download_or_save(urls[0], output_path)

            try:
                debug_path = os.path.join(os.path.dirname(output_path), "last_response.json")
                with open(debug_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"[BananaService] 已保存原始响应: {debug_path}")
            except Exception as debug_err:
                print(f"[BananaService] [WARN] 保存响应失败: {debug_err}")

            raise ValueError("响应格式错误")

        except Exception as e:
            print(f"[BananaService] [EXCEPTION] 发生异常: {str(e)}")
            print(traceback.format_exc())
            raise

banana_service = BananaService()
