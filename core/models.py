#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional

class Layer(Enum):
    L1 = auto()
    L2 = auto()
    L3 = auto()

@dataclass
class Crystal:
    id: str
    content: str
    links: List[str] = field(default_factory=list)
    layer: Layer = Layer.L2
    heat: float = 0.0
    last_accessed: Optional[date] = None
    # ===== 新增：晶体代码化字段 =====
    input_conditions: List[str] = field(default_factory=list)
    execution_logic: str = ""
    output_format: str = ""
    validation_criteria: List[str] = field(default_factory=list)
    @property
    def summary(self) -> str:
        return self.content[:50] + "..." if len(self.content) > 50 else self.content

@dataclass
class Hole:
    id: str
    content: str
    urgency: float = 0.5
    layer: int = 2
    @property
    def summary(self) -> str:
        return self.content[:50] + "..." if len(self.content) > 50 else self.content

@dataclass
class Conflict:
    crystal_a: str
    crystal_b: str
    similarity: float
    content_a: str
    content_b: str

@dataclass
class TaskCard:
    id: str
    type: str
    title: str
    content: str
    source: str
    links: List[str] = field(default_factory=list)
    suggested_action: str = ""
    status: str = "pending"

@dataclass
class HealthCheckResult:
    level: str
    file: str
    message: str
    suggested_fix: str = ""

@dataclass
class CognitiveFingerprint:
    """
    用户认知指纹 —— 让系统"认识你"
    """
    # ===== 决策偏好维度 =====
    risk_tolerance: float = 0.5
    innovation_preference: float = 0.5
    decisiveness: float = 0.5

    # ===== 角色倾向维度 =====
    preferred_role: str = "structural"
    role_adoption_history: Dict[str, int] = field(default_factory=dict)

    # ===== 冲突解决风格 =====
    conflict_resolution_style: str = "integrative"

    # ===== 注意力模式 =====
    attention_span: float = 0.5
    context_preference: int = 3

    # ===== Day 2.5: 认知风格 =====
    reasoning_style: str = "balanced"
    analogy_preference: str = "balanced"
    output_style: str = "balanced"

    # ===== Day 13.8: 语言风格偏好 =====
    language_style: Dict[str, str] = field(default_factory=lambda: {
        "wenbai_ratio": "balanced",      # "wen" | "bai" | "balanced"
        "metaphor_preference": "nature", # "nature" | "architecture" | "military" | "balanced"
        "rhythm_preference": "balanced", # "short" | "long" | "balanced"
        "cultural_roots": ["儒家", "道家"]  # 默认文化根基
    })

    # ===== 元数据 =====
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    total_interactions: int = 0
    confidence: float = 0.3
    evolution_log: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_tolerance": self.risk_tolerance,
            "innovation_preference": self.innovation_preference,
            "decisiveness": self.decisiveness,
            "preferred_role": self.preferred_role,
            "role_adoption_history": self.role_adoption_history,
            "conflict_resolution_style": self.conflict_resolution_style,
            "attention_span": self.attention_span,
            "context_preference": self.context_preference,
            "reasoning_style": self.reasoning_style,
            "analogy_preference": self.analogy_preference,
            "output_style": self.output_style,
            "language_style": self.language_style,
            "last_updated": self.last_updated,
            "total_interactions": self.total_interactions,
            "confidence": self.confidence,
            "evolution_log": self.evolution_log
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CognitiveFingerprint":
        return cls(
            risk_tolerance=data.get("risk_tolerance", 0.5),
            innovation_preference=data.get("innovation_preference", 0.5),
            decisiveness=data.get("decisiveness", 0.5),
            preferred_role=data.get("preferred_role", "structural"),
            role_adoption_history=data.get("role_adoption_history", {}),
            conflict_resolution_style=data.get("conflict_resolution_style", "integrative"),
            attention_span=data.get("attention_span", 0.5),
            context_preference=data.get("context_preference", 3),
            reasoning_style=data.get("reasoning_style", "balanced"),
            analogy_preference=data.get("analogy_preference", "balanced"),
            output_style=data.get("output_style", "balanced"),
            language_style=data.get("language_style", {
                "wenbai_ratio": "balanced",
                "metaphor_preference": "nature",
                "rhythm_preference": "balanced",
                "cultural_roots": ["儒家", "道家"]
            }),
            last_updated=data.get("last_updated", datetime.now().isoformat()),
            total_interactions=data.get("total_interactions", 0),
            confidence=data.get("confidence", 0.3),
            evolution_log=data.get("evolution_log", [])
        )

@dataclass
class FingerprintExtractionResult:
    """指纹提取结果"""
    fingerprint: CognitiveFingerprint
    source_analysis: Dict[str, Any]
    changes: List[Dict[str, Any]]
    confidence_delta: float

@dataclass
class Report:
    title: str
    sections: Dict[str, Any] = field(default_factory=dict)
    source_question: str = ""
    created_at: str = ""
