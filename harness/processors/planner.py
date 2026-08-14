#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.benchmarks import BENCHMARK_QUESTIONS
from core.models import Conflict, TaskCard
from data.storage import FileIO
from external.ai_client import AIClient
from external.fetcher import ExternalFetcher
from governance.config import Config
from harness.engine import CrystalEngine
from harness.processors.debate import DebateEngine

class BaselineRunner:
    """
    运行标准测试问题，采集辩论系统基线数据。
    在代码修改前运行一次，生成基线 JSON，供 Day 3 对比。
    """
    
    def __init__(self, engine: CrystalEngine, ai_client: AIClient, roles: List[Dict]):
        self.engine = engine
        self.ai = ai_client
        self.roles = roles
        self.results = []
    
    def run(
        self,
        max_rounds: int = 2,
        question_limit: Optional[int] = None,
        output_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """运行基线测试；question_limit 限制题数，output_path 覆盖默认落盘位置。"""
        print("📊 开始基线采集...")
        questions = BENCHMARK_QUESTIONS
        if question_limit is not None:
            questions = questions[: max(0, int(question_limit))]
        total = len(questions)
        if total == 0:
            raise ValueError("question_limit 必须大于 0")
        
        for idx, question in enumerate(questions):
            print(f"\n[{idx+1}/{total}] 测试问题: {question[:50]}...")
            
            # 初始化辩论引擎
            debate = DebateEngine(
                self.ai,
                self.engine,
                self.roles,
                log=lambda m, l: print(f"  {m[:80]}"),
                progress_callback=None
            )
            
            # 运行辩论
            try:
                result = debate.run(question, mode="debate_full", max_rounds=max_rounds)
                metrics = self._extract_metrics(question, result)
            except Exception as e:
                print(f"  ❌ 错误: {e}")
                metrics = self._empty_metrics(question, str(e))
            
            self.results.append(metrics)
            
            # 打印简要结果
            print(f"  Jaccard: {metrics['jaccard_similarity']:.3f} | "
                  f"引用率: {metrics['crystal_reference_rate']:.1%} | "
                  f"审计反馈长度: {metrics['audit_feedback_avg_len']:.1f}")
        
        # 汇总统计
        summary = self._aggregate(self.results)
        
        # 写入 JSON
        output_path = output_path or Config.DATA_ROOT / "系统日志" / "辩论基线.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        baseline_data = {
            "timestamp": datetime.now().isoformat(),
            "total_questions": total,
            "max_rounds": max_rounds,
            "summary": summary,
            "details": self.results,
            "good_debate_criteria": [
                "最终答案包含至少 2 个可执行建议",
                "最终答案明确指出了至少 1 个风险",
                "one_sentence_conclusion 不超过 30 字",
                "至少 2 个不同角色在最后一轮出现观点修正（自我批判后的变化）"
            ]
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(baseline_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 基线数据已保存至: {output_path}")
        return baseline_data
    
    def _extract_metrics(self, question: str, result: Dict) -> Dict[str, Any]:
        """从单次辩论结果中提取全部指标"""
        rounds_data = result.get("rounds", [])
        if not rounds_data:
            return self._empty_metrics(question, "no_rounds")
        
        # 1. Jaccard 相似度：取最后一轮各角色回答的平均相似度
        last_round = rounds_data[-1]
        answers = [item["answer"] for item in last_round.get("answers", [])]
        if len(answers) >= 2:
            temp_debate = DebateEngine(self.ai, self.engine, self.roles, lambda m, l: None)
            jaccard = temp_debate._average_jaccard(answers)
        else:
            jaccard = 0.0
        
        # 2. 晶体引用率：统计所有发言中 [Cxxx] 或 [Hxxx] 的出现次数
        all_text = " ".join(answers)
        crystal_matches = re.findall(r'\[C\d+\]', all_text)
        hole_matches = re.findall(r'\[H\d+\]', all_text)
        total_refs = len(crystal_matches) + len(hole_matches)
        total_answers = len(answers)
        ref_rate = total_refs / max(1, total_answers)
        
        # 3. 审计反馈具体性：用平均反馈长度作为代理指标
        audit = last_round.get("audit", {})
        feedbacks = list(audit.get("feedback_by_role", {}).values())
        avg_feedback_len = sum(len(str(f)) for f in feedbacks) / max(1, len(feedbacks))
        
        # 4. 分歧丰富度：disagreement_map 中非空类别数
        disc_map = audit.get("disagreement_map", {})
        active_categories = [k for k, v in disc_map.items() if v]
        diversity_score = len(active_categories) / max(1, len(disc_map))
        
        # 5. 证据评分方差
        ev_scores = list(audit.get("evidence_scores", {}).values())
        if len(ev_scores) > 1:
            mean = sum(ev_scores) / len(ev_scores)
            variance = sum((s - mean) ** 2 for s in ev_scores) / len(ev_scores)
        else:
            variance = 0.0
        
        # 6. 最终答案有用性代理：优先读取 final_schema 五版本输出
        schema = result.get("final_schema") or {}
        board = schema.get("board_version") or result.get("board_version") or ""
        employee = schema.get("employee_version") or result.get("employee_version") or ""
        novice = schema.get("novice_version") or result.get("novice_version") or ""
        expert = schema.get("expert_version") or result.get("expert_version") or ""
        final = result.get("final") or {}
        one_sentence = final.get("one_sentence_conclusion", (board or "")[:30])
        student_answer = final.get("student_friendly_answer", novice)
        teacher_detail = final.get("teacher_detail", expert)
        raw_final = {
            "one_sentence_conclusion": one_sentence,
            "student_friendly_answer": student_answer,
            "teacher_detail": teacher_detail,
            "rigid_core": {
                "decision_summary": (board or "")[:200],
                "key_synthesis": (board or "")[:200],
            },
            "soft_wrap": employee,
        }
        
        return {
            "question": question,
            "jaccard_similarity": round(jaccard, 4),
            "crystal_reference_rate": round(ref_rate, 4),
            "audit_feedback_avg_len": round(avg_feedback_len, 1),
            "disagreement_diversity": round(diversity_score, 3),
            "evidence_score_variance": round(variance, 4),
            "one_sentence_len": len(one_sentence),
            "student_answer_len": len(student_answer),
            "teacher_detail_len": len(teacher_detail),
            "has_risks": "风险" in student_answer or "风险" in teacher_detail,
            "has_executable_actions": any(kw in student_answer for kw in ["步骤", "建议", "方法", "操作", "执行"]),
            "rounds_count": len(rounds_data),
            "total_roles": len(answers),
            "raw_final": raw_final
        }
    
    def _empty_metrics(self, question: str, reason: str) -> Dict:
        return {
            "question": question,
            "error": reason,
            "jaccard_similarity": 0.0,
            "crystal_reference_rate": 0.0,
            "audit_feedback_avg_len": 0.0,
            "disagreement_diversity": 0.0,
            "evidence_score_variance": 0.0,
            "one_sentence_len": 0,
            "student_answer_len": 0,
            "teacher_detail_len": 0,
            "has_risks": False,
            "has_executable_actions": False,
            "rounds_count": 0,
            "total_roles": 0
        }
    
    def _aggregate(self, results: List[Dict]) -> Dict[str, Any]:
        valid = [r for r in results if "error" not in r]
        if not valid:
            return {"error": "无有效结果"}
        
        keys = ["jaccard_similarity", "crystal_reference_rate", 
                "audit_feedback_avg_len", "disagreement_diversity", "evidence_score_variance",
                "one_sentence_len", "student_answer_len", "teacher_detail_len"]
        
        avg = {}
        for k in keys:
            vals = [r.get(k, 0) for r in valid]
            avg[k] = round(sum(vals) / len(vals), 4) if vals else 0
        
        avg["has_risks_rate"] = sum(1 for r in valid if r.get("has_risks", False)) / len(valid)
        avg["has_executable_rate"] = sum(1 for r in valid if r.get("has_executable_actions", False)) / len(valid)
        avg["total_valid"] = len(valid)
        avg["total_errors"] = len(results) - len(valid)
        
        return avg


# =============================================================================
class DailyPlanner:
    DEFAULT_KEYWORDS = ["AI", "认知科学", "教育学习", "Agent", "推理能力", "国产大模型"]
    STAGES = [
        "更新晶体分层",
        "外部信息采集",
        "价值评分筛选",
        "生成待确认卡片",
        "冲突预警",
        "孔洞进展评估",
        "Wondering 与日报整理",
    ]

    def __init__(
        self,
        engine: CrystalEngine,
        ai_client: AIClient,
        fetcher: ExternalFetcher,
        log_callback: Callable,
        update_status_callback: Callable,
    ):
        self.engine = engine
        self.ai = ai_client
        self.fetcher = fetcher
        self.log = log_callback
        self.update_status = update_status_callback
        self.today = date.today().isoformat()
        self.report_content = ""
        self.last_external = []
        self._reset_state()

    def _reset_state(self):
        self.started_at = time.time()
        self.deadline = self.started_at + Config.DAILY_PLAN_TIME_BUDGET_SECONDS
        self.keywords = list(self.DEFAULT_KEYWORDS)
        self.completed_stages: List[str] = []
        self.skipped_stages: List[str] = []
        self.candidates: List[Dict] = []
        self.scored_candidates: List[Dict] = []
        self.created_pending_ids: List[str] = []
        self.created_task_ids: List[str] = []
        self.wondering: List[str] = []
        self.interrupted_reason = ""
        self.progress_callback: Optional[Callable[[Dict], None]] = None
        self.stop_flag: Optional[Callable[[], bool]] = None

    def is_today_run(self) -> bool:
        last_run_file = Config.get_path("change_log").parent / "last_daily_run.txt"
        return last_run_file.exists() and last_run_file.read_text(encoding="utf-8").strip() == self.today

    def _mark_today_run(self):
        last_run_file = Config.get_path("change_log").parent / "last_daily_run.txt"
        last_run_file.parent.mkdir(parents=True, exist_ok=True)
        last_run_file.write_text(self.today, encoding="utf-8")

    def _task_cards_io(self, cards: Optional[List[Dict]] = None) -> Optional[List[Dict]]:
        """读取或写入任务卡片：cards=None 时读取并返回列表，否则写入并返回 None。"""
        if cards is None:
            if not FileIO.exists("task_cards"):
                return []
            try:
                return json.loads(FileIO.read("task_cards"))
            except Exception:
                return []
        FileIO.write("task_cards", json.dumps(cards, ensure_ascii=False, indent=2))
        return None

    @staticmethod
    def _stable_suffix(*parts: str) -> str:
        raw = "|".join(str(p) for p in parts)
        return f"{int(hashlib.sha256(raw.encode('utf-8')).hexdigest(), 16) % 1000:03d}"

    def _normalize_keywords(self, keywords: Optional[List[str]]) -> List[str]:
        if isinstance(keywords, str):
            raw = keywords
        else:
            raw = " ".join(str(x) for x in (keywords or []))
        parts = [p.strip() for p in re.split(r"[,，;；\s\n]+", raw) if p.strip()]
        result = []
        for item in parts:
            if item not in result:
                result.append(item)
        return result[:10] or list(self.DEFAULT_KEYWORDS)

    def _emit_progress(self, stage: str, progress: int, stage_index: int = 0):
        elapsed = int(time.time() - self.started_at)
        payload = {
            "stage": stage,
            "progress": max(0, min(100, int(progress))),
            "stage_index": stage_index,
            "stage_total": len(self.STAGES),
            "candidate_count": len(self.candidates),
            "pending_count": len(self.created_pending_ids),
            "task_count": len(self.created_task_ids),
            "elapsed_seconds": elapsed,
            "budget_seconds": int(self.deadline - self.started_at),
            "keywords": self.keywords,
        }
        self.update_status(f"{stage}：{payload['progress']}%")
        if self.progress_callback:
            self.progress_callback(payload)

    def _should_stop(self) -> bool:
        if self.stop_flag and self.stop_flag():
            self.interrupted_reason = "用户中断"
            return True
        if time.time() >= self.deadline:
            self.interrupted_reason = "达到 15 分钟预算"
            return True
        return False

    def _ensure_can_continue(self, next_stage: str):
        if self._should_stop():
            raise InterruptedError(self.interrupted_reason)
        self.log(f"▶ {next_stage}", "system")

    def _add_task_card(self, card: TaskCard):
        cards = self._task_cards_io() or []
        if any(
            c.get("type") == card.type
            and c.get("source") == card.source
            and c.get("title") == card.title
            and c.get("status") == "pending"
            for c in cards
        ):
            self.log(f"  已存在任务卡片，跳过重复生成：{card.title}", "system")
            return False
        cards.append(card.__dict__)
        self._task_cards_io(cards)
        self.created_task_ids.append(card.id)
        return True

    def _create_pending_card_from_info(self, info: Dict) -> str:
        pending_content = FileIO.read("pending")
        title = info.get("title", "")
        source = info.get("source", "")
        if title and source and title in pending_content and source in pending_content:
            self.log(f"  已存在待确认卡片，跳过重复生成：{title[:60]}", "system")
            return ""

        card_id = f"PENDING-{datetime.now().strftime('%Y%m%d%H%M%S')}-{self._stable_suffix(source, title)}"
        matched_holes = ", ".join(info.get("matched_holes", [])[:3]) or "暂无"
        matched_crystals = ", ".join(info.get("matched_crystals", [])[:3]) or "暂无"
        keywords = ", ".join(self.keywords)
        content = f"""## {card_id}
- 类型：{info.get('type', 'external')}
- 标题：{title}
- 来源：{source}
- 链接：{info.get('link', '')}
- 当日意向关键词：{keywords}
- 意向匹配原因：{info.get('intent_reason', '与今日关键词或核心孔洞存在潜在关联')}
- 价值评分：{info.get('value_score', 0):.2f}
- 匹配孔洞：{matched_holes}
- 匹配晶体：{matched_crystals}
- 内容摘要：{info.get('summary', '')[:500]}
- 建议动作：{info.get('suggested_action', '老师确认后决定是否转为晶体')}
- AI判断：可能与孔洞或 L1 晶体相关，建议确认后再转为晶体。
"""
        FileIO.append("pending", f"\n{content}\n")
        self.created_pending_ids.append(card_id)
        self.log(f"  📄 生成待确认卡片 {card_id}", "system")
        return card_id

    def _create_conflict_task_card(self, conflict: Conflict) -> str:
        """生成冲突任务卡片（升级版：包含冲突类型和严重程度）"""
        if conflict.similarity > 0.85:
            conflict_type = "高度重复"
            severity = "高"
            suggestion = "建议合并这两个晶体，保留更完整的一个"
        elif conflict.similarity > 0.70:
            conflict_type = "语义冲突"
            severity = "中"
            suggestion = "建议补充适用边界，明确两者的区分条件"
        else:
            conflict_type = "潜在关联"
            severity = "低"
            suggestion = "建议建立链接关系，说明两者的关联"

        card_id = f"TASK-{datetime.now().strftime('%Y%m%d%H%M%S')}-{self._stable_suffix(conflict.crystal_a, conflict.crystal_b)}"

        task = TaskCard(
            id=card_id,
            type="conflict",
            title=f"晶体冲突：{conflict.crystal_a} vs {conflict.crystal_b}",
            content=f"""冲突类型：{conflict_type}
严重程度：{severity}
相似度：{conflict.similarity:.2f}

A ({conflict.crystal_a}): {conflict.content_a}
B ({conflict.crystal_b}): {conflict.content_b}

建议动作：{suggestion}""",
            source=f"{conflict.crystal_a} vs {conflict.crystal_b}",
            suggested_action=suggestion,
            status="pending",
        )

        if not self._add_task_card(task):
            return ""
        self.log(f"  [WARN] 生成{conflict_type}任务卡片 {card_id} (严重程度: {severity})", "system")
        return card_id

    def _collect_external_info(self) -> Tuple[List[str], List[Dict]]:
        data = self.fetcher.fetch_all()
        insights_text = self.fetcher.build_insights(data)
        structured = self.fetcher.build_structured_insights(data)

        for keyword in self.keywords:
            if self._should_stop():
                break
            try:
                self.log(f"  关键词追踪：{keyword}", "system")
                for paper in self.fetcher.fetch_arxiv_papers(query=keyword, max_results=3):
                    if paper.startswith("(") or not paper.strip():
                        continue
                    title = paper.split(" (")[0].strip()
                    structured.append({
                        "type": "keyword_arxiv",
                        "title": title,
                        "summary": title,
                        "link": "",
                        "source": f"arXiv({keyword})",
                        "intent_keyword": keyword,
                    })
                for news in self.fetcher.fetch_baidu_news(keyword, max_results=2):
                    if news.startswith("(") or not news.strip():
                        continue
                    structured.append({
                        "type": "keyword_news",
                        "title": news,
                        "summary": news,
                        "link": "",
                        "source": f"百度新闻({keyword})",
                        "intent_keyword": keyword,
                    })
                if Config.ENABLE_BAIDU_QIANFAN:
                    qianfan_items = self.fetcher.fetch_qianfan(keyword, max_results=3)
                    if qianfan_items:
                        for item in qianfan_items:
                            item["intent_keyword"] = keyword
                            structured.append(item)
                    else:
                        self.log(
                            f"⚠️ 百度千帆未返回有效结果（{keyword}），降级到现有抓取",
                            "warning",
                        )
            except Exception as exc:
                self.log(f"  关键词 {keyword} 追踪失败：{exc}", "warning")

        deduped = []
        seen = set()
        for item in structured:
            title = re.sub(r"\s+", " ", item.get("title", "")).strip()
            source = item.get("source", "")
            key = title.lower()
            if not title or key in seen:
                continue
            seen.add(key)
            item["title"] = title
            item.setdefault("summary", title)
            item.setdefault("source", source)
            deduped.append(item)
            if len(deduped) >= Config.DAILY_PLAN_MAX_CANDIDATES:
                break
        return insights_text, deduped

    def _score_candidates(self, candidates: List[Dict]) -> List[Dict]:
        holes = self.engine.parse_holes()
        crystals = self.engine.parse_crystals()
        scored = []
        for item in candidates:
            text = f"{item.get('title', '')} {item.get('summary', '')}"
            keyword_hits = [kw for kw in self.keywords if kw.lower() in text.lower()]
            keyword_score = min(1.0, len(keyword_hits) * 0.35)

            hole_scores = []
            for hole in holes:
                try:
                    score = self.engine.match_info_to_hole(text, hole.content)
                except Exception:
                    score = self.engine._simple_similarity(text, hole.content)
                if score > 0.25:
                    hole_scores.append((score, hole.id))
            hole_scores.sort(reverse=True)

            ranked_crystals = self.engine.rank_crystals(text, crystals, top_k=3) if crystals else []
            crystal_score = ranked_crystals[0][0] if ranked_crystals else 0.0
            crystal_score = min(1.0, crystal_score / 5.0)

            source_bonus = 0.15 if item.get("type", "").startswith(("keyword", "arxiv", "huggingface")) else 0.05
            value_score = round(keyword_score + min(0.6, (hole_scores[0][0] if hole_scores else 0.0)) + crystal_score + source_bonus, 3)
            item["value_score"] = value_score
            item["matched_holes"] = [hid for _score, hid in hole_scores[:3]]
            item["matched_crystals"] = [crystal.id for _score, crystal in ranked_crystals[:3]]
            item["intent_reason"] = "、".join(keyword_hits) if keyword_hits else "与核心孔洞或 L1 晶体存在语义关联"
            item["suggested_action"] = "优先确认并考虑转为晶体" if value_score >= 0.8 else "暂存观察，必要时转为任务"
            scored.append(item)
        scored.sort(key=lambda x: x.get("value_score", 0), reverse=True)
        return scored[:Config.DAILY_PLAN_TOP_ITEMS]

    def _summarize_candidate(self, item: Dict) -> Dict:
        if self._should_stop():
            return item
        prompt = f"""请对这条外部信息做教师可读的价值摘要。
标题：{item.get('title')}
来源：{item.get('source')}
今日关键词：{', '.join(self.keywords)}
匹配孔洞：{', '.join(item.get('matched_holes', []))}
匹配晶体：{', '.join(item.get('matched_crystals', []))}

输出 120 字以内，说明为什么值得看，以及可能转成什么认知晶体。"""
        try:
            item["summary"] = self.ai.chat(prompt)[:500]
        except Exception as exc:
            self.log(f"  摘要生成失败，使用原摘要：{exc}", "warning")
        return item

    def _update_hole_progress_with_evidence(self, external_insights: List[Dict]) -> Tuple[List[Dict], str]:
        holes = self.engine.parse_holes()
        progress = self.engine.load_hole_progress()
        important_holes = [h for h in holes if h.urgency >= 0.7]
        if not external_insights:
            hole_list = [{"id": h.id, "content": h.content, "progress": int(progress.get(h.id, 0.0) * 100), "urgency": h.urgency} for h in important_holes]
            return hole_list, "无外部信息，无法评估填充进展。"

        updated = False
        evidence_log = []
        for hole in important_holes:
            hid = hole.id
            cur = progress.get(hid, 0.0)
            best_match = 0.0
            best_info = None
            for info in external_insights:
                text = f"{info.get('title', '')} {info.get('summary', '')}"
                try:
                    score = self.engine.match_info_to_hole(text, hole.content)
                except Exception:
                    score = self.engine._simple_similarity(text, hole.content)
                if score > best_match:
                    best_match = score
                    best_info = info
            if best_info and best_match > 0.6:
                increment = min(0.15, best_match * 0.2)
                new_prog = min(1.0, cur + increment)
                if new_prog > cur:
                    progress[hid] = new_prog
                    updated = True
                    evidence_log.append(f"{hid} 进度 {int(cur * 100)}% -> {int(new_prog * 100)}%，依据：{best_info['title'][:60]}")
        if updated:
            self.engine.save_hole_progress(progress)
            for ev in evidence_log:
                self.engine._append_change_log("孔洞填充", ev)
        hole_progress_list = [{"id": h.id, "content": h.content, "progress": int(progress.get(h.id, 0.0) * 100), "urgency": h.urgency} for h in important_holes]
        desc = "\n".join(evidence_log[:5]) if evidence_log else "暂无显著填充进展。"
        return hole_progress_list, desc

    def _generate_wondering(self, external_insights: List[str]) -> List[str]:
        l0_holes, l1_crystals = self.engine.get_attention_context()
        l0_text = "\n".join([f"- {h.id}: {h.content[:80]}" for h in l0_holes])
        l1_text = "\n".join([f"- {c.id}: {c.content[:60]}" for c in l1_crystals[:30]])
        external_text = "\n".join(external_insights[:8])
        prompt = f"""基于今日关键词、核心孔洞、L1晶体和外部信息，生成 3 个“我好奇”的问题。
今日关键词：{', '.join(self.keywords)}
L0核心孔洞：
{l0_text}
L1晶体：
{l1_text}
外部信息：
{external_text[:2000]}

每行一个问题，不加编号。"""
        try:
            reply = self.ai.chat(prompt)
            lines = [l.strip(" -0123456789.、") for l in reply.strip().split("\n") if l.strip()]
        except Exception:
            lines = []
        defaults = [
            "如何把今日外部信息转化为可验证的学习策略？",
            "哪些新信息可能挑战当前晶体树的默认判断？",
            "哪个孔洞最值得下一步集中探索？",
        ]
        unique = []
        for q in lines + defaults:
            if q and not any(self.engine._simple_similarity(q, u) > 0.8 for u in unique):
                unique.append(q)
            if len(unique) >= 3:
                break
        self.wondering = [f"{i + 1}. {q}" for i, q in enumerate(unique[:3])]
        return self.wondering

    def _generate_report(
        self,
        status: str,
        external_insights: List[str],
        hole_progress_list: List[Dict],
        created_pending_count: int,
        created_conflict_count: int,
    ):
        elapsed = time.time() - self.started_at
        top_lines = [
            f"- {item.get('title', '')[:90]} | {item.get('source', '')} | 评分 {item.get('value_score', 0):.2f}"
            for item in self.scored_candidates[:10]
        ]
        hole_text = "\n".join([
            f"- {hp['id']}「{hp['content'][:40]}」填充进度 {hp['progress']}%"
            for hp in hole_progress_list[:5]
        ]) or "暂无高紧迫度孔洞进展。"
        completed = "、".join(self.completed_stages) or "暂无"
        skipped = "、".join([s for s in self.STAGES if s not in self.completed_stages]) or "无"
        report = f"""# 自主工作日报 {self.today}

## 运行状态
- 状态：{status}
- 当日意向关键词：{', '.join(self.keywords)}
- 实际耗时：{elapsed:.1f} 秒
- 已完成阶段：{completed}
- 未完成阶段：{skipped}
- 中断/收尾原因：{self.interrupted_reason or '正常完成'}

## 高价值候选
{chr(10).join(top_lines) if top_lines else '暂无高价值候选。'}

## 孔洞填充
{hole_text}

## Wondering
{chr(10).join(self.wondering) if self.wondering else '暂无。'}

## 成果清单
- 已生成 PENDING：{created_pending_count} 张
- PENDING ID：{', '.join(self.created_pending_ids) or '无'}
- 已生成任务卡：{created_conflict_count} 张
- 任务卡 ID：{', '.join(self.created_task_ids) or '无'}

## 下次继续建议
- 优先复查本次 Top 候选中的前 3 条。
- 若本次中断，下次可继续使用关键词：{', '.join(self.keywords)}
"""
        self.engine._append_change_log("自主工作日报", report)
        self.report_content = report

    def _finish_partial(self, hole_progress_list: Optional[List[Dict]] = None):
        self.log(f"⏸ 每日计划部分完成：{self.interrupted_reason}", "warning")
        self._generate_report(
            "中断" if self.interrupted_reason == "用户中断" else "超时部分完成",
            [f"- {c.get('title', '')}" for c in self.scored_candidates[:10]],
            hole_progress_list or [],
            len(self.created_pending_ids),
            len(self.created_task_ids),
        )
        progress = int(len(self.completed_stages) / max(1, len(self.STAGES)) * 100)
        self._emit_progress("整理中断成果完成", min(99, progress), len(self.completed_stages))

    def run(
        self,
        intent_keywords: Optional[List[str]] = None,
        time_budget_seconds: int = None,
        stop_flag: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[[Dict], None]] = None,
    ):
        self._reset_state()
        self.keywords = self._normalize_keywords(intent_keywords)
        budget = int(time_budget_seconds or Config.DAILY_PLAN_TIME_BUDGET_SECONDS)
        self.deadline = self.started_at + max(60, budget)
        self.stop_flag = stop_flag
        self.progress_callback = progress_callback
        hole_progress_list: List[Dict] = []
        external_insights_text: List[str] = []

        self.log("📅 开始执行每日自主工作计划（15分钟高价值版）...", "system")
        self.log(f"  今日意向关键词：{', '.join(self.keywords)}", "system")
        self.update_status("执行每日计划中...")

        try:
            self._ensure_can_continue(self.STAGES[0])
            self._emit_progress(self.STAGES[0], 5, 1)
            L1, L2, L3 = self.engine.update_crystal_layers()
            self.log(f"  分层完成：L1={len(L1)}，L2={len(L2)}，L3={len(L3)}", "success")
            archived = self.engine.archive_cold_crystals()
            self.log(f"  冷晶体归档：{len(archived)} 条", "system")
            # ===== Day 3 新增：运行元原语并触发链 =====
            try:
                self.log("🧠 运行元层元原语（含触发链）...", "system")
                meta_results = self.engine.meta.run_all_primitives()
                triggered = meta_results.get("triggered_chains", [])
                if triggered:
                    self.log(f"✅ 触发链执行：{len(triggered)} 条链被触发", "success")
                    for chain in triggered:
                        self.log(f"   {chain['chain']}: {chain['source']} → {chain['target']} (通过: {chain['passed']})", "system")
                else:
                    self.log("ℹ️ 无触发链条件满足", "system")
            except Exception as e:
                self.log(f"⚠️ 元原语执行异常：{e}", "warning")           
            self.completed_stages.append(self.STAGES[0])

            self._ensure_can_continue(self.STAGES[1])
            self._emit_progress(self.STAGES[1], 15, 2)
            external_insights_text, self.candidates = self._collect_external_info()
            self.log(f"  采集候选信息：{len(self.candidates)} 条", "system")
            self.completed_stages.append(self.STAGES[1])

            self._ensure_can_continue(self.STAGES[2])
            self._emit_progress(self.STAGES[2], 32, 3)
            self.scored_candidates = self._score_candidates(self.candidates)
            self.log(f"  入选高价值候选：{len(self.scored_candidates)} 条", "system")
            self.completed_stages.append(self.STAGES[2])

            self._ensure_can_continue(self.STAGES[3])
            self._emit_progress(self.STAGES[3], 48, 4)
            for item in self.scored_candidates[:Config.DAILY_PLAN_MAX_PENDING_CARDS]:
                if self._should_stop():
                    raise InterruptedError(self.interrupted_reason)
                summarized = self._summarize_candidate(item)
                self._create_pending_card_from_info(summarized)
            self.completed_stages.append(self.STAGES[3])

            self._ensure_can_continue(self.STAGES[4])
            self._emit_progress(self.STAGES[4], 62, 5)

            # 使用向量级矛盾检测（自动选择最优方法）
            try:
                conflicts = self.engine.detect_conflicts(method="auto")
            except Exception as e:
                self.log(f"  向量矛盾检测失败，降级到 Jaccard: {e}", "warning")
                conflicts = self.engine.detect_conflicts(method="jaccard")

            conflict_count = len(conflicts)
            created_count = 0

            # 按严重程度排序：高优先级先处理
            high_severity = [c for c in conflicts if c.similarity > 0.85]
            medium_severity = [c for c in conflicts if 0.70 < c.similarity <= 0.85]
            low_severity = [c for c in conflicts if c.similarity <= 0.70]

            for conflict in high_severity[:3]:
                if self._should_stop():
                    raise InterruptedError(self.interrupted_reason)
                if self._create_conflict_task_card(conflict):
                    created_count += 1

            for conflict in medium_severity[:2]:
                if self._should_stop():
                    raise InterruptedError(self.interrupted_reason)
                if self._create_conflict_task_card(conflict):
                    created_count += 1

            if low_severity:
                self.log(f"  [INFO] 发现 {len(low_severity)} 个潜在关联（低优先级，暂不生成任务卡）", "system")

            self.log(f"  冲突预警：发现 {conflict_count} 个潜在问题（高:{len(high_severity)}, 中:{len(medium_severity)}, 低:{len(low_severity)}），生成 {created_count} 张任务卡", "system")
            self.completed_stages.append(self.STAGES[4])

            self._ensure_can_continue(self.STAGES[5])
            self._emit_progress(self.STAGES[5], 76, 6)
            hole_progress_list, hole_desc = self._update_hole_progress_with_evidence(self.scored_candidates)
            self.log(f"  孔洞评估完成：{hole_desc[:120]}", "system")
            self.completed_stages.append(self.STAGES[5])

            # ===== 新增：负能力修剪 + 验证门控 =====
            self._emit_progress("负能力修剪", 82)
            self.log("🧹 开始负能力修剪与验证门控...", "system")

            try:
                low_contribution = self.engine.get_low_contribution_crystals(threshold=25.0)
                self.log(f"  发现 {len(low_contribution)} 条低贡献晶体", "system")

                verification_count = 0
                archive_count = 0

                for item in low_contribution[:10]:  # 每轮最多处理10条，避免任务泛滥
                    if self._should_stop():
                        raise InterruptedError(self.interrupted_reason)

                    # 执行验证门控
                    validation = self._validate_crystal_for_retention(item)

                    if validation["suggested_action"] == "keep":
                        self.log(f"  ✅ {item['crystal_id']} 通过验证，保留", "system")
                    elif validation["suggested_action"] == "pending_review":
                        # 生成 PENDING 验证卡片
                        self._generate_verification_pending_card(item, validation)
                        verification_count += 1
                    else:  # archive
                        # 记录但不立即删除（等待用户确认）
                        self.log(f"  📦 {item['crystal_id']} 建议归档（等待用户确认）", "system")
                        archive_count += 1

                self.log(f"  验证门控完成：保留 {len(low_contribution) - verification_count - archive_count} 条，待复核 {verification_count} 条，建议归档 {archive_count} 条", "system")

            except Exception as e:
                self.log(f"  ⚠️ 负能力修剪异常：{e}", "warning")

            self._ensure_can_continue(self.STAGES[6])
            self._emit_progress(self.STAGES[6], 90, 7)
            self._generate_wondering(external_insights_text)
            self._generate_report("完成", external_insights_text, hole_progress_list, len(self.created_pending_ids), len(self.created_task_ids))
            self.completed_stages.append(self.STAGES[6])
            self._mark_today_run()
            elapsed = time.time() - self.started_at
            self.log(f"✅ 每日计划执行完成，耗时 {elapsed:.1f} 秒", "success")
            self.update_status("每日计划完成")
            self._emit_progress("每日计划完成", 100, len(self.STAGES))
        except InterruptedError:
            self._finish_partial(hole_progress_list)
            self.update_status("每日计划已中断并整理成果")
        except Exception as exc:
            self.interrupted_reason = f"异常：{exc}"
            self._finish_partial(hole_progress_list)
            self.update_status("每日计划异常收尾")
            raise

        self.log("\n" + "=" * 60 + "\n" + self.report_content + "\n" + "=" * 60, "system")
        return {
            "status": "partial" if self.interrupted_reason else "done",
            "reason": self.interrupted_reason,
            "report": self.report_content,
            "pending_ids": self.created_pending_ids,
            "task_ids": self.created_task_ids,
            "keywords": self.keywords,
        }

    def _validate_crystal_for_retention(self, crystal_data: Dict) -> Dict[str, Any]:
        """
        验证门控自我进化：判断低贡献晶体是否应该保留

        验证规则（可配置）：
        1. 是否至少被 3 个不同角色引用过？
        2. 是否有独立来源支持？（外部案例或论文引用）
        3. 是否被用户主动标记为“固定”？
        4. 是否在最近 60 天内被访问过？

        Returns:
            {
                "passed": bool,
                "rules": [{"name": str, "passed": bool, "reason": str}],
                "summary": str,
                "suggested_action": str  # "keep" | "pending_review" | "archive"
            }
        """
        cid = crystal_data.get("crystal_id")
        if not cid:
            return {"passed": False, "summary": "缺少晶体ID", "suggested_action": "archive"}

        # 获取晶体完整信息
        crystals = self.engine.parse_crystals()
        crystal = next((c for c in crystals if c.id == cid), None)
        if not crystal:
            return {"passed": False, "summary": f"未找到晶体 {cid}", "suggested_action": "archive"}

        rules = []
        passed_count = 0
        total_rules = 4

        # 规则1：至少被 3 个不同晶体引用
        ref_count = sum(1 for c in crystals if cid in c.links)
        rule1_passed = ref_count >= 2  # 放宽到 2 个引用
        rules.append({
            "name": "被其他晶体引用",
            "passed": rule1_passed,
            "reason": f"被 {ref_count} 条晶体引用" if rule1_passed else f"仅被 {ref_count} 条晶体引用（需要 ≥2）"
        })
        if rule1_passed:
            passed_count += 1

        # 规则2：是否有外部来源（检查链接中是否有 H 开头或外部引用）
        has_external = any(link.startswith("H") or link.startswith("http") for link in crystal.links)
        rule2_passed = has_external
        rules.append({
            "name": "有外部来源或孔洞支撑",
            "passed": rule2_passed,
            "reason": "有孔洞或外部链接支撑" if rule2_passed else "仅内部引用，建议补充外部来源"
        })
        if rule2_passed:
            passed_count += 1

        # 规则3：是否被固定到 L1
        state = self.engine.load_layer_state()
        layers = state.get("layers", {})
        manual = state.get("manual_override", {})
        is_fixed = manual.get(cid) == "L1_fixed"
        rule3_passed = is_fixed or layers.get(cid) == "L1"
        rules.append({
            "name": "在核心区（L1）或已固定",
            "passed": rule3_passed,
            "reason": "已固定到 L1" if is_fixed else "在 L1 层" if layers.get(cid) == "L1" else "不在核心区"
        })
        if rule3_passed:
            passed_count += 1

        # 规则4：最近 60 天内被访问过
        last_accessed = state.get("last_accessed", {})
        last = last_accessed.get(cid)
        if last:
            try:
                days_since = (date.today() - date.fromisoformat(last)).days
                rule4_passed = days_since <= 60
            except:
                rule4_passed = False
        else:
            rule4_passed = False
        rules.append({
            "name": "近期被访问",
            "passed": rule4_passed,
            "reason": f"{days_since} 天前访问" if last and rule4_passed else "60 天以上未访问" if last else "从未访问"
        })
        if rule4_passed:
            passed_count += 1

        # 综合判断：至少通过 2 条规则（宽松标准）
        passed = passed_count >= 2

        if passed:
            suggested_action = "keep"
            summary = f"通过 {passed_count}/{total_rules} 条验证规则，建议保留"
            self.engine.log_evolution_event(
                "verification_passed",
                {
                    "crystal_id": cid,
                    "crystal_content": crystal.content[:80],
                    "rules_passed": passed_count,
                    "rules_total": total_rules,
                    "trigger": "daily_plan"
                }
            )
        elif passed_count >= 1:
            suggested_action = "pending_review"
            summary = f"仅通过 {passed_count}/{total_rules} 条验证规则，建议进入 PENDING 复核"
        else:
            suggested_action = "archive"
            summary = f"未通过验证（{passed_count}/{total_rules}），建议归档"

        return {
            "passed": passed,
            "rules": rules,
            "summary": summary,
            "suggested_action": suggested_action,
            "crystal_id": cid,
            "content": crystal.content
        }

    def _generate_verification_pending_card(self, crystal_data: Dict, validation_result: Dict) -> str:
        """
        为低贡献晶体生成 PENDING 验证卡片
        """
        cid = crystal_data.get("crystal_id")
        if not cid:
            return ""

        card_id = f"PENDING-VERIFY-{datetime.now().strftime('%Y%m%d%H%M%S')}-{self._stable_suffix(cid)}"

        rules_text = "\n".join([
            f"  - {'✅' if r['passed'] else '❌'} {r['name']}：{r['reason']}"
            for r in validation_result.get("rules", [])
        ])

        content = f"""## {card_id}
- 类型：验证门控·低贡献晶体复核
- 晶体ID：{cid}
- 晶体内容：{crystal_data.get('content', '')[:80]}
- 贡献得分：{crystal_data.get('score', 0):.1f}
- 验证结果：{validation_result.get('summary', '')}
- 建议动作：{validation_result.get('suggested_action', 'pending_review')}
- 验证详情：
{rules_text}
- AI判断：此晶体贡献度较低，建议人工确认是否保留、修改或归档。
"""
        FileIO.append("pending", f"\n{content}\n")
        self.created_pending_ids.append(card_id)
        self.log(f"  📄 生成验证门控卡片 {card_id} (晶体 {cid})", "system")
        return card_id

# =============================================================================
