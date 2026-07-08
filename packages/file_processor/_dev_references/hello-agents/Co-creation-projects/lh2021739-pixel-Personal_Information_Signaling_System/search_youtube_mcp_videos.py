"""
YouTube 视频搜索脚本 - 按主题搜索、评分、生成日报
从 themes.yaml 读取主题列表，对每个主题分别搜索 YouTube
合并结果、评分、排序后生成日报报告
"""

import sys
import os
import json
import argparse
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone

# 设置控制台编码为UTF-8（Windows）
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

try:
    import httpx
except ImportError:
    print("❌ 错误: 需要安装 httpx 库")
    print("💡 运行: pip install httpx")
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("❌ 错误: 需要安装 PyYAML 库")
    print("💡 运行: pip install pyyaml")
    sys.exit(1)

# 加载 .env 文件（如果存在）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv 可选，如果未安装则跳过

# 可选：导入 LLM 相关模块（仅用于 research 模式）
try:
    from hello_agents.core.llm import HelloAgentsLLM
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

# 配置常量
DAYS_WINDOW = int(os.getenv("DAYS_WINDOW", "14"))  # 时间窗口：默认14天


def load_youtube_api_key():
    """从环境变量或配置文件中加载 YouTube API Key"""
    # 首先尝试环境变量
    api_key = os.getenv("YOUTUBE_API_KEY")
    
    if api_key:
        return api_key
    
    # 尝试从配置文件中读取
    config_file = Path(__file__).parent / "config"
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("YOUTUBE_API_KEY=") and not line.startswith("#"):
                        api_key = line.split("=", 1)[1].strip()
                        if api_key:
                            return api_key
        except Exception as e:
            print(f"⚠️  读取配置文件失败: {e}")
    
    return None


