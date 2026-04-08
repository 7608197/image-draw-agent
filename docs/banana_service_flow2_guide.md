# BananaService Flow2 - 使用指南

## 概述

`banana_service_flow2.py` 是一个支持**三种图像生成模式**的统一服务：

1. **SD (Stable Diffusion)** - 本地模型生成
2. **Gemini** - Google Gemini Imagen 3 云端生成
3. **Proxy** - 远程代理服务生成

---

## 快速开始

### 1. 环境配置

#### 安装依赖

**Windows (PowerShell/CMD):**
```cmd
conda env create -f environment.yml
conda activate bishe
```

**Linux/Mac (Bash):**
```bash
conda env create -f environment.yml
conda activate bishe
```

#### 设置环境变量

**Windows (PowerShell):**
```powershell
# 设置默认模式 (可选: sd, gemini, proxy)
$env:IMAGE_GEN_MODE="sd"

# Gemini API密钥 (使用Gemini模式时必需)
$env:GEMINI_API_KEY="your-actual-gemini-api-key"

# 代理API密钥 (使用Proxy模式时必需)
$env:PROXY_API_KEY="your-proxy-api-key"
```

**Linux/Mac (Bash):**
```bash
export IMAGE_GEN_MODE="sd"
export GEMINI_API_KEY="your-actual-gemini-api-key"
export PROXY_API_KEY="your-proxy-api-key"
```

---

### 2. 基本用法

#### 方式A: 使用默认模式

```python
from backend.services.banana_service_flow2 import banana_service

# 使用环境变量 IMAGE_GEN_MODE 指定的模式 (默认: sd)
banana_service.generate(
    prompt="A beautiful sunset over the ocean",
    output_path="G:/Dev/repos/bishe/tests/images/sunset.png"
)
```

#### 方式B: 动态指定模式

```python
from backend.services.banana_service_flow2 import banana_service

# 本地 SD 模式
banana_service.generate(
    prompt="A cat sitting on a table",
    output_path="G:/Dev/repos/bishe/tests/images/cat_sd.png",
    mode="sd"
)

# Gemini API 模式
banana_service.generate(
    prompt="A futuristic city",
    output_path="G:/Dev/repos/bishe/tests/images/city_gemini.png",
    mode="gemini"
)

# 远程代理模式
banana_service.generate(
    prompt="A fantasy castle",
    output_path="G:/Dev/repos/bishe/tests/images/castle_proxy.png",
    mode="proxy"
)
```

#### 方式C: 创建自定义实例

```python
from backend.services.banana_service_flow2 import BananaService

# 创建专用于 Gemini 的实例
gemini_service = BananaService(default_mode="gemini")
gemini_service.generate("A dragon", "dragon.png")

# 创建专用于 SD 的实例
sd_service = BananaService(default_mode="sd")
sd_service.generate("A dragon", "dragon_sd.png")
```

---

## 三种模式详解

### Mode 1: SD (本地 Stable Diffusion)

**优点:**
- 完全离线，无需API密钥
- 无网络延迟
- 可自定义模型

**缺点:**
- 需要GPU (推荐 VRAM ≥ 8GB)
- 首次加载模型较慢 (约30-60秒)
- 生成速度取决于硬件

**配置:**
```python
# 在 banana_service_flow2.py 中修改
SD_MODEL_ID = "runwayml/stable-diffusion-v1-5"  # 可替换为其他模型
```

**适用场景:**
- 开发测试
- 离线环境
- 需要自定义模型

---

### Mode 2: Gemini (Google Gemini API)

**优点:**
- 云端计算，无需本地GPU
- 生成质量高
- 支持复杂prompt

**缺点:**
- 需要有效的 Google API Key
- 有请求配额限制
- 需要网络连接

**配置:**
```bash
# 设置环境变量
export GEMINI_API_KEY="your-actual-key-here"
```

**适用场景:**
- 生产环境
- 高质量图像需求
- 无GPU硬件

---

### Mode 3: Proxy (远程代理)

