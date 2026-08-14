#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from governance.config import Config

@dataclass
class PromptTemplate:
    """Prompt 模板数据结构"""
    name: str
    system_prompt: str
    user_prompt_template: str
    version: int = 1
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    performance_score: float = 0.0
    is_active: bool = True
    parent_version: Optional[int] = None
    improvement_delta: float = 0.0


class PromptTemplateManager:
    """
    Prompt 模板管理器（热加载）
    管理 核心配置/辩论角色模板.json
    """

    def __init__(self, file_io: Any):
        self.files = file_io
        self._templates: Dict[str, PromptTemplate] = {}
        self._load_templates()

    def _get_templates_path(self) -> Path:
        """获取模板配置文件路径"""
        return Config.DATA_ROOT / "核心配置" / "辩论角色模板.json"

    def _load_templates(self):
        """加载模板配置"""
        path = self._get_templates_path()
        if not path.exists():
            self._create_default_templates()
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for name, config in data.get("templates", {}).items():
                self._templates[name] = PromptTemplate(
                    name=name,
                    system_prompt=config.get("system_prompt", ""),
                    user_prompt_template=config.get("user_prompt_template", ""),
                    version=config.get("version", 1),
                    created_at=config.get("created_at", datetime.now().isoformat()),
                    performance_score=config.get("performance_score", 0.0),
                    is_active=config.get("is_active", True),
                    parent_version=config.get("parent_version"),
                    improvement_delta=config.get("improvement_delta", 0.0)
                )
        except Exception as e:
            print(f"⚠️ 加载模板失败: {e}，使用默认模板")
            self._create_default_templates()

    def _create_default_templates(self):
        """创建默认模板"""
        default_templates = {
            "radical": {
                "system_prompt": "你是认知晶体树辩论引擎中的【激进者】。角色立场：攻击默认前提，假设现有框架是错的，给出颠覆性方案。",
                "user_prompt_template": "用户问题：{question}\n请基于你的角色立场给出独立答案，包含结论、理由、证据和风险建议。"
            },
            "conservative": {
                "system_prompt": "你是认知晶体树辩论引擎中的【保守者】。角色立场：风险优先，假设资源有限，给出最可落地的稳健方案。",
                "user_prompt_template": "用户问题：{question}\n请基于你的角色立场给出独立答案，包含结论、理由、证据和风险建议。"
            },
            "structural": {
                "system_prompt": "你是认知晶体树辩论引擎中的【结构主义者】。角色立场：从已有晶体中寻找同构案例，用类比生成方案。",
                "user_prompt_template": "用户问题：{question}\n请基于你的角色立场给出独立答案，包含结论、理由、证据和风险建议。"
            },
            "judge": {
                "system_prompt": "你是认知晶体树辩论引擎中的【大法官】。角色立场：以晶体卡片、核心操作原则和资源约束为准绳，做出终审裁决。必须明确引用依据（晶体ID、原则条款或约束条件），不得凭直觉判案。",
                "user_prompt_template": "用户问题：{question}\n请基于你的角色立场给出独立答案，包含结论、理由、证据和风险建议。"
            },
            "spokesperson": {
                "system_prompt": "你是认知晶体树辩论引擎中的【首席发言人】。角色立场：将内部辩论结论转化为清晰、简洁、无歧义的对外陈述。遵循降维（通俗化）、定调（不超过3条核心信息）、检验（老板读前100字能决策）三原则。",
                "user_prompt_template": "用户问题：{question}\n请基于你的角色立场给出独立答案，包含结论、理由、证据和风险建议。"
            }
        }

        for name, config in default_templates.items():
            self._templates[name] = PromptTemplate(
                name=name,
                system_prompt=config["system_prompt"],
                user_prompt_template=config["user_prompt_template"]
            )

        self._save_templates()

    def _save_templates(self):
        """保存模板到文件"""
        path = self._get_templates_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "templates": {},
            "last_updated": datetime.now().isoformat(),
            "version": "1.0"
        }

        for name, tmpl in self._templates.items():
            data["templates"][name] = {
                "system_prompt": tmpl.system_prompt,
                "user_prompt_template": tmpl.user_prompt_template,
                "version": tmpl.version,
                "created_at": tmpl.created_at,
                "performance_score": tmpl.performance_score,
                "is_active": tmpl.is_active,
                "parent_version": tmpl.parent_version,
                "improvement_delta": tmpl.improvement_delta
            }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """获取模板"""
        return self._templates.get(name)

    def get_all_templates(self) -> Dict[str, PromptTemplate]:
        """获取所有模板"""
        return self._templates

    def update_template(self, name: str, system_prompt: str = None,
                        user_prompt_template: str = None) -> bool:
        """更新模板（热加载）"""
        if name not in self._templates:
            return False

        tmpl = self._templates[name]

        if system_prompt is not None and system_prompt != tmpl.system_prompt:
            tmpl.system_prompt = system_prompt
            tmpl.version += 1
            tmpl.parent_version = tmpl.version - 1

        if user_prompt_template is not None and user_prompt_template != tmpl.user_prompt_template:
            tmpl.user_prompt_template = user_prompt_template
            tmpl.version += 1
            tmpl.parent_version = tmpl.version - 1

        self._save_templates()
        return True

    def rollback(self, name: str, target_version: int) -> bool:
        """回滚到指定版本"""
        return False

