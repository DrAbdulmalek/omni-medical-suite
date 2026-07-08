"""
维度提取模块 - 使用LLM从报告中提取维度
"""

import sys
import json
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# 设置控制台编码为UTF-8（Windows）
# 注意：只在作为主脚本运行时重定向，避免在被导入时冲突
if sys.platform == 'win32' and __name__ == "__main__":
    import io
    if not isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    if not isinstance(sys.stderr, io.TextIOWrapper):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 加载 .env 文件（如果存在）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 导入LLM
try:
    from hello_agents.core.llm import HelloAgentsLLM
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    print("⚠️  警告: hello_agents 模块未安装，无法使用LLM提取维度")


def init_llm():
    """初始化LLM"""
    if not LLM_AVAILABLE:
        return None
    
    # 从环境变量读取LLM配置
    llm_model = (
        os.getenv("LLM_MODEL") or
        os.getenv("LLM_MODEL_ID") or
        "qwen-plus"
    )
    llm_api_key = (
        os.getenv("LLM_API_KEY") or
        os.getenv("MODELSCOPE_API_KEY") or
        os.getenv("MODELSCOPE_API_TOKEN")
    )
    llm_base_url = (
        os.getenv("LLM_BASE_URL") or
        "https://api-inference.modelscope.cn/v1/"
    )
    llm_provider = os.getenv("LLM_PROVIDER", "modelscope")
    
    if not llm_api_key:
        print("⚠️  警告: 未找到LLM API Key")
        return None
    
    try:
        llm = HelloAgentsLLM(
            model=llm_model,
            api_key=llm_api_key,
            base_url=llm_base_url,
            provider=llm_provider
        )
        return llm
    except Exception as e:
        print(f"⚠️  初始化LLM失败: {e}")
        return None


def extract_json_from_text(text: str) -> Optional[Dict]:
    """从文本中提取JSON内容"""
    import re
    
    # 尝试直接解析
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    
    # 尝试提取JSON代码块
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # 尝试提取第一个完整的JSON对象
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
    
    return None


def extract_dimensions_from_text(text: str, llm, existing_themes: List[str] = None) -> Dict:
    """从报告文本中提取维度
    
    Args:
        text: 报告文本内容
        llm: LLM实例
        existing_themes: 现有的themes列表，用于参考抽象级别
    """
    if not llm:
        return {"dimensions": [], "confidence": 0.0, "error": "LLM未初始化"}
    
    themes_hint = ""
    if existing_themes:
        themes_hint = f"\n参考现有themes的风格（这些是用户已经定义的兴趣主题）：{existing_themes}\n提取的维度应该与这些themes在抽象级别上保持一致。"
    
    prompt = f"""请从以下用户报告中提取3-8个维度（dimensions）。维度应该是用户关注的**高级别的主题、领域或兴趣点**，而不是简单的名词拆分。

报告内容：
{text}
{themes_hint}

**提取原则**：
1. **保持概念完整性**：如果报告中提到"信息信号系统"这样的完整概念，应该提取为"信息信号系统"或"系统"，而不要拆成"信息"、"信号"、"系统"三个词
2. **提取主题级别**：维度应该是主题级别的概念（如"AI"、"健康"、"工作"），而不是具体细节（如"更新"、"今天"、"高兴"）
3. **过滤无关词**：
   - 过滤掉动作词（如：更新、创建、删除）
   - 过滤掉时间词（如：今天、昨天、本周）
   - 过滤掉情绪词（如：高兴、难过），除非情绪本身是报告的主题
   - 过滤掉过于通用的词（如：事情、内容、问题）
4. **理解语义上下文**：理解整个句子的含义，提取其背后关注的主题
5. **抽象层次**：维度应该是足够抽象的主题，可以作为YouTube搜索关键词或兴趣标签使用

**示例**：
- 报告："今天很高兴，我们的信息信号系统再次迎来了更新"
- ❌ 错误提取：["信息", "信号", "系统", "更新", "今天"]
- ✅ 正确提取：["信息信号系统"] 或 ["系统"] 或 ["技术系统"]

请以JSON格式返回维度列表：
{{
  "dimensions": ["维度1", "维度2", "维度3"],
  "confidence": 0.85,
  "reasoning": "简要说明提取理由"
}}

要求：
- 维度数量：3-8个（根据报告内容的重要性决定）
- 维度格式：简洁的主题词（2-8个字），保持概念的完整性
- confidence：提取的置信度（0-1之间）
- reasoning：简要说明为什么提取这些维度

请直接返回JSON，不要包含其他文字。"""

    try:
        messages = [
            {"role": "system", "content": "你是一个专业的文本分析助手，擅长从文本中提取高级别的主题和兴趣维度。你会理解语义上下文，保持概念的完整性，不会简单地进行分词。"},
            {"role": "user", "content": prompt}
        ]
        
        response = llm.invoke(messages)
        
        # 提取JSON
        result = extract_json_from_text(response)
        
        if result and "dimensions" in result:
            return {
                "dimensions": result["dimensions"],
                "confidence": result.get("confidence", 0.8),
                "reasoning": result.get("reasoning", "")
            }
        else:
            print(f"⚠️  LLM返回格式不正确: {response[:200]}")
            return {"dimensions": [], "confidence": 0.0, "error": "格式解析失败"}
    
    except Exception as e:
        print(f"⚠️  提取维度失败: {e}")
        return {"dimensions": [], "confidence": 0.0, "error": str(e)}