**优点:**
- 灵活的远程服务接入
- 支持多种返回格式 (Base64, URL)
- 适合团队协作

**缺点:**
- 依赖远程服务可用性
- 网络延迟
- 需要配置代理服务器

**配置:**
```python
# 在 banana_service_flow2.py 中修改
PROXY_URL = "http://your-proxy-server:port/v1/chat/completions"
PROXY_API_KEY = "your-proxy-api-key"
```

**适用场景:**
- 企业内部服务
- LAN部署
- 需要统一管理

---

## 运行测试

### 测试所有模式

**Windows:**
```cmd
cd G:\Dev\repos\bishe
python tests\test_dual_mode.py
```

**Linux/Mac:**
```bash
cd /path/to/bishe
python tests/test_dual_mode.py
```

### 测试单个模式

```python
# 仅测试 SD 模式
python -c "from tests.test_dual_mode import test_sd_mode; test_sd_mode()"

# 仅测试 Gemini 模式
python -c "from tests.test_dual_mode import test_gemini_mode; test_gemini_mode()"
```

---

## 故障排查

### 问题1: "请先设置 GEMINI_API_KEY"

**解决方案:**
```bash
# Windows
$env:GEMINI_API_KEY="your-real-key"

# Linux/Mac
export GEMINI_API_KEY="your-real-key"
```

### 问题2: SD模式 "CUDA out of memory"

**解决方案:**
- 减小生成图片尺寸
- 降低batch_size
- 使用CPU模式 (较慢):
  ```python
  # 修改 banana_service_flow2.py
  self.device = "cpu"  # 强制使用CPU
  ```

### 问题3: Proxy模式连接失败

**解决方案:**
1. 检查代理服务是否运行
2. 验证网络连接:
   ```bash
   # Windows
   Test-NetConnection 192.168.1.110 -Port 38000

   # Linux/Mac
   nc -zv 192.168.1.110 38000
   ```
3. 检查API密钥是否正确

### 问题4: 模型下载慢

**解决方案:**
```bash
# 设置 HuggingFace 镜像 (国内用户)
export HF_ENDPOINT=https://hf-mirror.com
```

---

## 性能优化

### SD模式优化

```python
# 使用半精度 (节省显存)
torch_dtype=torch.float16

# 启用注意力切片 (降低显存占用)
pipe.enable_attention_slicing()

# 使用更快的调度器
from diffusers import DPMSolverMultistepScheduler
pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)
```

### Gemini模式优化

```python
# 批量生成
config=types.GenerateImageConfig(
    number_of_images=4,  # 一次生成多张
)
```

---

## 与FastAPI集成

### 示例端点

```python
from fastapi import FastAPI
from backend.services.banana_service_flow2 import banana_service

app = FastAPI()

@app.post("/generate")
async def generate_image(prompt: str, mode: str = "sd"):
    output_path = f"outputs/{hash(prompt)}.png"
    result = banana_service.generate(prompt, output_path, mode=mode)
    return {"status": "success", "path": result}
```

**启动服务:**

**Windows:**
```cmd
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Linux/Mac:**
```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**测试API:**
```bash
curl -X POST "http://localhost:8000/generate" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "A beautiful landscape", "mode": "sd"}'
```

---

## 毕设建议

### 文档结构

1. **系统架构图** - 展示三种模式的切换逻辑
2. **性能对比** - SD vs Gemini vs Proxy 的速度/质量对比
3. **实验设计** - 不同prompt在三种模式下的效果
4. **代码说明** - 详细注释关键函数

### 实验数据收集

```python
import time

start = time.time()
result = banana_service.generate(prompt, output_path, mode="sd")
duration = time.time() - start

print(f"生成耗时: {duration:.2f}秒")
```

---

## 更新日志

### v2.0 (当前版本)
- ✓ 支持三种模式: SD + Gemini + Proxy
- ✓ 修复双HTTP URL bug
- ✓ 统一接口设计
- ✓ 懒加载优化
- ✓ 环境变量配置

### v1.0 (原版本)
- 仅支持远程代理模式
- 存在URL配置错误
