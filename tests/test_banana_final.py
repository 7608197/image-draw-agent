"""
测试 Banana 模型通过 NewAPI 接口生成图片
Test Banana model image generation via NewAPI interface

配置信息:
- URL: http://192.168.1.110:38000/v1/chat/completions
- API Key: vyJ3y6LgzPog0pjh8560gPRZWAphYvId
- Model: gemini-3-pro-image-preview
- Mode: proxy (远程代理模式)
"""

import sys
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import time

# 将项目根目录添加到 python path，确保能正确导入 backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.services.banana_service_flow2 import BananaService


def test_banana_newapi_generation():
    """
    测试 Banana 模型通过 NewAPI 接口生成图片
    使用 proxy 模式连接到远程代理服务
    """
    print("=" * 70)
    print("开始测试 Banana Service (NewAPI 接口 - Proxy 模式)")
    print("=" * 70)

    # 显示配置信息
    print("\n【配置信息】")
    print("  接口地址: http://192.168.1.110:38000/v1/chat/completions")
    print("  模型名称: gemini-3.0-pro-image-landscape-2k")
    print("  生成模式: proxy (远程代理)")
    print("  API Key: vyJ3y6LgzPog0pjh8560gPRZWAphYvId")

    # 初始化 Banana Service (使用 proxy 模式)
    print("\n【初始化服务】")
    banana_service = BananaService(default_mode="proxy")

    # 测试提示词
    prompt = "cyberpunk poster illustration of a cute robot holding a banana, bold graphic shapes, neon pink and teal palette, rain-soaked city silhouettes, strong rim light, high contrast, clean typography space (no text), centered hero composition, ultra sharp, detailed, professional poster art"

    # 准备输出路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    images_dir = os.path.join(current_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    output_filename = f"test_banana_newapi_{int(time.time())}.png"
    output_path = os.path.join(images_dir, output_filename)

    print("\n【测试参数】")
    print(f"  Prompt: {prompt[:100]}...")
    print(f"  输出路径: {output_path}")

    # 执行生成
    print("\n【开始生成】")
    try:
        start_time = time.time()

        # 调用 generate 方法，明确指定使用 proxy 模式
        result_path = banana_service.generate(
            prompt=prompt,
            output_path=output_path,
            mode="proxy"  # 明确指定使用 proxy 模式
        )

        end_time = time.time()
        duration = end_time - start_time

        # 验证结果
        if os.path.exists(result_path):
            file_size = os.path.getsize(result_path)

            print("\n" + "=" * 70)
            print("[OK] 测试通过！")
            print("=" * 70)
            print(f"  生成的图片文件: {result_path}")
            print(f"  文件大小: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
            print(f"  生成耗时: {duration:.2f} 秒")

            # 验证图片是否可以被正常打开
            try:
                from PIL import Image
                with Image.open(result_path) as img:
                    print(f"  图片尺寸: {img.size[0]} x {img.size[1]} 像素")
                    print(f"  图片格式: {img.format}")
                    print(f"  颜色模式: {img.mode}")
                print("\n[OK] 图片文件验证成功，可以正常打开")
            except Exception as e:
                print(f"\n[WARN] 警告: 图片文件可能已损坏 - {e}")

            return True

        else:
            print("\n" + "=" * 70)
            print("[ERROR] 测试失败")
            print("=" * 70)
            print(f"  错误: 文件未找到 - {result_path}")
            return False

    except Exception as e:
        print("\n" + "=" * 70)
        print("[ERROR] 测试过程中发生异常")
        print("=" * 70)
        print(f"  异常类型: {type(e).__name__}")
        print(f"  异常信息: {str(e)}")

        # 打印详细的堆栈信息
        import traceback
        print("\n【详细错误堆栈】")
        traceback.print_exc()

        return False


def test_connection():
    """
    测试与 NewAPI 服务的网络连接
    """
    print("\n" + "=" * 70)
    print("连接测试")
    print("=" * 70)

    import requests

    url = "http://192.168.1.110:38000/v1/chat/completions"

    print(f"\n正在测试连接到: {url}")

    try:
        # 发送一个简单的测试请求
        response = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer vyJ3y6LgzPog0pjh8560gPRZWAphYvId"
            },
            json={
                "model": "gemini-3-pro-image-preview",
                "messages": [
                    {"role": "user", "content": "Draw an image of: test connection"}
                ]
            },
            timeout=10
        )

        print(f"响应状态码: {response.status_code}")

        if response.status_code == 200:
            print("[OK] 连接成功！服务端正常响应")
            return True
        else:
            print(f"[ERROR] 服务端返回错误状态码: {response.status_code}")
            print(f"响应内容: {response.text[:500]}")
            return False

    except requests.exceptions.Timeout:
        print("[ERROR] 连接超时")
        print("提示: 请检查网络连接和服务器是否正常运行")
        return False
    except requests.exceptions.ConnectionError:
        print("[ERROR] 无法连接到服务器")
        print("提示: 请检查 IP 地址和端口是否正确，服务是否已启动")
        return False
    except Exception as e:
        print(f"[ERROR] 连接测试失败: {e}")
        return False


if __name__ == "__main__":
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 10 + "Banana Service - NewAPI 接口测试套件" + " " * 20 + "║")
    print("╚" + "═" * 68 + "╝")

    # 先测试连接
    print("\n步骤 1/2: 测试网络连接")
    connection_ok = test_connection()

    if not connection_ok:
        print("\n⚠ 警告: 网络连接测试失败，但仍将继续尝试生成测试...")
        print("如果生成测试也失败，请先解决网络连接问题。")

    # 执行主测试
    print("\n步骤 2/2: 测试图片生成")
    success = test_banana_newapi_generation()

    # 总结
    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)

    if success:
        print("[OK] 所有测试通过！")
        print("\n生成的图片已保存到: tests/images/")
        print("您可以打开查看生成的图片。")
    else:
        print("[ERROR] 测试失败")
        print("\n可能的原因:")
        print("  1. 网络连接问题 - 无法访问 192.168.1.110:38000")
        print("  2. API 密钥错误 - 请检查 API Key 是否正确")
        print("  3. 服务端错误 - 检查服务端日志")
        print("  4. 模型名称错误 - 确认模型是 'gemini-3-pro-image-preview'")
        print("\n请根据上方的详细错误信息进行排查。")

    print("=" * 70)
