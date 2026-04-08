import requests
import json
import os

# 设置环境变量解决 OpenMP 冲突
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

url = os.getenv("IMAGE_GEN_DEBUG_URL", "http://127.0.0.1:38000/v1/chat/completions")
api_key = os.getenv("IMAGE_GEN_API_KEY", "")
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}
payload = {
    "model": "gemini-3.0-pro-image-landscape-2k",
    "messages": [
        {"role": "user", "content": "Draw a cat"}
    ],
    "stream": True
}

print(f"Testing URL: {url}")
try:
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    print(f"Status Code: {response.status_code}")

    # 尝试打印原始字节
    print(f"Raw Bytes: {response.content}")

    # 尝试 UTF-8 解码
    try:
        print(f"UTF-8 Decoded: {response.content.decode('utf-8')}")
    except:
        print("UTF-8 Decode Failed")

    # 尝试 GBK 解码 (常见的 Windows 乱码源)
    try:
        print(f"GBK Decoded: {response.content.decode('gbk')}")
    except:
        print("GBK Decode Failed")

    # JSON 解析
    try:
        data = response.json()
        if "choices" in data and len(data["choices"]) > 0:
            content = data["choices"][0]["message"]["content"]
            print(f"Content: {content}")
    except:
        pass

except Exception as e:
    print(f"Error: {e}")