def load_themes():
    """从 themes.yaml 读取主题列表"""
    themes_file = Path(__file__).parent / "themes.yaml"
    if not themes_file.exists():
        print(f"❌ 错误: 找不到 themes.yaml 文件: {themes_file}")
        return []
    
    try:
        with open(themes_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            if data is None:
                print("❌ 错误: themes.yaml 文件为空或格式错误")
                return []
            themes = data.get('themes', [])
            if not themes:
                print("⚠️  警告: themes.yaml 中未找到主题列表")
                return []
            print(f"✅ 加载了 {len(themes)} 个主题: {', '.join(themes)}")
            return themes
    except Exception as e:
        print(f"❌ 读取 themes.yaml 失败: {e}")
        import traceback
        traceback.print_exc()
        return []


def load_whitelist_channels():
    """从 channels.yaml 读取白名单频道"""
    channels_file = Path(__file__).parent / "channels.yaml"
    if not channels_file.exists():
        print(f"⚠️  警告: 找不到 channels.yaml 文件: {channels_file}")
        return []
    
    try:
        with open(channels_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            if data is None:
                print("⚠️  警告: channels.yaml 文件为空或格式错误")
                return []
            channels = data.get('whitelist_channels', [])
            print(f"✅ 加载了 {len(channels)} 个白名单频道")
            return channels
    except Exception as e:
        print(f"⚠️  读取 channels.yaml 失败: {e}")
        return []


def search_youtube_videos(query: str, max_results: int = 10, api_key: str = None):
    """搜索 YouTube 视频"""
    if not api_key:
        api_key = load_youtube_api_key()
    
    if not api_key:
        print("❌ 错误: 未找到 YouTube API Key")
        print("💡 请设置环境变量 YOUTUBE_API_KEY 或在 config 文件中配置")
        return None
    
    try:
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "key": api_key,
            "q": query,
            "part": "snippet",
            "type": "video",
            "maxResults": min(max_results, 50),  # API limit
            "order": "relevance"
        }
        
        response = httpx.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        
        data = response.json()
        
        if "items" not in data or not data["items"]:
            return []
        
        videos = []
        for item in data["items"]:
            video_info = {
                "video_id": item["id"]["videoId"],
                "title": item["snippet"]["title"],
                "description": item["snippet"]["description"],
                "channel_title": item["snippet"]["channelTitle"],
                "channel_id": item["snippet"]["channelId"],
                "published_at": item["snippet"]["publishedAt"],
                "thumbnail": item["snippet"]["thumbnails"].get("medium", {}).get("url", ""),
                "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                "query": query  # 记录搜索关键词
            }
            videos.append(video_info)
        
        return videos
    
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            print(f"❌ 错误: API 密钥无效或配额已用完 (查询: {query})")
        else:
            print(f"❌ HTTP 错误: {e.response.status_code} (查询: {query})")
        return None
    except Exception as e:
        print(f"❌ 搜索失败 (查询: {query}): {str(e)}")
        return None


def parse_published_time(published_at_str: str):
    """解析发布时间字符串为 datetime 对象"""
    try:
        # YouTube API 返回 ISO 8601 格式: 2024-01-01T12:00:00Z
        dt = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
        return dt
    except Exception as e:
        print(f"⚠️  解析发布时间失败: {published_at_str}, 错误: {e}")
        return None


def is_within_time_window(published_at_str: str, days_window: int = DAYS_WINDOW):
    """检查视频是否在时间窗口内（默认14天）"""
    published_time = parse_published_time(published_at_str)
    if not published_time:
        return False
    
    now = datetime.now(timezone.utc)
    time_diff = now - published_time
    
    return time_diff <= timedelta(days=days_window)


def calculate_time_score(published_at_str: str):
    """计算时间评分：24小时内 +3，48小时内 +2"""
    published_time = parse_published_time(published_at_str)
    if not published_time:
        return 0
    
    now = datetime.now(timezone.utc)
    time_diff = now - published_time
    
    if time_diff <= timedelta(hours=24):
        return 3
    elif time_diff <= timedelta(hours=48):
        return 2
    else:
        return 0


def count_theme_keywords(text: str, themes: list):
    """计算文本中命中的主题关键词数量（不区分大小写）"""
    if not text:
        return 0
    
    text_lower = text.lower()
    count = 0
    for theme in themes:
        if theme.lower() in text_lower:
            count += 1
    return count


def score_video(video: dict, themes: list, whitelist_channels: list):
    """为视频计算评分"""
    score = 0
    
    # 1. 白名单频道评分 +10
    if video['channel_title'] in whitelist_channels:
        score += 10
    
    # 2. 标题或描述中每命中1个主题关键词 +5
    title_matches = count_theme_keywords(video['title'], themes)
    desc_matches = count_theme_keywords(video['description'], themes)
    keyword_score = (title_matches + desc_matches) * 5
    score += keyword_score
    
    # 3. 发布时间评分
    time_score = calculate_time_score(video['published_at'])
    score += time_score
    
    return score


def merge_and_deduplicate_videos(all_videos: list):
    """合并视频列表并按 videoId 去重"""
    video_dict = {}
    
    for video in all_videos:
        video_id = video['video_id']
        if video_id not in video_dict:
            video_dict[video_id] = video
        else:
            # 如果已存在，合并查询关键词
            existing_queries = video_dict[video_id].get('queries', [])
            if isinstance(existing_queries, str):
                existing_queries = [existing_queries]
            if video['query'] not in existing_queries:
                existing_queries.append(video['query'])
            video_dict[video_id]['queries'] = existing_queries
    
    return list(video_dict.values())


def generate_action(videos: list):
    """生成 action 字段：从 Top1 生成1条可执行动作（≤15min）"""
    if not videos:
        return "暂无推荐视频"
    
    # 只使用 Top1
    top1 = videos[0]
    action = f"观看《{top1['title']}》({top1['channel_title']})，预计≤15分钟"
    
    return action


def has_clickbait_words(title: str):
    """检查标题中是否包含标题党词汇"""
    clickbait_words = ['INSANE', 'HYPE', 'SHOCKING', 'UNBELIEVABLE', 'MIND-BLOWING', 
                       'AMAZING', 'INCREDIBLE', 'YOU WON\'T BELIEVE', 'THIS WILL BLOW YOUR MIND']
    title_upper = title.upper()
    for word in clickbait_words:
        if word in title_upper:
            return True
    return False


def is_older_than_days(published_at_str: str, days: int = 30):
    """检查视频是否超过指定天数"""
    published_time = parse_published_time(published_at_str)
    if not published_time:
        return False
    
    now = datetime.now(timezone.utc)
    time_diff = now - published_time
    
    return time_diff > timedelta(days=days)


def generate_risk(videos: list, themes: list):
    """生成 risk 字段：偏差检测"""
    if not videos:
        return "无风险"
    
    # 只检查 Top3
    top3 = videos[:3]
    warnings = []
    
    # 检查是否有超过30天的视频
    old_videos = []
    for video in top3:
        if is_older_than_days(video['published_at'], days=30):
            old_videos.append(video['title'])
    
    if old_videos:
        warnings.append(f"Top3中存在超过30天的视频: {', '.join(old_videos[:2])}")
    
    # 检查是否有标题党词汇
    clickbait_videos = []
    for video in top3:
        if has_clickbait_words(video['title']):
            clickbait_videos.append(video['title'])
    
    if clickbait_videos:
        warnings.append(f"检测到标题党词汇: {', '.join(clickbait_videos[:2])}")
    
    # 如果有警告，返回警告；否则返回正面评价
    if warnings:
        return "; ".join(warnings)
    else:
        return "今日信号较新且较可信"


def init_research_llm():
    """初始化用于研究模式的 LLM（使用通义千问/ModelScope配置）"""
    if not LLM_AVAILABLE:
        print("⚠️  警告: hello_agents 模块未安装，无法使用研究模式")
        return None
    
    # 从环境变量读取 LLM 配置（优先级顺序，与 chapter9 保持一致）
    # 优先使用 ModelScope 配置（通义千问）
    llm_model = (
        os.getenv("LLM_MODEL") or 
        os.getenv("LLM_MODEL_ID") or
        "Qwen/Qwen2.5-7B-Instruct"  # 默认通义千问模型
    )
    llm_api_key = (
        os.getenv("LLM_API_KEY") or  # 优先使用 LLM_API_KEY（阿里云通义千问）
        os.getenv("MODELSCOPE_API_KEY") or 
        os.getenv("MODELSCOPE_API_TOKEN")
    )
    llm_base_url = (
        os.getenv("LLM_BASE_URL") or 
        "https://api-inference.modelscope.cn/v1/"  # ModelScope 默认地址
    )
    llm_provider = os.getenv("LLM_PROVIDER", "modelscope")
    
    if not llm_api_key:
        print("⚠️  警告: 未找到 LLM API Key，研究模式需要配置 LLM")
        print("💡 请设置环境变量（推荐在 .env 文件中配置）:")
        print("   MODELSCOPE_API_KEY=your-modelscope-token-here")
        print("   LLM_MODEL=Qwen/Qwen2.5-7B-Instruct")
        print("   LLM_BASE_URL=https://api-inference.modelscope.cn/v1/")
        print("   LLM_PROVIDER=modelscope")
        return None
    
    try:
        llm = HelloAgentsLLM(
            model=llm_model,
            api_key=llm_api_key,
            base_url=llm_base_url,
            provider=llm_provider
        )
        print(f"✅ LLM 初始化成功: {llm_model} ({llm_provider})")
        return llm
    except Exception as e:
        print(f"⚠️  初始化 LLM 失败: {e}")
        return None


def prepare_sources_data(top3_videos: list):
    """从 Top3 视频中提取 sources 数据"""
    sources = []
    for video in top3_videos:
        sources.append({
            "title": video['title'],
            "channel": video['channel_title'],
            "url": video['url'],
            "published_at": video['published_at'],
            "score": video['score']
        })
    return sources


def extract_json_from_text(text: str):
    """从文本中提取 JSON 内容（处理 LLM 可能返回的格式化文本）"""
    # 尝试直接解析
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    
    # 尝试提取 JSON 代码块
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # 尝试提取第一个完整的 JSON 对象
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
    
    return None


def generate_research_report(top3_videos: list, themes: list, llm):
    """使用 LLM 生成研究报告"""
    if not top3_videos:
        return None
    
    # 构建视频信息文本
    videos_info = []
    for i, video in enumerate(top3_videos, 1):
        videos_info.append(
            f"{i}. 标题: {video['title']}\n"
            f"   频道: {video['channel_title']}\n"
            f"   发布时间: {video['published_at']}\n"
            f"   评分: {video['score']}分\n"
            f"   链接: {video['url']}"
        )
    
    videos_text = "\n\n".join(videos_info)
    themes_text = ", ".join(themes)
    
    # 构建 prompt
    prompt = f"""基于以下 Top3 YouTube 视频信息，生成一份结构化研究报告。

视频信息：
{videos_text}

搜索主题：{themes_text}

请以 JSON 格式返回以下内容：
1. question: 一个核心问题，概括这些视频的共同关注点
2. key_findings: 3条发现，每条1句话，基于标题/频道/发布时间推断，使用"可能/倾向"等措辞
3. why_it_matters_to_me: 为什么这些信息对我重要（个性化解释）
4. next_steps: 1-3条行动建议，每条≤15分钟

请严格按照以下 JSON 格式返回（不要包含其他文字）：
{{
  "question": "核心问题",
  "key_findings": [
    "发现1（使用可能/倾向等措辞）",
    "发现2（使用可能/倾向等措辞）",
    "发现3（使用可能/倾向等措辞）"
  ],
  "why_it_matters_to_me": "个性化解释",
  "next_steps": [
    "行动建议1（≤15分钟）",
    "行动建议2（≤15分钟）",
    "行动建议3（≤15分钟）"
  ]
}}"""

    messages = [
        {"role": "system", "content": "你是一位专业的研究分析师，擅长从视频信息中提取关键洞察并给出可执行的行动建议。请始终以 JSON 格式返回结果。"},
        {"role": "user", "content": prompt}
    ]
    
    try:
        print("\n🔬 正在使用 LLM 生成研究报告...")
        response = llm.invoke(messages)
        
        if not response:
            print("⚠️  LLM 返回空响应")
            return None
        
        # 提取 JSON
        research_data = extract_json_from_text(response)
        
        if not research_data:
            print(f"⚠️  无法解析 LLM 响应为 JSON，原始响应: {response[:200]}...")
            return None
        
        # 验证必需字段
        required_fields = ["question", "key_findings", "why_it_matters_to_me", "next_steps"]
        missing_fields = [field for field in required_fields if field not in research_data]
        if missing_fields:
            print(f"⚠️  LLM 响应缺少必需字段: {', '.join(missing_fields)}")
            return None
        
        # 确保 key_findings 是列表且有3条
        if not isinstance(research_data.get("key_findings"), list):
            research_data["key_findings"] = []
        if len(research_data["key_findings"]) != 3:
            # 如果不足3条，填充或截断
            while len(research_data["key_findings"]) < 3:
                research_data["key_findings"].append("暂无发现")
            research_data["key_findings"] = research_data["key_findings"][:3]
        
        # 确保 next_steps 是列表，最多3条
        if not isinstance(research_data.get("next_steps"), list):
            research_data["next_steps"] = []
        research_data["next_steps"] = research_data["next_steps"][:3]
        
        print("✅ 研究报告生成成功")
        return research_data
        
    except Exception as e:
        print(f"⚠️  生成研究报告时出错: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="YouTube 视频搜索 - 多主题智能搜索与日报生成")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["daily_signal", "research"],
        default="research",
        help="运行模式: research (默认，生成日报+研究报告) 或 daily_signal (仅生成日报)"
    )
    args = parser.parse_args()
    mode = args.mode
    
    print("=" * 70)
    print("YouTube 视频搜索 - 多主题智能搜索与日报生成")
    if mode == "research":
        print("运行模式: 研究模式 (将生成日报 + 研究报告)")
    else:
        print("运行模式: 日报模式 (仅生成日报)")
    print("=" * 70)
    
    # 1. 加载配置
    themes = load_themes()
    if not themes:
        print("❌ 无法加载主题列表，退出")
        return
    
    whitelist_channels = load_whitelist_channels()
    api_key = load_youtube_api_key()
    if not api_key:
        print("❌ 无法加载 API Key，退出")
        return
    
    # 2. 对每个主题搜索
    print(f"\n🔍 开始搜索 {len(themes)} 个主题...")
    all_videos = []
    
    for theme in themes:
        print(f"  搜索主题: {theme}")
        videos = search_youtube_videos(theme, max_results=10, api_key=api_key)
        if videos:
            all_videos.extend(videos)
            print(f"    ✅ 找到 {len(videos)} 个视频")
        else:
            print("    ⚠️  未找到视频或搜索失败")
    
    if not all_videos:
        print("❌ 未找到任何视频，退出")
        return
    
    print(f"\n📊 合并前共找到 {len(all_videos)} 个视频")
    
    # 3. 合并去重
    unique_videos = merge_and_deduplicate_videos(all_videos)
    print(f"📊 去重后剩余 {len(unique_videos)} 个唯一视频")
    
    # 4. 时间窗口过滤：只考虑最近 DAYS_WINDOW 天的视频
    print(f"\n⏰ 应用时间窗口过滤（{DAYS_WINDOW}天）...")
    filtered_videos = [v for v in unique_videos if is_within_time_window(v['published_at'], DAYS_WINDOW)]
    excluded_count = len(unique_videos) - len(filtered_videos)
    if excluded_count > 0:
        print(f"   ⚠️  过滤掉 {excluded_count} 个超过 {DAYS_WINDOW} 天的视频")
    print(f"   ✅ 剩余 {len(filtered_videos)} 个视频参与排序")
    
    if not filtered_videos:
        print(f"❌ 时间窗口内（{DAYS_WINDOW}天）未找到任何视频，退出")
        return
    
    # 5. 评分
    print("\n⭐ 开始评分...")
    for video in filtered_videos:
        score = score_video(video, themes, whitelist_channels)
        video['score'] = score
        video['scoring_details'] = {
            'whitelist_bonus': 10 if video['channel_title'] in whitelist_channels else 0,
            'keyword_matches': count_theme_keywords(video['title'], themes) + count_theme_keywords(video['description'], themes),
            'time_bonus': calculate_time_score(video['published_at'])
        }
    
    # 6. 排序并取 Top 3
    sorted_videos = sorted(filtered_videos, key=lambda x: x['score'], reverse=True)
    top3_videos = sorted_videos[:3]
    
    print("\n🏆 Top 3 视频:")
    for i, video in enumerate(top3_videos, 1):
        print(f"  {i}. [{video['score']}分] {video['title']}")
        print(f"     频道: {video['channel_title']}")
        print(f"     链接: {video['url']}")
    
    # 7. 生成日期字符串
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 8. 创建输出目录
    base_dir = Path(__file__).parent
    raw_dir = base_dir / "raw" / "youtube"
    archive_dir = base_dir / "archive" / "youtube"
    raw_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    # 9. 保存原始数据
    raw_file = raw_dir / f"{today}_raw.json"
    raw_data = {
        "date": today,
        "themes_used": themes,
        "whitelist_channels": whitelist_channels,
        "days_window": DAYS_WINDOW,
        "total_videos_found": len(all_videos),
        "unique_videos": len(unique_videos),
        "filtered_videos_count": len(filtered_videos),
        "all_videos": sorted_videos  # 保存过滤后的视频，按评分排序
    }
    
    try:
        with open(raw_file, 'w', encoding='utf-8') as f:
            json.dump(raw_data, f, indent=2, ensure_ascii=False)
        print(f"\n💾 原始数据已保存到: {raw_file}")
    except Exception as e:
        print(f"❌ 保存原始数据失败: {e}")
        return
    
    # 10. 生成并保存日报
    action = generate_action(top3_videos)
    risk = generate_risk(sorted_videos, themes)
    
    daily_report = {
        "date": today,
        "themes_used": themes,
        "dimensions": [],  # 新增：用户可选的维度标签（如：["健康", "情绪", "工作"]），向后兼容
        "top3": [
            {
                "title": video['title'],
                "channel": video['channel_title'],
                "url": video['url'],
                "score": video['score'],
                "published_at": video['published_at'],
                "scoring_details": video['scoring_details']
            }
            for video in top3_videos
        ],
        "action": action,
        "risk": risk
    }
    
    archive_file = archive_dir / f"{today}.json"
    try:
        with open(archive_file, 'w', encoding='utf-8') as f:
            json.dump(daily_report, f, indent=2, ensure_ascii=False)
        print(f"💾 日报信号已保存到: {archive_file}")
    except Exception as e:
        print(f"❌ 保存日报信号失败: {e}")
        return
    
    # 11. 如果模式是 research，生成研究报告
    if mode == "research":
        llm = init_research_llm()
        if llm:
            try:
                research_report = generate_research_report(top3_videos, themes, llm)
                if research_report:
                    # 添加 sources 字段
                    research_report["sources"] = prepare_sources_data(top3_videos)
                    research_report["date"] = today
                    research_report["themes_used"] = themes
                    
                    # 保存研究报告
                    research_file = archive_dir / f"{today}_research.json"
                    with open(research_file, 'w', encoding='utf-8') as f:
                        json.dump(research_report, f, indent=2, ensure_ascii=False)
                    print(f"\n💾 研究报告已保存到: {research_file}")
                    
                    # 显示研究报告摘要
                    print("\n" + "=" * 70)
                    print("🔬 研究报告摘要")
                    print("=" * 70)
                    print(f"核心问题: {research_report.get('question', 'N/A')}")
                    print("\n关键发现:")
                    for i, finding in enumerate(research_report.get('key_findings', []), 1):
                        print(f"  {i}. {finding}")
                    print(f"\n为什么重要: {research_report.get('why_it_matters_to_me', 'N/A')}")
                    print("\n下一步行动:")
                    for i, step in enumerate(research_report.get('next_steps', []), 1):
                        print(f"  {i}. {step}")
                    print("=" * 70)
                else:
                    print("⚠️  研究报告生成失败，已跳过")
            except Exception as e:
                print(f"⚠️  生成研究报告时出错: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("⚠️  未配置 LLM，跳过研究模式")
    
    # 12. 显示日报摘要
    print("\n" + "=" * 70)
    print("📄 日报摘要")
    print("=" * 70)
    print(f"日期: {daily_report['date']}")
    print(f"主题: {', '.join(daily_report['themes_used'])}")
    print("\n推荐行动 (Action):")
    print(f"  {daily_report['action']}")
    print("\n风险评估 (Risk):")
    print(f"  {daily_report['risk']}")
    print("=" * 70)


if __name__ == "__main__":
    main()
