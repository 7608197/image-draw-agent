import re
from typing import Any, Optional


def _to_data_url(base64_str: str, mime_type: str = "image/png") -> str:
    return f"data:{mime_type};base64,{base64_str}"


def _extract_from_part(part: Any) -> Optional[str]:
    if not isinstance(part, dict):
        return None

    image_url = part.get("image_url")
    if isinstance(image_url, str):
        return image_url
    if isinstance(image_url, dict):
        url = image_url.get("url")
        if isinstance(url, str):
            return url

    image_obj = part.get("image")
    if isinstance(image_obj, dict):
        url = image_obj.get("url")
        if isinstance(url, str):
            return url
        b64_json = image_obj.get("b64_json") or image_obj.get("base64")
        if isinstance(b64_json, str):
            return _to_data_url(b64_json)

    b64_json = part.get("b64_json") or part.get("image_base64") or part.get("image_b64")
    if isinstance(b64_json, str):
        return _to_data_url(b64_json)

    return None


def extract_urls_from_text(text: str) -> list[str]:
    if not text:
        return []
    url_pattern = r"https?://[^\s\)\"\]]+"
    return re.findall(url_pattern, text)


def extract_image_source(result: Any) -> Optional[str]:
    if not isinstance(result, dict):
        return None

    data = result.get("data")
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if isinstance(url, str):
                return url
            b64_json = item.get("b64_json") or item.get("base64")
            if isinstance(b64_json, str):
                return _to_data_url(b64_json)

    output = result.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, list):
                for part in content:
                    source = _extract_from_part(part)
                    if source:
                        return source

    choices = result.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
        if isinstance(message, dict):
            images = message.get("images")
            if isinstance(images, list) and images:
                image_data = images[0]
                if isinstance(image_data, dict):
                    image_url = image_data.get("image_url")
                    if isinstance(image_url, dict):
                        url = image_url.get("url")
                        if isinstance(url, str):
                            return url
                    if isinstance(image_url, str):
                        return image_url

            content = message.get("content")
            if isinstance(content, list):
                for part in content:
                    source = _extract_from_part(part)
                    if source:
                        return source

    return None
