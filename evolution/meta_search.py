"""Meta ???????? harness.processors.planner ????? evolution?"""

from __future__ import annotations

from typing import Any, Dict, List


class MetaSearchEngine:
    """
    Meta-Harness 式自动搜索的局部原型

    对同一问题生成多条认知路径，用规则引擎快速评分，选择最优路径。
    对应建议9：引入Meta-Harness式自动搜索
    """

    def __init__(self, engine: Any, ai_client: Any):
        self.engine = engine
        self.ai = ai_client

    def generate_paths(self, question: str, num_paths: int = 3) -> List[Dict[str, Any]]:
        """
        生成多条认知路径

        每条路径包含不同的：
        - 晶体组合
        - 孔洞检测策略
        - 推理权重
        """
        crystals = self.engine.parse_crystals()
        if not crystals:
            return []

        paths = []

        # 路径1：标准检索（向量 + BM25 混合）
        path1 = self._build_path_standard(question, crystals)
        paths.append(path1)

        # 路径2：激进模式（偏重新颖性，优先高热度晶体）
        path2 = self._build_path_radical(question, crystals)
        paths.append(path2)

        # 路径3：保守模式（偏重稳定性，优先高置信度/固定晶体）
        path3 = self._build_path_conservative(question, crystals)
        paths.append(path3)

        return paths[:num_paths]

    def _build_path_standard(self, question: str, crystals: List) -> Dict[str, Any]:
        """标准检索路径"""
        ranked = self.engine.rank_crystals(question, crystals, top_k=5)
        return {
            "name": "标准路径",
            "crystals": [{"id": c.id, "content": c.content, "score": score} for score, c in ranked],
            "crystal_ids": [c.id for _, c in ranked],
            "strategy": "vector_bm25_hybrid"
        }

    def _build_path_radical(self, question: str, crystals: List) -> Dict[str, Any]:
        """激进路径：偏重新颖性和高热度"""
        # 按热度排序，取 top 10
        sorted_crystals = sorted(crystals, key=lambda c: c.heat, reverse=True)
        selected = sorted_crystals[:5]
        return {
            "name": "激进路径",
            "crystals": [{"id": c.id, "content": c.content, "heat": c.heat} for c in selected],
            "crystal_ids": [c.id for c in selected],
            "strategy": "heat_priority"
        }

    def _build_path_conservative(self, question: str, crystals: List) -> Dict[str, Any]:
        """保守路径：偏重固定晶体和 L1 层"""
        state = self.engine.load_layer_state()
        layers = state.get("layers", {})
        manual = state.get("manual_override", {})

        # 优先固定晶体
        fixed = [c for c in crystals if manual.get(c.id) == "L1_fixed"]
        l1 = [c for c in crystals if layers.get(c.id) == "L1" and c.id not in [f.id for f in fixed]]

        selected = fixed[:3] + l1[:2]
        if not selected:
            selected = crystals[:5]

        return {
            "name": "保守路径",
            "crystals": [{"id": c.id, "content": c.content, "layer": layers.get(c.id, "L2")} for c in selected],
            "crystal_ids": [c.id for c in selected],
            "strategy": "fixed_l1_priority"
        }

    def score_paths(self, paths: List[Dict[str, Any]], question: str) -> List[Dict[str, Any]]:
        """
        使用规则引擎快速评分（非 LLM）

        评分维度：
        - 引用晶体数（越多越好）
        - 晶体层级权重（L1 > L2 > L3）
        - 与指纹匹配度
        """
        try:
            fingerprint = self.engine.fingerprint_extractor.get_fingerprint()
            pref_role = fingerprint.preferred_role if fingerprint else "structural"
        except:
            pref_role = "structural"

        # 角色关键词权重
        role_keywords = {
            "radical": ["颠覆", "激进", "创新", "突破"],
            "conservative": ["稳健", "保守", "风险", "安全"],
            "structural": ["结构", "系统", "框架", "模型"],
            "executor": ["执行", "步骤", "操作", "落地"],
            "auditor": ["审计", "验证", "检查", "证据"]
        }
        fp_keywords = role_keywords.get(pref_role, role_keywords["structural"])

        scored_paths = []
        for path in paths:
            score = 0

            # 1. 晶体数量（0-20分）
            crystal_count = len(path.get("crystals", []))
            score += min(20, crystal_count * 4)

            # 2. 层级权重（0-30分）
            state = self.engine.load_layer_state()
            layers = state.get("layers", {})
            for c in path.get("crystals", []):
                cid = c.get("id") if isinstance(c, dict) else c.id
                layer = layers.get(cid, "L2")
                if layer == "L1":
                    score += 6
                elif layer == "L2":
                    score += 3
                else:
                    score += 1

            # 3. 指纹匹配度（0-30分）
            for c in path.get("crystals", []):
                content = c.get("content") if isinstance(c, dict) else c.content
                for kw in fp_keywords:
                    if kw in content:
                        score += 3
                        break
            score = min(30, score)

            # 4. 多样性奖励（0-20分）
            # 检查晶体是否来自不同领域（基于内容长度和关键词差异）
            contents = [c.get("content") if isinstance(c, dict) else c.content for c in path.get("crystals", [])]
            unique_keywords = set()
            for content in contents:
                words = content[:30].split()
                unique_keywords.update(words)
            diversity_score = min(20, len(unique_keywords) * 2)

            total_score = score + diversity_score

            scored_paths.append({
                "path": path,
                "score": total_score,
                "details": {
                    "crystal_count_score": min(20, len(path.get("crystals", [])) * 4),
                    "layer_score": score - min(20, len(path.get("crystals", [])) * 4) - diversity_score + 30,
                    "fingerprint_score": min(30, sum(3 for c in path.get("crystals", []) if any(kw in (c.get("content") if isinstance(c, dict) else c.content) for kw in fp_keywords))),
                    "diversity_score": diversity_score
                }
            })

        scored_paths.sort(key=lambda x: x["score"], reverse=True)
        return scored_paths

    def select_best_path(self, question: str) -> Dict[str, Any]:
        """
        选择最优认知路径
        """
        paths = self.generate_paths(question)
        if not paths:
            return {"error": "无法生成认知路径"}

        scored = self.score_paths(paths, question)
        best = scored[0] if scored else None

        return {
            "question": question,
            "paths": scored,
            "best_path": best,
            "selected_crystals": best["path"]["crystal_ids"] if best else []
        }

    def run_comparison(self, question: str) -> Dict[str, Any]:
        """
        运行认知路径对比（对外接口）
        """
        result = self.select_best_path(question)
        return result
