import torch
from diffusers import StableDiffusionPipeline
from google import genai
from google.genai import types

import os
from PIL import Image
import io

class ModelManager:
    def __init__(self):
        self.sd_pipe = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # 1. 配置 Google API (Banana)
        # 建议把 Key 放在环境变量里，或者直接填在这里(测试用)
        self.api_key = os.getenv("GEMINI_API_KEY", "你的_API_KEY_填在这里")
        self.gemini_client = None

    def load_sd_model(self):
        """加载本地 Stable Diffusion (懒加载)"""
        if self.sd_pipe is not None:
            return self.sd_pipe

        print("正在加载本地 Stable Diffusion 模型...")
        model_id = "runwayml/stable-diffusion-v1-5"
        self.sd_pipe = StableDiffusionPipeline.from_pretrained(
            model_id,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32
        )
        self.sd_pipe.to(self.device)
        print("本地 SD 模型加载完毕！")
        return self.sd_pipe

    def call_banana_api(self, prompt: str):
        """调用 Google Gemini 3 (Banana) API"""
        if not self.gemini_client:
            if "你的_API_KEY" in self.api_key:
                raise ValueError("请先在代码里填入 Google API Key！")
            self.gemini_client = genai.Client(api_key=self.api_key)

        print(f"正在呼叫 Banana (Gemini 3) 生成: {prompt}")

        # 注意：这里使用的是 Imagen 3 的模型 ID，它是 Gemini 家族的画图模型
        # 如果你有特定的 Gemini 3 ID，请替换 model 参数
        response = self.gemini_client.models.generate_image(
            model='imagen-3.0-generate-001',
            prompt=prompt,
            config=types.GenerateImageConfig(
                number_of_images=1,
            )
        )

        # Google 返回的是二进制数据，需要转换成 PIL Image
        if response.generated_images:
            image_bytes = response.generated_images[0].image.image_bytes
            return Image.open(io.BytesIO(image_bytes))
        else:
            raise RuntimeError("Banana 模型未返回图片，可能是 Prompt 被安全拦截。")

# 全局单例
manager = ModelManager()

def init_model():
    # 启动时可以先预热 SD，也可以不预热
    pass

def generate_image(prompt: str, output_path: str, model_type: str = "sd"):
    """
    统一生成入口
    :param model_type: 'sd' (本地) 或 'banana' (云端)
    """
    image = None

    if model_type == "sd":
        # 1. 使用本地 Stable Diffusion
        pipe = manager.load_sd_model()
        image = pipe(prompt).images[0]

    elif model_type == "banana":
        # 2. 使用云端 Gemini 3 (Banana)
        try:
            image = manager.call_banana_api(prompt)
        except Exception as e:
            print(f"Banana 调用失败: {e}")
            raise e

    else:
        raise ValueError(f"不支持的模型类型: {model_type}")

    # 保存图片
    if image:
        image.save(output_path)
        return output_path
    return None
