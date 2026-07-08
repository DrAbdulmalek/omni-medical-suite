#!/usr/bin/env python3
"""
测试浏览器工具和终端工具的功能
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from src.tools.browser_tool import BrowserTool
from src.tools.terminal_tool import TerminalTool
from src.agents.config import TERMINAL_SECURITY_MODE

def test_terminal_tool():
    """测试终端工具"""
    print("=" * 60)
    print("🧪 测试终端工具 (TerminalTool)")
    print("=" * 60)
    
    terminal = TerminalTool(security_mode=TERMINAL_SECURITY_MODE)
    print(f"安全模式: {TERMINAL_SECURITY_MODE}\n")
    
    # 测试用例
    test_cases = [
        {
            "name": "测试 pwd 命令",
            "input": "pwd",
            "expected": "应该返回当前工作目录"
        },
        {
            "name": "测试 ls 命令",
            "input": "ls",
            "expected": "应该列出当前目录文件"
        },
        {
            "name": "测试 echo 命令",
            "input": "echo Hello World",
            "expected": "应该输出 Hello World"
        },
        {
            "name": "测试 whoami 命令",
            "input": "whoami",
            "expected": "应该返回当前用户名"
        },
        {
            "name": "测试 date 命令",
            "input": "date",
            "expected": "应该返回当前日期时间"
        },
        {
            "name": "测试危险命令 (rm)",
            "input": "rm -rf /",
            "expected": "应该被安全拒绝"
        },
        {
            "name": "测试不在白名单的命令",
            "input": "python --version",
            "expected": "应该被拒绝（不在白名单）"
        }
    ]
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n[{i}/{len(test_cases)}] {test['name']}")
        print(f"输入: {test['input']}")
        print(f"预期: {test['expected']}")
        
        try:
            result = terminal.run({"input": test['input']})
            print(f"结果: {result[:200]}...")  # 只显示前200字符
            
            # 简单判断测试是否通过
            if "错误" in result or "拒绝" in result or "警告" in result:
                if "rm" in test['input'] or "python" in test['input']:
                    print("✅ 测试通过（正确拒绝）")
                    passed += 1
                else:
                    print("❌ 测试失败（不应该被拒绝）")
                    failed += 1
            else:
                if "rm" in test['input'] or "python" in test['input']:
                    print("❌ 测试失败（应该被拒绝）")
                    failed += 1
                else:
                    print("✅ 测试通过")
                    passed += 1
                    
        except Exception as e:
            print(f"❌ 测试异常: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"终端工具测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
    return passed, failed


def test_browser_tool():
    """测试浏览器工具"""
    print("\n" + "=" * 60)
    print("🧪 测试浏览器工具 (BrowserTool)")
    print("=" * 60 + "\n")
    
    browser = BrowserTool()
    
    # 测试用例
    test_cases = [
        {
            "name": "测试简单搜索",
            "input": "Python",
            "expected": "应该返回搜索结果"
        },
        {
            "name": "测试中文搜索",
            "input": "人工智能",
            "expected": "应该返回中文搜索结果"
        },
        {
            "name": "测试空输入",
            "input": "",
            "expected": "应该返回错误提示"
        }
    ]
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n[{i}/{len(test_cases)}] {test['name']}")
        print(f"输入: '{test['input']}'")
        print(f"预期: {test['expected']}")
        
        try:
            result = browser.run({"input": test['input']})
            
            if not test['input']:
                # 空输入测试
                if "错误" in result or "不能为空" in result:
                    print("✅ 测试通过（正确检测到空输入）")
                    passed += 1
                else:
                    print("❌ 测试失败（应该检测到空输入）")
                    failed += 1
            else:
                # 正常搜索测试
                if result and len(result) > 50 and ("错误" not in result or "失败" not in result):
                    print("✅ 测试通过")
                    print(f"结果预览: {result[:150]}...")
                    passed += 1
                else:
                    print("❌ 测试失败")
                    print(f"结果: {result[:200]}")
                    failed += 1
                    
        except Exception as e:
            print(f"❌ 测试异常: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"浏览器工具测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
    return passed, failed


def main():
    """主测试函数"""
    print("\n🚀 开始测试工具功能...\n")
    
    # 测试终端工具
    terminal_passed, terminal_failed = test_terminal_tool()
    
    # 测试浏览器工具
    browser_passed, browser_failed = test_browser_tool()
    
    # 总结
    print("\n" + "=" * 60)
    print("📊 测试总结")
    print("=" * 60)
    print(f"终端工具: {terminal_passed} 通过, {terminal_failed} 失败")
    print(f"浏览器工具: {browser_passed} 通过, {browser_failed} 失败")
    print(f"总计: {terminal_passed + browser_passed} 通过, {terminal_failed + browser_failed} 失败")
    print("=" * 60)
    
    if terminal_failed == 0 and browser_failed == 0:
        print("\n✅ 所有测试通过！工具可以正常使用。")
        return 0
    else:
        print("\n⚠️  部分测试失败，请检查工具实现。")
        return 1


if __name__ == "__main__":
    sys.exit(main())

