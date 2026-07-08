# processors/add_knowledge.py
"""知识添加处理器 - 使用 LLM 分析、分类并保存知识"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from hello_agents import HelloAgentsLLM
from core.file_manager import FileManager
from core.summary_manager import SummaryManager


class AddKnowledgeProcessor:
    """
    知识添加处理器

    功能：
    - 识别输入类型（文本/文件/URL）
    - 使用 LLM 分析内容
    - 智能分类和打标签
    - 提取关键概念
    - 生成文件名
    - 保存到 knowledge 目录
    - 更新 knowledge_summary.md
    """

    def __init__(self, llm: HelloAgentsLLM, file_manager: FileManager):
        """
        初始化 AddKnowledgeProcessor

        Args:
            llm: HelloAgentsLLM 实例
            file_manager: FileManager 实例
        """
        self.llm = llm
        self.file_manager = file_manager
        self.summary_manager = SummaryManager(file_manager)

    def _identify_input_type(self, input_data: str) -> str:
        """
        识别输入类型

        Args:
            input_data: 用户输入

        Returns:
            输入类型（text/file/url）
        """
        # 检查 URL
        if input_data.startswith("http://") or input_data.startswith("https://"):
            return "url"

        # 检查文件路径
        if (
            input_data.startswith("~")
            or input_data.startswith("/")
            or input_data.startswith("./")
        ):
            return "file"

        # 默认为文本
        return "text"

    def _read_file(self, file_path: str) -> str:
        """
        读取文件内容

        Args:
            file_path: 文件路径

        Returns:
            文件内容
        """
        # 处理 ~ 路径
        if file_path.startswith("~"):
            file_path = os.path.expanduser(file_path)

        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def _analyze_content(self, content: str, domain: str) -> Dict[str, any]:
        """
        使用 LLM 分析内容

        Args:
            content: 知识内容
            domain: 领域名称

        Returns:
            分析结果字典，包含：
            - category: 分类
            - tags: 标签列表
            - key_concepts: 关键概念列表
            - summary: 摘要
        """
        user_prompt = f"""请分析以下知识内容并提取关键信息：

【领域】
{domain}

【知识内容】
{content[:2000]}

请提供以下信息（JSON格式）：
{{
  "category": "分类（如：算法、概念、工具、实践等）",
  "tags": ["标签1", "标签2", "标签3"],
  "key_concepts": ["核心概念1", "核心概念2", "核心概念3"],
  "summary": "一句话摘要（50字以内）"
}}
"""

        messages = [
            {
                "role": "system",
                "content": "你是一个知识管理专家，擅长分析学习内容并提取关键信息、分类和标签。",
            },
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = self.llm.invoke(messages)

            # 尝试解析 JSON（简化实现：使用规则提取）
            return self._extract_metadata_from_text(response)
        except Exception:
            # 降级：使用规则分析
            return {
                "category": self._classify_content(content, domain),
                "tags": self._extract_tags_from_content(content),
                "key_concepts": self._extract_concepts_from_content(content),
                "summary": content[:100] + "..." if len(content) > 100 else content,
                "domain": domain,  # 添加 domain 字段
            }

    def _extract_metadata_from_text(self, text: str) -> Dict[str, any]:
        """
        从文本中提取元数据（简化版）

        Args:
            text: LLM 响应文本

        Returns:
            元数据字典
        """
        # 简化实现：基于规则提取
        lines = text.strip().split("\n")

        category = "通用"
        tags = []
        key_concepts = []
        summary = ""

        for line in lines:
            line = line.strip()
            if "分类" in line or "category" in line.lower():
                category = line.split("：")[-1].split(":")[-1].strip()
            elif "标签" in line or "tags" in line.lower():
                tags = [
                    tag.strip(" \"'[]{}")
                    for tag in line.split("：")[-1].split(":")[-1].split(",")
                ]
            elif "概念" in line or "concepts" in line.lower():
                key_concepts = [
                    c.strip(" \"'[]{}")
                    for c in line.split("：")[-1].split(":")[-1].split(",")
                ]
            elif "摘要" in line or "summary" in line.lower():
                summary = line.split("：")[-1].split(":")[-1].strip()

        return {
            "category": category if category else "通用",
            "tags": [t for t in tags if t],
            "key_concepts": [c for c in key_concepts if c],
            "summary": summary if summary else "知识笔记",
            "domain": domain,  # 添加 domain 字段
        }

    def _extract_tags_from_content(self, content: str) -> List[str]:
        """
        从内容中提取标签（基于关键词）

        Args:
            content: 内容文本

        Returns:
            标签列表
        """
        # 常见技术关键词
        keywords = [
            "算法",
            "数据结构",
            "机器学习",
            "深度学习",
            "Python",
            "JavaScript",
            "TypeScript",
            "Java",
            "框架",
            "库",
            "工具",
            "API",
            "前端",
            "后端",
            "全栈",
            "数据库",
            "理论",
            "实践",
            "教程",
            "示例",
        ]

        found = []
        content_lower = content.lower()
        for keyword in keywords:
            if keyword.lower() in content_lower:
                found.append(keyword)

        return found[:5]  # 最多5个标签

    def _extract_concepts_from_content(self, content: str) -> List[str]:
        """
        从内容中提取关键概念

        Args:
            content: 内容文本

        Returns:
            关键概念列表
        """
        # 提取以 # 开头的标题作为概念
        concepts = []
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("#"):
                # 去掉 # 符号和空格
                concept = line.lstrip("#").strip()
                if concept and len(concept) < 50:  # 限制长度
                    concepts.append(concept)

        return concepts[:5]  # 最多5个概念

    def _generate_filename(self, title: str, category: str = "") -> str:
        """
        生成文件名

        Args:
            title: 标题
            category: 分类（可选）

        Returns:
            文件名（带扩展名）
        """
        # 提取第一句话作为文件名
        if len(title) > 50:
            title = title[:50]

        # 清理特殊字符
        title = title.replace(" ", "-")
        title = "".join(c for c in title if c.isalnum() or c in "-_")

        # 添加时间戳
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")

        if category:
            base_name = f"{timestamp}-{category}-{title}"
        else:
            base_name = f"{timestamp}-{title}"

        return f"{base_name}.md"  # 添加 .md 扩展名

    def _save_knowledge(
        self, domain: str, content: str, metadata: Dict[str, any]
    ) -> Path:
        """
        保存知识笔记

        Args:
            domain: 领域名称
            content: 知识内容
            metadata: 元数据

        Returns:
            保存的文件路径
        """
        # 生成文件名（_generate_filename 已包含 .md 扩展名）
        title = content.split("\n")[0].lstrip("#").strip()
        filename = self._generate_filename(title, metadata.get("category", ""))

        # 添加元数据到内容
        full_content = f"""# {title}

