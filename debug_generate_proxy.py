import os
import sys
import requests

DEFAULT_MODEL = "gemini-3-pro-image-preview"
DEFAULT_BASE_URL = "http://127.0.0.1:38000/v1"
DEFAULT_API_KEY = ""


def _print_response(label: str, response: requests.Response) -> None:
    print(f"\n== {label} ==")
    print("Status:", response.status_code)
    text = response.text or ""
    print(text[:4000])


def _post_json(url: str, headers: dict, payload: dict, timeout: int = 120) -> requests.Response:
    return requests.post(url, headers=headers, json=payload, timeout=timeout)


def _probe_endpoints(base_url: str, headers: dict, model: str) -> None:
    models_url = f"{base_url}/models"
    images_url = f"{base_url}/images/generations"
    responses_url = f"{base_url}/responses"

    print("Probe base URL:", base_url)
    print("Probe model:", model)

    try:
        resp = requests.get(models_url, headers=headers, timeout=30)
        _print_response("GET /models", resp)
    except Exception as exc:
        print("\n== GET /models ==")
        print("Error:", exc)

    try:
        payload = {
            "model": model,
            "prompt": "A red apple on a table",
            "size": "512x512",
        }
        resp = _post_json(images_url, headers, payload)
        _print_response("POST /images/generations", resp)
    except Exception as exc:
        print("\n== POST /images/generations ==")
        print("Error:", exc)

    try:
        payload = {
            "model": model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Draw an image of: a red apple on a table"}
                    ],
                }
            ],
        }
        resp = _post_json(responses_url, headers, payload)
        _print_response("POST /responses", resp)
    except Exception as exc:
        print("\n== POST /responses ==")
        print("Error:", exc)


def main() -> int:
    args = [arg for arg in sys.argv[1:] if arg]
    probe_mode = "--probe" in args
    prompt_args = [arg for arg in args if arg != "--probe"]

    prompt = "Draw an image of: a red apple on a table"
    if prompt_args:
        prompt = " ".join(prompt_args).strip()

    base_url = os.getenv("IMAGE_GEN_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    api_key = os.getenv("IMAGE_GEN_API_KEY", DEFAULT_API_KEY)
    model = os.getenv("IMAGE_GEN_MODEL", DEFAULT_MODEL)

    if not base_url or not api_key or not model:
        print("Missing IMAGE_GEN_* configuration.")
        return 1

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    if probe_mode:
        _probe_endpoints(base_url, headers, model)
        return 0

    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt}
                ],
            }
        ],
    }

    url = f"{base_url}/responses"
    response = _post_json(url, headers, payload)

    print("Status:", response.status_code)
    print(response.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