def extract_dimensions_from_report(report_file: Path, llm, existing_themes: List[str] = None) -> Optional[Dict]:
    """从Markdown文件中提取维度
    
    Args:
        report_file: 报告文件路径
        llm: LLM实例
        existing_themes: 现有的themes列表，用于参考抽象级别
    """
    if not report_file.exists():
        print(f"❌ 报告文件不存在: {report_file}")
        return None
    
    try:
        with open(report_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 移除Markdown标题（如果存在）
        lines = content.split('\n')
        # 跳过开头的#标题行
        content_lines = []
        for line in lines:
            if line.strip().startswith('#') and not content_lines:
                continue
            content_lines.append(line)
        text = '\n'.join(content_lines).strip()
        
        if not text:
            print(f"⚠️  报告内容为空: {report_file}")
            return None
        
        # 提取维度（传入existing_themes）
        result = extract_dimensions_from_text(text, llm, existing_themes=existing_themes)
        
        # 添加报告信息
        result["report_file"] = str(report_file)
        result["report_date"] = report_file.stem
        result["extraction_date"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        
        return result
    
    except Exception as e:
        print(f"❌ 读取报告失败 {report_file}: {e}")
        return None


def save_extraction_result(base_dir: Path, result: Dict, report_type: str):
    """保存提取结果"""
    dimensions_dir = base_dir / "archive" / "dimensions"
    dimensions_dir.mkdir(parents=True, exist_ok=True)
    
    # 根据报告日期生成文件名
    report_date = result.get("report_date", datetime.now().strftime("%Y-%m-%d"))
    output_file = dimensions_dir / f"{report_date}_{report_type}_dimensions.json"
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"✅ 维度提取结果已保存: {output_file}")
        return output_file
    except Exception as e:
        print(f"❌ 保存失败: {e}")
        return None


def batch_extract_dimensions(base_dir: Path, report_type: str = None, llm=None, existing_themes: List[str] = None) -> List[Dict]:
    """批量提取维度
    
    Args:
        base_dir: 基础目录路径
        report_type: 报告类型（daily/weekly/monthly），None表示处理所有类型
        llm: LLM实例
        existing_themes: 现有的themes列表，如果为None则自动从themes.yaml加载
    """
    if not llm:
        llm = init_llm()
        if not llm:
            print("❌ LLM未初始化，无法提取维度")
            return []
    
    # 如果没有传入existing_themes，尝试从themes.yaml加载
    if existing_themes is None:
        try:
            # 避免循环导入，直接在这里读取yaml
            import yaml
            themes_file = base_dir / "themes.yaml"
            if themes_file.exists():
                with open(themes_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    if data and isinstance(data, dict):
                        existing_themes = data.get('themes', [])
                    else:
                        existing_themes = []
                if existing_themes:
                    print(f"📌 已加载 {len(existing_themes)} 个现有themes作为参考: {existing_themes}")
        except Exception as e:
            print(f"⚠️  加载themes.yaml失败，将不参考现有themes: {e}")
            existing_themes = []
    
    reports_dir = base_dir / "archive" / "reports"
    results = []
    
    # 确定要处理的报告类型
    types_to_process = [report_type] if report_type else ["daily", "weekly", "monthly"]
    
    for rtype in types_to_process:
        type_dir = reports_dir / rtype
        if not type_dir.exists():
            continue
        
        print(f"\n📂 处理{rtype}报告...")
        report_files = sorted(type_dir.glob("*.md"))
        
        for report_file in report_files:
            print(f"  处理: {report_file.name}")
            result = extract_dimensions_from_report(report_file, llm, existing_themes=existing_themes)
            
            if result and result.get("dimensions"):
                # 添加报告类型
                result["report_type"] = rtype
                
                # 保存提取结果
                save_extraction_result(base_dir, result, rtype)
                
                results.append(result)
                print(f"    ✅ 提取到 {len(result['dimensions'])} 个维度: {', '.join(result['dimensions'][:5])}")
                # 如果有reasoning，也显示出来（用于调试）
                if result.get("reasoning"):
                    print(f"       推理: {result['reasoning'][:100]}...")
            else:
                print("    ⚠️  未提取到维度")
    
    return results


def load_extraction_results(base_dir: Path) -> List[Dict]:
    """加载所有提取结果"""
    dimensions_dir = base_dir / "archive" / "dimensions"
    
    if not dimensions_dir.exists():
        return []
    
    results = []
    for json_file in dimensions_dir.glob("*_dimensions.json"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                result = json.load(f)
                results.append(result)
        except Exception as e:
            print(f"⚠️  读取提取结果失败 {json_file.name}: {e}")
    
    return results


if __name__ == "__main__":
    # 命令行工具
    import argparse
    
    parser = argparse.ArgumentParser(description="从报告中提取维度")
    parser.add_argument("--report-type", choices=["daily", "weekly", "monthly"], 
                       help="指定报告类型（不指定则处理所有类型）")
    parser.add_argument("--report-file", type=str,
                       help="指定单个报告文件路径")
    parser.add_argument("--base-dir", type=str,
                       help="基础目录路径（默认为脚本所在目录）")
    
    args = parser.parse_args()
    
    base_dir = Path(args.base_dir) if args.base_dir else Path(__file__).parent
    
    llm = init_llm()
    if not llm:
        print("❌ 无法初始化LLM，退出")
        sys.exit(1)
    
    # 加载existing_themes（如果存在）
    existing_themes = None
    try:
        import yaml
        themes_file = base_dir / "themes.yaml"
        if themes_file.exists():
            with open(themes_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data and isinstance(data, dict):
                    existing_themes = data.get('themes', [])
    except Exception:
        pass
    
    if args.report_file:
        # 处理单个文件
        report_file = Path(args.report_file)
        result = extract_dimensions_from_report(report_file, llm, existing_themes=existing_themes)
        if result:
            report_type = result.get("report_type", "daily")
            save_extraction_result(base_dir, result, report_type)
            print(f"\n提取的维度: {result.get('dimensions', [])}")
    else:
        # 批量处理
        results = batch_extract_dimensions(base_dir, args.report_type, llm, existing_themes=existing_themes)
        print(f"\n✅ 共处理 {len(results)} 个报告")

