# Banana Service NewAPI 测试说明

## 测试文件

**文件路径**: `G:\Dev\repos\bishe\tests\test_banana_final.py`

## 测试目的

验证 Banana 模型通过 NewAPI 接口（远程代理模式）生成图片的功能。

## 配置信息

| 配置项 | 值 |
|--------|-----|
| **接口地址** | `http://192.168.1.110:38000/v1/chat/completions` |
| **API Key** | `vyJ3y6LgzPog0pjh8560gPRZWAphYvId` |
| **模型名称** | `gemini-3-pro-image-preview` |
| **生成模式** | `proxy` (远程代理) |

## 测试内容

### 1. 网络连接测试
- 验证与 NewAPI 服务的连接状态
- 检查服务端是否正常响应

### 2. 图片生成测试
- 使用 `banana_service_flow2.py` 的 `proxy` 模式
- 发送图片生成请求
- 接收并保存生成的图片
- 验证图片文件的完整性

### 3. 结果验证
- 检查图片文件是否存在
- 验证文件大小
- 检查图片是否可以正常打开
- 显示图片尺寸和格式信息

## 如何运行测试

### Windows (PowerShell/CMD)

```cmd
# 进入项目目录
cd G:\Dev\repos\bishe

# 激活 conda 环境（如果使用）
conda activate bishe

# 运行测试
python tests\test_banana_final.py
```

### Linux/Mac (Bash)

```bash
# 进入项目目录
cd /path/to/bishe

# 激活 conda 环境（如果使用）
conda activate bishe

# 运行测试
python tests/test_banana_final.py
```

## 预期输出

### 成功示例

```
╔════════════════════════════════════════════════════════════════════╗
║          Banana Service - NewAPI 接口测试套件                      ║
╚════════════════════════════════════════════════════════════════════╝

步骤 1/2: 测试网络连接
======================================================================
连接测试
======================================================================

正在测试连接到: http://192.168.1.110:38000/v1/chat/completions
响应状态码: 200
✓ 连接成功！服务端正常响应

步骤 2/2: 测试图片生成
======================================================================
开始测试 Banana Service (NewAPI 接口 - Proxy 模式)
======================================================================

【配置信息】
  接口地址: http://192.168.1.110:38000/v1/chat/completions
  模型名称: gemini-3-pro-image-preview
  生成模式: proxy (远程代理)
  API Key: vyJ3y6LgzPog0pjh8560gPRZWAphYvId

【初始化服务】
[BananaService] 初始化完成
[BananaService] 默认模式: proxy
[BananaService] 计算设备: cuda

【测试参数】
  Prompt: cyberpunk poster illustration of a cute robot holding a banana...
  输出路径: G:\Dev\repos\bishe\tests\images\test_banana_newapi_1707123456.png

【开始生成】
[BananaService] ========== 开始生成任务 ==========
[BananaService] 模式: proxy
[BananaService] Prompt: cyberpunk poster illustration...
...
[BananaService] [SUCCESS] 图片已下载并保存至: ...

======================================================================
✓ 测试通过！
======================================================================
  生成的图片文件: G:\Dev\repos\bishe\tests\images\test_banana_newapi_1707123456.png
  文件大小: 1,234,567 bytes (1,205.63 KB)
  生成耗时: 45.32 秒
  图片尺寸: 1024 x 1024 像素
  图片格式: PNG
  颜色模式: RGB

✓ 图片文件验证成功，可以正常打开

======================================================================
测试总结
======================================================================
✓ 所有测试通过！

生成的图片已保存到: tests/images/
您可以打开查看生成的图片。
======================================================================
```

## 故障排查

### 问题 1: 网络连接失败

**错误信息**: `✗ 无法连接到服务器`

**可能原因**:
- NewAPI 服务未启动
- IP 地址或端口配置错误
- 防火墙阻止连接

**解决方案**:
```bash
# Windows - 测试网络连接
Test-NetConnection 192.168.1.110 -Port 38000

# Linux/Mac - 测试网络连接
nc -zv 192.168.1.110 38000
```

### 问题 2: API Key 错误

**错误信息**: HTTP 401 或 403

**解决方案**:
- 检查 API Key 是否正确
- 验证 API Key 是否过期
- 联系管理员获取新的 API Key

### 问题 3: 模型名称错误

**错误信息**: `模型不存在` 或类似错误

**解决方案**:
- 确认模型名称: `gemini-3-pro-image-preview`
- 检查 NewAPI 服务支持的模型列表
- 更新 `banana_service_flow2.py` 中的 `REMOTE_MODEL_NAME`

### 问题 4: 导入错误

**错误信息**: `ModuleNotFoundError: No module named 'backend'`

**解决方案**:
```bash
# 确保在项目根目录运行
cd G:\Dev\repos\bishe
python tests\test_banana_final.py
```

### 问题 5: 依赖缺失

**错误信息**: `ModuleNotFoundError: No module named 'torch'`

**解决方案**:
```bash
# 安装缺失的依赖
pip install torch pillow requests
```

## 输出文件

生成的图片将保存在:
- **路径**: `G:\Dev\repos\bishe\tests\images\`
- **文件名格式**: `test_banana_newapi_<timestamp>.png`
- **示例**: `test_banana_newapi_1707123456.png`

## 技术细节

### 测试流程

1. **导入模块**: 从 `banana_service_flow2.py` 导入 `BananaService`
2. **初始化服务**: 创建 `BananaService` 实例，指定 `default_mode="proxy"`
3. **发送请求**: 调用 `generate()` 方法，明确指定 `mode="proxy"`
4. **接收响应**: 处理 Chat Completion 格式的响应
5. **提取图片**: 从响应中提取图片 URL 或 Base64 数据
6. **保存文件**: 下载并保存图片到本地
7. **验证结果**: 检查文件完整性和可读性

### 代码结构

```python
# 初始化（使用 proxy 模式）
banana_service = BananaService(default_mode="proxy")

# 生成图片（明确指定 proxy 模式）
result_path = banana_service.generate(
    prompt="your prompt here",
    output_path="output.png",
    mode="proxy"  # 使用 NewAPI 接口
)
```

## 相关文件

- **服务实现**: `G:\Dev\repos\bishe\backend\services\banana_service_flow2.py`
- **测试脚本**: `G:\Dev\repos\bishe\tests\test_banana_final.py`
- **输出目录**: `G:\Dev\repos\bishe\tests\images\`
- **使用指南**: `G:\Dev\repos\bishe\docs\banana_service_flow2_guide.md`

## 注意事项

1. **网络要求**: 确保能访问 `192.168.1.110:38000`
2. **超时设置**: 默认超时 480 秒（8 分钟）
3. **文件大小**: 生成的图片通常在 500KB - 2MB 之间
4. **生成时间**: 通常需要 30-60 秒，取决于网络和服务端负载
5. **并发限制**: 避免同时运行多个测试，可能导致服务端过载

## 下一步

测试通过后，您可以：

1. **集成到 FastAPI**: 将 `banana_service_flow2.py` 集成到主应用
2. **批量测试**: 使用不同的 prompt 进行批量测试
3. **性能测试**: 记录生成时间、文件大小等指标
4. **质量评估**: 对比不同模式下的生成质量
5. **文档撰写**: 将测试结果整理到毕业设计论文中
