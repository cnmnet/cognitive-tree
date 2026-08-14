#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import random
import re
import time
from datetime import datetime
from typing import Callable, Dict, List
from urllib.parse import quote

import requests

from core.dependencies import ARXIV_AVAILABLE, BS4_AVAILABLE, BeautifulSoup, HTTPAdapter, REQUESTS_AVAILABLE, Retry
from external.network import NetworkManager
from governance.config import Config

class ExternalFetcher:
    def __init__(self, log_callback: Callable = None, file_io: Callable = None):
        self.log_callback = log_callback
        self.file_io = file_io
        self._has_requests = REQUESTS_AVAILABLE
        self._has_bs4 = BS4_AVAILABLE
        self._has_arxiv = ARXIV_AVAILABLE

    def _log(self, msg: str, tag: str = "system"):
        if self.log_callback:
            self.log_callback(msg, tag)

    def translate_to_english(self, text: str) -> str:
        if not re.search(r'[\u4e00-\u9fff]', text):
            return text
        if not self._has_requests:
            return text
        try:
            url = "https://api.mymemory.translated.net/get"
            params = {"q": text, "langpair": "zh|en", "de": "a@b.c"}
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                translated = resp.json().get("responseData", {}).get("translatedText", "")
                if translated and translated != text:
                    return translated
        except:
            pass
        return text

    def fetch_arxiv_papers(self, query: str = "cat:cs.AI", max_results: int = 5) -> List[str]:
        if not self._has_arxiv:
            return ["(需要安装 arxiv 库)"]
        import arxiv
        query = self.translate_to_english(query)
        self._log(f"  搜索查询: {query}", "system")
        session = requests.Session()
        retry_strategy = Retry(total=Config.MAX_RETRIES, backoff_factor=Config.BACKOFF_FACTOR, status_forcelist=[429,500,502,503,504], allowed_methods=["GET","HEAD"])
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update({"User-Agent": NetworkManager.get_random_user_agent(), "Accept": "application/atom+xml,application/xml"})
        client = arxiv.Client(page_size=min(max_results,20), delay_seconds=3.0, num_retries=Config.MAX_RETRIES)
        client._session = session
        search = arxiv.Search(query=query, max_results=max_results, sort_by=arxiv.SortCriterion.SubmittedDate)
        try:
            papers = []
            for paper in client.results(search):
                pub_date = paper.published.date().isoformat() if paper.published else ""
                title = paper.title.strip().replace('\n',' ')
                papers.append(f"{title} (发布于: {pub_date})" if pub_date else title)
                if len(papers) >= max_results:
                    break
            return papers if papers else ["(未找到相关论文)"]
        except Exception as e:
            return [f"(arXiv 请求失败: {e})"]

    def fetch_hf_papers(self, max_results: int = 3) -> List[str]:
        if not self._has_requests or not self._has_bs4:
            return ["(需要 requests + beautifulsoup4)"]
        response = NetworkManager.safe_request(f"{Config.HF_MIRROR}/papers", use_mirror=True, log_callback=self._log)
        if not response:
            return ["(HuggingFace镜像站连接失败)"]
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            for link in soup.select('a[href^="/papers/"]')[:max_results]:
                title = link.get_text(strip=True)
                if title and 20 < len(title) < 200:
                    results.append(title[:120])
            return results if results else ["(HF页面结构可能已更新)"]
        except:
            return ["(HF解析失败)"]

    def fetch_baidu_news(self, keyword: str, max_results: int = 2) -> List[str]:
        if not self._has_requests or not self._has_bs4:
            return ["(需要 requests + beautifulsoup4)"]
        search_url = f"https://www.baidu.com/s?rtt=1&tn=news&word={quote(keyword)}"
        response = NetworkManager.safe_request(search_url, log_callback=self._log)
        if not response:
            return ["(百度新闻搜索失败)"]
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            for container in soup.select('.result, .c-container')[:max_results*2]:
                title_elem = container.select_one('h3 a, .news-title a')
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    title = re.sub(r'百度快照|查看更多|资讯|\|.*', '', title)
                    title = re.sub(r'\s+', ' ', title).strip()
                    if title and len(title) > 10 and keyword[:2] in title:
                        results.append(title[:80])
                    if len(results) >= max_results:
                        break
            return results if results else [f"(未找到关于 '{keyword}' 的新闻)"]
        except:
            return ["(百度新闻解析异常)"]

    def fetch_all(self) -> Dict:
        self._log("📡 开始增强型外部信源抓取...", "system")
        cache_data = self._load_cache()
        if cache_data:
            self._log("  使用缓存数据（12小时内有效）", "system")
            return cache_data
        self._log("  缓存无效或已过期，开始在线抓取（可能需要1-2分钟）...", "system")
        data = {}
        self._log("  🔬 抓取 arXiv AI论文...", "system")
        data['ai_papers'] = self.fetch_arxiv_papers(query="cat:cs.AI OR cat:cs.LG OR cat:cs.CL", max_results=5)
        self._log("  🤗 抓取 HuggingFace 论文...", "system")
        data['hf_papers'] = self.fetch_hf_papers(max_results=3)
        self._log("  📰 抓取国产大模型动态...", "system")
        llm_keywords = ["面壁智能 新模型", "智谱AI 最新进展", "阿里通义 大模型"]
        llm_news = {}
        for kw in llm_keywords:
            self._log(f"    搜索: {kw}", "system")
            llm_news[kw] = self.fetch_baidu_news(kw, max_results=2)
            time.sleep(random.uniform(2,3))
        data['llm_news'] = llm_news
        self._log("  🧠 抓取认知科学论文...", "system")
        data['neuro_papers'] = self.fetch_arxiv_papers(query="cat:q-bio.NC", max_results=4)
        data['timestamp'] = datetime.now().isoformat()
        self._save_cache(data)
        return data

    # ========================================================================
    # Day 11: 外部信息注入器增强
    # ========================================================================

    def fetch_by_source(self, source_type: str, query: str = None, max_results: int = 5) -> List[Dict]:
        """
        按指定信源类型抓取信息
        
        Args:
            source_type: 信源类型 (arxiv, huggingface, news, custom)
            query: 查询关键词
            max_results: 最大结果数
        
        Returns:
            List[Dict]: 抓取结果列表
        """
        results = []
        
        if source_type == "arxiv":
            papers = self.fetch_arxiv_papers(query=query or "cat:cs.AI", max_results=max_results)
            for paper in papers:
                if not paper.startswith("("):
                    results.append({
                        "type": "arxiv",
                        "title": paper,
                        "summary": paper,
                        "source": "arXiv",
                        "query": query,
                        "fetched_at": datetime.now().isoformat()
                    })
        
        elif source_type == "huggingface":
            papers = self.fetch_hf_papers(max_results=max_results)
            for paper in papers:
                if not paper.startswith("("):
                    results.append({
                        "type": "huggingface",
                        "title": paper,
                        "summary": paper,
                        "source": "HuggingFace",
                        "query": query,
                        "fetched_at": datetime.now().isoformat()
                    })
        
        elif source_type == "news":
            if query:
                news_list = self.fetch_baidu_news(query, max_results=max_results)
                for news in news_list:
                    if not news.startswith("("):
                        results.append({
                            "type": "news",
                            "title": news,
                            "summary": news,
                            "source": f"百度新闻({query})",
                            "query": query,
                            "fetched_at": datetime.now().isoformat()
                        })
        
        elif source_type == "custom":
            # 自定义信源：调用 fetch_all 后过滤
            try:
                all_data = self.fetch_all()
                structured = self.build_structured_insights(all_data)
                for item in structured[:max_results]:
                    results.append({
                        "type": item.get("type", "custom"),
                        "title": item.get("title", ""),
                        "summary": item.get("summary", ""),
                        "source": item.get("source", "Custom"),
                        "query": query,
                        "fetched_at": datetime.now().isoformat()
                    })
            except Exception as e:
                # Day 3 修改：仅记录错误，不返回任何数据
                if self.log_callback:
                    self.log_callback(f"[ERROR] fetch_by_source(custom) 失败: {e}", "error")
                # 返回空列表
                return []
        
        return results

    def fetch_qianfan(self, query: str = "", max_results: int = 3) -> List[Dict]:
        """百度千帆 AI 搜索（垂直切片，默认关闭；失败时返回空列表由调用方降级）。"""
        if not Config.ENABLE_BAIDU_QIANFAN:
            return []
        try:
            from external.providers.baidu_qianfan import BaiduQianfanProvider
            provider = BaiduQianfanProvider(log_callback=self._log)
            if not provider.is_available():
                self._log("百度千帆未配置 API Key，跳过", "warning")
                return []
            results = provider.search(query, top_k=max_results)
        except Exception as e:
            self._log(f"百度千帆搜索失败（降级到现有抓取）: {e}", "warning")
            return []
        items = []
        for result in results:
            title = (result.title or "").strip()
            if not title or title.startswith("(") or "模拟" in title:
                continue
            items.append({
                "type": "qianfan",
                "title": title[:120],
                "summary": (result.content or title)[:300],
                "link": result.url or "",
                "source": result.source or "百度千帆",
                "query": query,
                "fetched_at": datetime.now().isoformat(),
            })
        return items

    # ========== 新增：多语言新闻抓取（全球认知雷达） ==========
    def fetch_multilingual_news(self, max_per_lang: int = 5) -> Dict[str, List[Dict]]:
        """
        抓取5种语言（中/英/日/德/西）的当日新闻标题。
        返回: { 'zh': [...], 'en': [...], 'ja': [...], 'de': [...], 'es': [...] }
        每条新闻: {'title': str, 'summary': str, 'source': str, 'language': str}
        """
        import feedparser
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        # 创建带重试和超时的 requests Session
        session = requests.Session()
        retries = Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        session.mount('http://', HTTPAdapter(max_retries=retries))
        session.mount('https://', HTTPAdapter(max_retries=retries))
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

        rss_urls = {
            'zh': 'https://news.google.com/rss?hl=zh-CN&gl=CN&ceid=CN:zh-Hans',
            'en': 'https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en',
            'ja': 'https://news.google.com/rss?hl=ja&gl=JP&ceid=JP:ja',
            'de': 'https://news.google.com/rss?hl=de&gl=DE&ceid=DE:de',
            'es': 'https://news.google.com/rss?hl=es&gl=ES&ceid=ES:es',
        }

        result = {}
        any_success = False

        for lang, url in rss_urls.items():
            self._log(f"  📡 抓取 {lang} 新闻: {url}", "system")
            try:
                # 用 requests 获取内容（带超时）
                resp = session.get(url, timeout=15)
                resp.raise_for_status()
                # 用 feedparser 解析
                feed = feedparser.parse(resp.content)
                if not feed.entries:
                    self._log(f"  ⚠️ {lang} RSS 返回空条目", "warning")
                    result[lang] = []
                    continue

                entries = []
                for entry in feed.entries[:max_per_lang]:
                    title = entry.get('title', '').strip()
                    if not title:
                        continue
                    summary = entry.get('summary', title)
                    summary = re.sub(r'<[^>]+>', '', summary)  # 清理 HTML 标签
                    entries.append({
                        'title': title,
                        'summary': summary[:200],
                        'source': 'Google News',
                        'language': lang
                    })
                result[lang] = entries
                any_success = True
                self._log(f"  ✅ {lang} 抓取成功，共 {len(entries)} 条", "system")

            except requests.exceptions.RequestException as e:
                self._log(f"  ❌ {lang} 网络请求失败: {e}", "error")
                result[lang] = []
            except Exception as e:
                self._log(f"  ❌ {lang} 解析失败: {e}", "error")
                result[lang] = []

        # 如果没有任何语言成功，降级到模拟数据（但会附带当前时间以便验证）
        if not any_success:
            self._log("⚠️ 所有语言抓取均失败，使用模拟数据", "warning")
            return self._mock_multilingual_news()

        return result

    def _mock_multilingual_news(self) -> Dict[str, List[Dict]]:
        """模拟多语言新闻数据（附带当前时间戳，用于验证）"""
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return {
            'zh': [
                {'title': f'中国AI芯片突破7nm制程 (模拟 {now})', 'summary': '中科院宣布实现7nm制程AI芯片量产', 'source': '模拟', 'language': 'zh'},
                {'title': f'国产大模型通过备案 (模拟 {now})', 'summary': '多个国产大模型通过国家备案', 'source': '模拟', 'language': 'zh'}
            ],
            'en': [
                {'title': f'OpenAI releases GPT-5 (mock {now})', 'summary': 'GPT-5 with improved reasoning and longer context', 'source': '模拟', 'language': 'en'},
                {'title': f'Google launches new AI search (mock {now})', 'summary': 'AI-powered search with multi-modal capabilities', 'source': '模拟', 'language': 'en'}
            ],
            'ja': [
                {'title': f'ソニーがAIセンサーを発表 (模擬 {now})', 'summary': '新しいAIセンサーは省電力で高精度', 'source': '模拟', 'language': 'ja'},
                {'title': f'トヨタが自動運転AIを強化 (模擬 {now})', 'summary': '2027年までに完全自動運転を目指す', 'source': '模拟', 'language': 'ja'}
            ],
            'de': [
                {'title': f'Deutsche KI-Strategie (Mock {now})', 'summary': 'Bundesregierung investiert 5 Milliarden in KI', 'source': '模拟', 'language': 'de'},
                {'title': f'Siemens baut KI-Fabrik (Mock {now})', 'summary': 'neue Fabrik mit KI-gesteuerter Produktion', 'source': '模拟', 'language': 'de'}
            ],
            'es': [
                {'title': f'España apuesta por IA (Mock {now})', 'summary': 'El gobierno lanza un plan de IA para 2030', 'source': '模拟', 'language': 'es'},
                {'title': f'Nuevo algoritmo de traducción (Mock {now})', 'summary': 'mejora la precisión en lenguas minoritarias', 'source': '模拟', 'language': 'es'}
            ]
        }
        
    def fetch_scheduled(self, sources: List[str], queries: List[str] = None) -> Dict[str, List[Dict]]:
        """
        按调度抓取多个信源
        
        Args:
            sources: 信源列表 ["arxiv", "huggingface", "news"]
            queries: 对应的查询关键词列表
        
        Returns:
            Dict[str, List[Dict]]: 按信源分组的抓取结果
        """
        results = {}
        queries = queries or []
        
        for i, source in enumerate(sources):
            query = queries[i] if i < len(queries) else None
            self._log(f"  📡 抓取信源: {source}" + (f" (关键词: {query})" if query else ""), "system")
            
            try:
                data = self.fetch_by_source(source, query, max_results=3)
                results[source] = data
                self._log(f"     ✅ 获取 {len(data)} 条结果", "system")
            except Exception as e:
                self._log(f"     ❌ 抓取失败: {e}", "warning")
                results[source] = []
        
        return results

    def fetch_and_store(self, sources: List[str], queries: List[str] = None) -> Dict:
        """
        抓取并全量入库
        
        Args:
            sources: 信源列表
            queries: 查询关键词列表
        
        Returns:
            Dict: 入库结果
        """
        # 1. 执行抓取
        fetch_results = self.fetch_scheduled(sources, queries)
        
        # 2. 加载现有缓存
        cache_data = self._load_cache()
        if not cache_data:
            cache_data = {}
        
        # 3. 合并新数据（全量入库，不去重）
        if "all_fetched" not in cache_data:
            cache_data["all_fetched"] = []
        
        timestamp = datetime.now().isoformat()
        for source, items in fetch_results.items():
            for item in items:
                item["_source"] = source
                item["_stored_at"] = timestamp
                cache_data["all_fetched"].append(item)
        
        # 4. 更新缓存时间戳
        cache_data["_last_fetch"] = timestamp
        cache_data["_fetch_sources"] = sources
        
        # 5. 保存缓存
        self._save_cache(cache_data)
        
        return {
            "success": True,
            "fetched_count": sum(len(items) for items in fetch_results.values()),
            "sources": sources,
            "results": fetch_results,
            "stored_at": timestamp,
            "total_stored": len(cache_data.get("all_fetched", []))
        }

    def get_stored_external_data(self, limit: int = 50) -> List[Dict]:
        """
        获取已存储的外部数据
        
        Args:
            limit: 返回数量限制
        
        Returns:
            List[Dict]: 外部数据列表
        """
        cache_data = self._load_cache()
        if not cache_data:
            return []
        
        all_fetched = cache_data.get("all_fetched", [])
        # 按存储时间倒序排列
        sorted_data = sorted(all_fetched, key=lambda x: x.get("_stored_at", ""), reverse=True)
        return sorted_data[:limit]

    def get_external_stats(self) -> Dict:
        """
        获取外部数据统计信息
        """
        cache_data = self._load_cache()
        if not cache_data:
            return {
                "total_stored": 0,
                "last_fetch": None,
                "sources": [],
                "by_source": {}
            }
        
        all_fetched = cache_data.get("all_fetched", [])
        
        # 按信源统计
        by_source = {}
        for item in all_fetched:
            source = item.get("_source", "unknown")
            if source not in by_source:
                by_source[source] = 0
            by_source[source] += 1
        
        return {
            "total_stored": len(all_fetched),
            "last_fetch": cache_data.get("_last_fetch"),
            "sources": cache_data.get("_fetch_sources", []),
            "by_source": by_source
        }

    def _load_cache(self) -> Dict:
        if self.file_io is None:
            raise RuntimeError("ExternalFetcher 需要注入 file_io")
        if not self.file_io.exists("external_cache"):
            return {}
        try:
            cache = json.loads(self.file_io.read("external_cache"))
            cache_time = datetime.fromisoformat(cache.get("timestamp", "2000-01-01"))
            if (datetime.now() - cache_time).total_seconds()/3600 < 12:
                return cache.get("data", {})
        except:
            pass
        return {}

    def _save_cache(self, data: Dict):
        if self.file_io is None:
            raise RuntimeError("ExternalFetcher 需要注入 file_io")
        self.file_io.write("external_cache", json.dumps({"timestamp": datetime.now().isoformat(), "data": data}, ensure_ascii=False, indent=2))

    def build_insights(self, data: Dict) -> List[str]:
        insights = []
        ai_papers = data.get('ai_papers', [])
        if ai_papers and not ai_papers[0].startswith("("):
            insights.append("## AI学术前沿（arXiv）")
            insights.extend([f"- {p}" for p in ai_papers[:5]])
        else:
            insights.append("## AI学术前沿（arXiv）\n- （暂无最新论文）")
        insights.append("\n## 模型与应用动态")
        hf_papers = data.get('hf_papers', [])
        if hf_papers and not hf_papers[0].startswith("("):
            insights.append("### HuggingFace 论文")
            insights.extend([f"- {p}" for p in hf_papers])
        llm_news = data.get('llm_news', {})
        if llm_news:
            insights.append("\n## 国产大模型动态")
            for kw, news_list in llm_news.items():
                insights.append(f"### {kw}")
                for n in news_list:
                    insights.append(f"- {n}")
        neuro_papers = data.get('neuro_papers', [])
        if neuro_papers and not neuro_papers[0].startswith("("):
            insights.append("\n## 认知科学前沿")
            insights.extend([f"- {p}" for p in neuro_papers])
        if len(insights) <= 2:
            insights.append("（外部追踪未获取到有效数据）")
        return insights

    def build_structured_insights(self, data: Dict) -> List[Dict]:
        insights = []
        for paper in data.get('ai_papers', []):
            if paper.startswith("(") or not paper.strip():
                continue
            title = paper.split(" (发布于:")[0].strip()
            insights.append({"type": "arxiv", "title": title, "summary": title, "link": "", "source": "arXiv"})
        for paper in data.get('hf_papers', []):
            if paper.startswith("(") or not paper.strip():
                continue
            insights.append({"type": "huggingface", "title": paper, "summary": paper, "link": "", "source": "HuggingFace"})
        for kw, news_list in data.get('llm_news', {}).items():
            for news in news_list:
                if news.startswith("(") or not news.strip():
                    continue
                insights.append({"type": "news", "title": news, "summary": news, "link": "", "source": f"百度新闻({kw})"})
        return insights

