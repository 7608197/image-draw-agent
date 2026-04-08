"""
测试 banana_service_flow2 的三种模式
Test script for dual-mode image generation service
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.services.banana_service_flow2 import BananaService


def test_sd_mode():
    """测试本地 Stable Diffusion 模式"""
    print("\n" + "="*60)
    print("测试 1: 本地 SD 模式")
    print("="*60)

    service = BananaService(default_mode="sd")
    output_path = os.path.join(os.path.dirname(__file__), "images", "test_sd_mode.png")

    try:
        result = service.generate(
            prompt="A beautiful sunset over the ocean",
            output_path=output_path
        )
        print(f"\n✓ SD模式测试成功！图片保存至: {result}")
        return True
    except Exception as e:
        print(f"\n✗ SD模式测试失败: {e}")
        return False


def test_gemini_mode():
    """测试 Google Gemini API 模式"""
    print("\n" + "="*60)
    print("测试 2: Gemini API 模式")
    print("="*60)

    service = BananaService(default_mode="gemini")
    output_path = os.path.join(os.path.dirname(__file__), "images", "test_gemini_mode.png")

    try:
        result = service.generate(
            prompt="A futuristic city with flying cars",
            output_path=output_path
        )
        print(f"\n✓ Gemini模式测试成功！图片保存至: {result}")
        return True
    except Exception as e:
        print(f"\n✗ Gemini模式测试失败: {e}")
        print("提示: 请确保已设置有效的 GEMINI_API_KEY 环境变量")
        return False


def test_proxy_mode():
    """测试远程代理模式"""
    print("\n" + "="*60)
    print("测试 3: 远程代理模式")
    print("="*60)

    service = BananaService(default_mode="proxy")
    output_path = os.path.join(os.path.dirname(__file__), "images", "test_proxy_mode.png")

    try:
        result = service.generate(
            prompt="A cute robot playing with a cat",
            output_path=output_path
        )
        print(f"\n✓ Proxy模式测试成功！图片保存至: {result}")
        return True
    except Exception as e:
        print(f"\n✗ Proxy模式测试失败: {e}")
        print("提示: 请确保远程代理服务可访问 (http://192.168.1.110:38000)")
        return False


def test_mode_switching():
    """测试动态切换模式"""
    print("\n" + "="*60)
    print("测试 4: 动态模式切换")
    print("="*60)

    # 创建默认使用 SD 模式的服务
    service = BananaService(default_mode="sd")
    output_dir = os.path.join(os.path.dirname(__file__), "images")

    prompts_and_modes = [
        ("A serene mountain landscape", "sd"),
        ("A cyberpunk street at night", "gemini"),
        ("A fantasy castle in the clouds", "proxy"),
    ]

    results = []
    for i, (prompt, mode) in enumerate(prompts_and_modes):
        output_path = os.path.join(output_dir, f"test_switch_mode_{mode}.png")
        try:
            print(f"\n尝试使用 {mode} 模式生成...")
            result = service.generate(prompt, output_path, mode=mode)
            print(f"✓ {mode} 模式成功: {result}")
            results.append(True)
        except Exception as e:
            print(f"✗ {mode} 模式失败: {e}")
            results.append(False)

    success_count = sum(results)
    print(f"\n模式切换测试: {success_count}/{len(results)} 成功")
    return success_count == len(results)


if __name__ == "__main__":
    print("\n" + "="*60)
    print("BananaService 双模式测试套件")
    print("="*60)

    # 确保输出目录存在
    output_dir = os.path.join(os.path.dirname(__file__), "images")
    os.makedirs(output_dir, exist_ok=True)

    # 运行测试
    tests = [
        ("SD 模式", test_sd_mode),
        ("Gemini 模式", test_gemini_mode),
        ("Proxy 模式", test_proxy_mode),
        ("模式切换", test_mode_switching),
    ]

    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except KeyboardInterrupt:
            print("\n\n用户中断测试")
            break
        except Exception as e:
            print(f"\n✗ 测试 '{test_name}' 发生未预期错误: {e}")
            results[test_name] = False

    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    for test_name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{test_name}: {status}")

    success_count = sum(results.values())
    total_count = len(results)
    print(f"\n总计: {success_count}/{total_count} 测试通过")

    if success_count == total_count:
        print("\n所有测试通过！")
    else:
        print(f"\n{total_count - success_count} 个测试失败，请检查配置。")