> **分类**: {metadata.get('category', '通用')}
> **标签**: {', '.join(metadata.get('tags', []))}
> **添加时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

{content}

## 关键概念
{chr(10).join(f"- {c}" for c in metadata.get('key_concepts', []))}

## 摘要
{metadata.get('summary', '无')}
"""

        # 保存文件
        self.file_manager.save_knowledge(domain, filename, full_content)

        # 返回完整路径
        return self.file_manager.BASE_DIR / domain / "knowledge" / filename

    def _classify_content(self, content: str, domain: str) -> str:
        """
        分类内容

        Args:
            content: 内容
            domain: 领域

        Returns:
            分类名称
        """
        # 基于规则的简单分类
        content_lower = content.lower()

        if any(
            word in content_lower for word in ["算法", "algorithm", "方法", "method"]
        ):
            return "算法"
        elif any(
            word in content_lower for word in ["概念", "concept", "原理", "principle"]
        ):
            return "概念"
        elif any(
            word in content_lower
            for word in ["工具", "tool", "框架", "framework", "库", "library"]
        ):
            return "工具"
        elif any(
            word in content_lower
            for word in ["实践", "practice", "案例", "case", "项目", "project"]
        ):
            return "实践"
        elif any(
            word in content_lower for word in ["教程", "tutorial", "指南", "guide"]
        ):
            return "教程"
        else:
            return "通用"

    def add(self, domain: str, input_data: str, input_type: str = None) -> str:
        """
        添加知识

        Args:
            domain: 领域名称
            input_data: 输入数据（文本/文件路径/URL）
            input_type: 输入类型（可选，自动识别）

        Returns:
            执行结果
        """
        # 识别输入类型
        if not input_type:
            input_type = self._identify_input_type(input_data)

        # 获取内容
        if input_type == "text":
            content = input_data
        elif input_type == "file":
            try:
                content = self._read_file(input_data)
            except Exception as e:
                return f"❌ 读取文件失败：{e}"
        elif input_type == "url":
            # 简化实现：提示用户复制内容
            content = f"# URL 知识\n\n来源：{input_data}\n\n请手动添加内容..."
        else:
            return f"❌ 未知的输入类型：{input_type}"

        # 分析内容
        metadata = self._analyze_content(content, domain)

        # 保存知识
        try:
            file_path = self._save_knowledge(domain, content, metadata)

            # 更新摘要
            self.summary_manager.update_knowledge_summary(domain, file_path.name)

            return f"""✅ 知识已添加

📁 保存位置: {domain}/knowledge/{file_path.name}
📊 分类: {metadata.get('category', '通用')}
🏷️  标签: {', '.join(metadata.get('tags', []))}
"""

        except Exception as e:
            return f"❌ 添加知识失败：{e}"
