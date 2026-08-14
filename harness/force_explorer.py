#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Dict, List

from data.storage import FileIO
from external.fetcher import ExternalFetcher
from governance.config import Config

class ForceExplorer:
    """
    强制探索调度器
    高优先级孔洞超时自动升级，强制分配计算资源
    """
    
    def __init__(self, engine: Any, log_callback=None, ai_client=None):
        self.engine = engine
        self.log = log_callback or (lambda msg, level="system": print(msg))
        self.ai_client = ai_client  # 新增：AI客户端
        self.exploration_log = []
        self._load_exploration_state()

  
    def _load_exploration_state(self):
        """加载探索状态"""
        state_file = Config.DATA_ROOT / "系统日志" / "exploration_state.json"
        if state_file.exists():
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.exploration_log = data.get("exploration_log", [])
            except:
                self.exploration_log = []
        else:
            self.exploration_log = []
    
    def _save_exploration_state(self):
        """保存探索状态"""
        state_file = Config.DATA_ROOT / "系统日志" / "exploration_state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({
                "exploration_log": self.exploration_log[-100:],  # 只保留最近100条
                "last_saved": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
    
    def check_holes_for_escalation(self, threshold_days: int = 7) -> List[Dict]:
        """
        检查哪些孔洞需要升级
        
        Args:
            threshold_days: 超时阈值（天）
        
        Returns:
            List[Dict]: 需要升级的孔洞列表
        """
        holes = self.engine.parse_holes()
        progress = self.engine.load_hole_progress()
        
        escalated = []
        today = date.today()
        
        for hole in holes:
            # 只检查高紧迫度孔洞 (urgency >= 0.7)
            if hole.urgency < 0.7:
                continue
            
            # 获取孔洞的进度和最后更新时间
            hole_progress = progress.get(hole.id, 0.0)
            
            # 检查是否有探索记录
            last_explored = None
            for record in self.exploration_log:
                if record.get("hole_id") == hole.id:
                    last_explored = record.get("timestamp")
                    break
            
            if last_explored:
                try:
                    days_since = (today - date.fromisoformat(last_explored.split("T")[0])).days
                except:
                    days_since = threshold_days + 1
            else:
                days_since = threshold_days + 1
            
            # 如果进度低于0.5且超过阈值天数，标记为需要升级
            if hole_progress < 0.5 and days_since >= threshold_days:
                escalated.append({
                    "hole_id": hole.id,
                    "content": hole.content,
                    "urgency": hole.urgency,
                    "current_progress": hole_progress,
                    "days_since_exploration": days_since,
                    "reason": f"超过 {threshold_days} 天未取得进展"
                })
        
        return escalated


    def force_explore(self, hole_id: str, force_level: str = "medium") -> Dict:
        """强制探索一个孔洞"""
        from datetime import datetime

        # 1. 获取孔洞信息
        holes = self.engine.parse_holes()
        hole = next((h for h in holes if h.id == hole_id), None)
        if not hole:
            return {"success": False, "error": f"孔洞 {hole_id} 不存在"}

        # 2. 获取相关晶体
        crystals = self.engine.parse_crystals()
        related_crystals = []
        for c in crystals:
            if hole_id in c.links:
                related_crystals.append(c)

        if len(related_crystals) < 3:
            keywords = hole.content[:30].split()[:5]
            query = " ".join(keywords)
            ranked = self.engine.rank_crystals(query, crystals, top_k=5)
            related_crystals = [c for _, c in ranked]

        # 3. 尝试获取外部信息
        try:
            fetcher = ExternalFetcher(log_callback=self.log, file_io=FileIO)
            external_data = fetcher.fetch_by_source("custom", query=hole.content[:50], max_results=3)
        except:
            external_data = []

        exploration_result = {
            "hole_id": hole_id,
            "force_level": force_level,
            "timestamp": datetime.now().isoformat(),
            "related_crystals": [c.id for c in related_crystals[:5]],
            "external_sources": len(external_data),
            "status": "completed",
            "crystal_generated": None
        }

        # 4. 尝试生成新晶体
        try:
            if self.ai_client:
                ai = self.ai_client
            else:
                from external.ai_client import AIClient
                ai = AIClient()

            prompt = f"""
请根据以下孔洞信息，生成一个认知晶体（不超过80字）：
孔洞ID: {hole_id}
孔洞内容: {hole.content}
相关晶体: {', '.join([c.id for c in related_crystals[:3]])}
外部信息: {external_data[:2] if external_data else '无'}

要求：
1. 晶体内容必须是一个可验证的认知模式或原则
2. 必须与孔洞内容直接相关
3. 格式：直接输出晶体内容，不要其他内容
"""
            try:
                new_crystal_content = ai.chat(prompt, temperature=0.7)
                if new_crystal_content and len(new_crystal_content) > 10:
                    # ===== 从 skills/ 目录读取最大ID =====
                    skills_dir = Config.DATA_ROOT / "skills"
                    max_num = 0
                    if skills_dir.exists():
                        for d in skills_dir.iterdir():
                            if d.is_dir() and d.name.startswith("C"):
                                try:
                                    num = int(d.name.replace("C", ""))
                                    if num > max_num:
                                        max_num = num
                                except:
                                    pass
                    next_num = max_num + 1
                    new_id = f"C{next_num:03d}"

                    # ===== 创建 Skill 目录（写入 skills/） =====
                                       # ===== 使用引擎统一入口创建晶体 =====
                    success = self.engine.create_crystal(
                        crystal_id=new_id,
                        content=new_crystal_content[:80],
                        links=[hole_id],
                        source="force_exploration"
                    )
                    if success:
                        exploration_result["crystal_generated"] = new_id
                        self.engine.log_evolution_event(
                            "force_exploration",
                            {
                                "hole_id": hole_id,
                                "crystal_id": new_id,
                                "content": new_crystal_content[:80],
                                "force_level": force_level,
                                "trigger": "force_explorer"
                            }
                        )
                        self.log(f"  ✅ 强制探索生成晶体 {new_id}: {new_crystal_content[:50]}...", "success")
                    else:
                        self.log("  ⚠️ Skill 创建失败", "warning")
                        exploration_result["error"] = "Skill 创建失败"
                else:
                    self.log("  ⚠️ 晶体内容生成失败: 内容为空或太短", "warning")
                    exploration_result["error"] = "晶体内容为空或太短"
            except Exception as e:
                self.log(f"  ⚠️ 晶体生成失败: {e}", "warning")
                exploration_result["error"] = str(e)
        except Exception as e:
            self.log(f"  ⚠️ AI调用失败: {e}", "warning")
            exploration_result["error"] = str(e)

        # 5. 记录探索日志
        self.exploration_log.append({
            "hole_id": hole_id,
            "timestamp": datetime.now().isoformat(),
            "force_level": force_level,
            "crystal_generated": exploration_result.get("crystal_generated"),
            "status": exploration_result.get("status")
        })
        self._save_exploration_state()

        return exploration_result    

    
    def run_scheduled_exploration(self) -> Dict:
        """
        运行定时探索任务
        检查所有孔洞，对超时的进行强制探索
        """
        self.log("🔍 开始定时探索调度...", "system")
        
        # 1. 检查需要升级的孔洞
        escalated = self.check_holes_for_escalation(threshold_days=7)
        
        if not escalated:
            self.log("  ℹ️ 没有需要强制探索的孔洞", "system")
            return {"success": True, "escalated": [], "results": []}
        
        self.log(f"  📋 发现 {len(escalated)} 个需要强制探索的孔洞", "system")
        
        results = []
        for hole_info in escalated[:3]:  # 每次最多处理3个
            self.log(f"  🚀 强制探索孔洞: {hole_info['hole_id']} (紧迫度: {hole_info['urgency']})", "system")
            
            result = self.force_explore(
                hole_info["hole_id"],
                force_level="high" if hole_info["urgency"] > 0.85 else "medium"
            )
            results.append(result)
        
        return {
            "success": True,
            "escalated": escalated,
            "processed": len(results),
            "results": results
        }
    
    def get_exploration_status(self) -> Dict:
        """获取探索状态"""
        holes = self.engine.parse_holes()
        _ = self.engine.load_hole_progress()
        
        high_priority_holes = [h for h in holes if h.urgency >= 0.7]
        
        status = {
            "total_holes": len(holes),
            "high_priority_holes": len(high_priority_holes),
            "exploration_log_count": len(self.exploration_log),
            "last_exploration": self.exploration_log[-1]["timestamp"] if self.exploration_log else None,
            "pending_escalation": len(self.check_holes_for_escalation(7))
        }
        
        # 按孔洞统计探索次数
        exploration_counts = {}
        for record in self.exploration_log:
            hid = record.get("hole_id")
            if hid not in exploration_counts:
                exploration_counts[hid] = 0
            exploration_counts[hid] += 1
        
        status["exploration_counts"] = exploration_counts
        
        return status
