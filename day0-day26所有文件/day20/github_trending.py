#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 20: GitHub Trending 自动抓取 + 晶体化模块
功能：
1. 抓取 GitHub Trending 热门仓库
2. 自动生成认知晶体
3. 存入 skills/trending/ 目录
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import requests
from bs4 import BeautifulSoup


# 延迟导入，避免循环
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
# 在方法内部导入
from crystal_tree_all_in_one_day import Config, CrystalEngine, FileIO, AIClient

class GitHubTrendingCrystalizer:
    """
    GitHub Trending 抓取与晶体化引擎
    """

    def __init__(self, engine: Optional[CrystalEngine] = None, ai_client: Optional[AIClient] = None):
        self.engine = engine or CrystalEngine(FileIO())
        self.ai = ai_client or AIClient()
        self.trending_dir = Config.DATA_ROOT / "skills" / "trending"
        self.trending_dir.mkdir(parents=True, exist_ok=True)

    def fetch_trending(self, language: str = "", since: str = "daily", max_items: int = 10) -> List[Dict]:
        """
        抓取 GitHub Trending

        Args:
            language: 编程语言筛选（如 "python", "javascript"），空字符串表示全部
            since: 时间范围 daily/weekly/monthly
            max_items: 最多抓取数量

        Returns:
            List[Dict]: 仓库信息列表
        """
        url = f"https://github.com/trending/{language}?since={since}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            print(f"⚠️ GitHub Trending 抓取失败：{e}")
            # 降级：使用模拟数据用于测试
            return self._get_mock_data()

        repos = []
        articles = soup.select("article.Box-row")
        for article in articles[:max_items]:
            try:
                # 仓库名称
                h2 = article.select_one("h2.h3 a")
                if not h2:
                    continue
                repo_name = h2.text.strip().replace("\n", "").replace(" ", "")
                repo_url = "https://github.com" + h2.get("href", "")

                # 描述
                desc_elem = article.select_one("p.col-9")
                description = desc_elem.text.strip() if desc_elem else ""

                # 语言
                lang_elem = article.select_one("span[itemprop='programmingLanguage']")
                language_used = lang_elem.text.strip() if lang_elem else ""

                # Star 数
                star_elem = article.select_one("a[href*='/stargazers']")
                stars = star_elem.text.strip() if star_elem else "0"

                # Fork 数
                fork_elem = article.select_one("a[href*='/forks']")
                forks = fork_elem.text.strip() if fork_elem else "0"

                # 今日新增 Star（如果有）
                today_star_elem = article.select_one("span.d-inline-block.float-sm-right")
                today_stars = today_star_elem.text.strip() if today_star_elem else ""

                repos.append({
                    "name": repo_name,
                    "url": repo_url,
                    "description": description,
                    "language": language_used,
                    "stars": stars,
                    "forks": forks,
                    "today_stars": today_stars,
                    "fetched_at": datetime.now().isoformat()
                })
            except Exception as e:
                print(f"⚠️ 解析仓库条目失败：{e}")
                continue

        return repos[:max_items]

    def _get_mock_data(self) -> List[Dict]:
        """模拟数据（网络失败时使用）"""
        return [
            {
                "name": "langchain-ai/langchain",
                "url": "https://github.com/langchain-ai/langchain",
                "description": "Building applications with LLMs through composability",
                "language": "Python",
                "stars": "82.5k",
                "forks": "12.3k",
                "today_stars": "256",
                "fetched_at": datetime.now().isoformat()
            },
            {
                "name": "microsoft/autogen",
                "url": "https://github.com/microsoft/autogen",
                "description": "A framework that enables the development of LLM applications",
                "language": "Python",
                "stars": "25.1k",
                "forks": "3.2k",
                "today_stars": "142",
                "fetched_at": datetime.now().isoformat()
            },
            {
                "name": "openai/openai-cookbook",
                "url": "https://github.com/openai/openai-cookbook",
                "description": "Examples and guides for using the OpenAI API",
                "language": "Jupyter Notebook",
                "stars": "56.8k",
                "forks": "9.1k",
                "today_stars": "87",
                "fetched_at": datetime.now().isoformat()
            }
        ]

    def generate_crystal_for_repo(self, repo: Dict) -> Dict[str, Any]:
        """
        为单个仓库生成认知晶体

        Args:
            repo: 仓库信息字典

        Returns:
            Dict: 晶体信息（id, content, links, etc.）
        """
        repo_name = repo.get("name", "")
        description = repo.get("description", "")
        language = repo.get("language", "")
        stars = repo.get("stars", "0")
        url = repo.get("url", "")

        # 生成晶体内容
        prompt = f"""
请为以下 GitHub 开源项目生成一个认知晶体（不超过80字）：

项目名称：{repo_name}
描述：{description}
主要语言：{language}
Stars：{stars}

要求：
1. 提炼该项目的核心认知价值或设计哲学
2. 与认知晶体树的已有概念（如"认知架构"、"接口思维"、"生长优于堆积"等）建立关联
3. 格式：一句话核心洞察 + 关联晶体关键词

直接输出晶体内容，不要其他说明。
"""
        try:
            crystal_content = self.ai.chat(prompt, temperature=0.6)
            if not crystal_content or len(crystal_content) < 10:
                crystal_content = f"{repo_name}：{description[:50]}... 与认知架构设计相关"
        except Exception as e:
            print(f"⚠️ 晶体生成失败 {repo_name}：{e}")
            crystal_content = f"{repo_name}：{description[:50]}... 开源项目认知晶体"

        # 生成 Skill ID
        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', repo_name)
        crystal_id = f"GHT-{datetime.now().strftime('%Y%m%d')}-{hash(safe_name) % 10000:04d}"

        # 构建晶体数据
        crystal_data = {
            "id": crystal_id,
            "content": crystal_content[:80],
            "links": [],
            "input_conditions": ["GitHub Trending 自动抓取"],
            "execution_logic": f"从 {repo_name} 提取认知模式",
            "output_format": "晶体摘要",
            "validation_criteria": ["内容非空", "长度<=80字"],
            "source": "github_trending",
            "repo": repo
        }

        return crystal_data

    def save_crystal(self, crystal_data: Dict) -> bool:
        """
        将晶体保存到 skills/trending/ 目录
        """
        crystal_id = crystal_data.get("id")
        if not crystal_id:
            print("❌ 保存失败：缺少晶体ID")
            return False

        try:
            # 创建 Skill 目录
            skill_dir = self.trending_dir / crystal_id
            skill_dir.mkdir(parents=True, exist_ok=True)
            print(f"   📁 创建目录：{skill_dir}")

            # 提取数据
            content = crystal_data.get("content", "")
            repo = crystal_data.get("repo", {})
            
            # 安全处理 input_conditions
            input_conditions = crystal_data.get('input_conditions', [])
            if isinstance(input_conditions, dict):
                input_conditions = ["GitHub Trending 自动抓取"]
            elif not isinstance(input_conditions, list):
                input_conditions = ["GitHub Trending 自动抓取"]
            
            links = crystal_data.get('links', [])
            if not isinstance(links, list):
                links = []
            
            execution_logic = crystal_data.get('execution_logic', '')
            output_format = crystal_data.get('output_format', '')
            validation_criteria = crystal_data.get('validation_criteria', [])
            if not isinstance(validation_criteria, list):
                validation_criteria = ["内容非空", "长度<=80字"]

            # 写入 CRYSTAL.md
            md_content = f"""# {crystal_id} - GitHub Trending 认知晶体

## 核心内容
{content}

## 来源仓库
- 名称：{repo.get('name', '')}
- URL：{repo.get('url', '')}
- 语言：{repo.get('language', '')}
- Stars：{repo.get('stars', '0')}
- 描述：{repo.get('description', '')}
- 抓取时间：{datetime.now().isoformat()}

## 链接关系
{', '.join(links) if links else '无'}

## 代码化字段
- 输入条件：{', '.join(input_conditions) if input_conditions else '无'}
- 执行逻辑：{execution_logic}
- 输出格式：{output_format}
- 验证标准：{', '.join(validation_criteria) if validation_criteria else '无'}

## 元数据
- 来源：GitHub Trending
- 生成时间：{datetime.now().isoformat()}
"""
            crystal_md_path = skill_dir / "CRYSTAL.md"
            crystal_md_path.write_text(md_content, encoding="utf-8")
            print(f"   ✅ 写入 CRYSTAL.md：{crystal_md_path}")

            # 写入 validate.py（骨架）
            validate_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GitHub Trending 晶体验证脚本"""
import sys

def validate(content: str) -> dict:
    checks = {
        "has_content": bool(content and content.strip()),
        "length_ok": 10 <= len(content) <= 500,
    }
    score = sum(1 for v in checks.values() if v) / len(checks)
    return {"valid": score >= 0.75, "checks": checks, "score": round(score, 2)}
'''
            (skill_dir / "validate.py").write_text(validate_content, encoding="utf-8")

            # 创建 references 目录
            (skill_dir / "references").mkdir(exist_ok=True)

            # 写入 repo.json（包含原始数据）
            with open(skill_dir / "repo.json", "w", encoding="utf-8") as f:
                json.dump(repo, f, ensure_ascii=False, indent=2)

            print(f"   ✅ 晶体 {crystal_id} 保存成功")
            return True

        except Exception as e:
            print(f"   ❌ 保存晶体 {crystal_id} 失败：{e}")
            import traceback
            traceback.print_exc()
            return False
    def run_daily(self, max_items: int = 10) -> Dict[str, Any]:
        """
        每日运行：抓取 Trending → 生成晶体 → 保存

        Args:
            max_items: 最多处理数量

        Returns:
            Dict: 运行结果
        """
        print("📡 开始抓取 GitHub Trending...")
        repos = self.fetch_trending(max_items=max_items)
        if not repos:
            return {"status": "failed", "message": "无数据", "repos": [], "crystals": []}

        print(f"✅ 抓取到 {len(repos)} 个仓库")

        results = []
        for repo in repos:
            print(f"  🔮 生成晶体：{repo.get('name')}")
            crystal = self.generate_crystal_for_repo(repo)
            if self.save_crystal(crystal):
                results.append(crystal)
                print(f"    ✅ 已保存：{crystal.get('id')}")
            else:
                print(f"    ❌ 保存失败")

        # 生成索引文件
        self._generate_index(results)

        return {
            "status": "success",
            "message": f"处理 {len(repos)} 个仓库，生成 {len(results)} 个晶体",
            "repos": repos,
            "crystals": results,
            "timestamp": datetime.now().isoformat()
        }

    def _generate_index(self, crystals: List[Dict]):
        """生成 trends_index.json"""
        index_path = self.trending_dir / "trends_index.json"
        data = {
            "last_updated": datetime.now().isoformat(),
            "total": len(crystals),
            "crystals": crystals
        }
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_trending_crystals(self, limit: int = 10) -> List[Dict]:
        """获取已保存的 Trending 晶体（干净数据）"""
        # 优先从索引文件读取
        index_path = self.trending_dir / "trends_index.json"
        if index_path.exists():
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    crystals = data.get("crystals", [])
                    # 仅保留必要字段，清洗数据
                    result = []
                    for c in crystals[:limit]:
                        if not c.get("id"):
                            continue
                        # 提取 content，如果是 dict 则取第一个值
                        content = c.get("content", "")
                        if isinstance(content, dict):
                            content = next(iter(content.values())) if content else ""
                        result.append({
                            "id": c["id"],
                            "content": content[:80] if content else "",
                            "path": str(self.trending_dir / c["id"])
                        })
                    return result
            except Exception as e:
                print(f"⚠️ 读取索引失败：{e}")
        
        # 降级：从目录读取
        crystals = []
        for d in self.trending_dir.iterdir():
            if d.is_dir() and d.name.startswith("GHT-"):
                crystal_md = d / "CRYSTAL.md"
                if crystal_md.exists():
                    try:
                        content = crystal_md.read_text(encoding="utf-8")
                        match = re.search(r"## 核心内容\s*\n+(.*?)(?=\n##|\Z)", content, re.DOTALL)
                        if match:
                            crystals.append({
                                "id": d.name,
                                "content": match.group(1).strip()[:80],
                                "path": str(d)
                            })
                    except:
                        continue
                if len(crystals) >= limit:
                    break
        return crystals[:limit]