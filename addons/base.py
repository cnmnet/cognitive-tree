"""Lightweight addon SDK: register(scene_config, hooks)."""

from __future__ import annotations

from dataclasses import dataclass, field
import importlib
from typing import Any, Callable, Dict, List, Optional


@dataclass
class SceneConfig:
    """市场模块的场景配置：换角色、换 Prompt、换输出、换数据。"""

    scene_id: str
    name: str
    version: str = "0.1.0"
    roles: List[str] = field(default_factory=list)
    prompt_bundle: Dict[str, str] = field(default_factory=dict)
    report_schema: Dict[str, Any] = field(default_factory=dict)
    data_vault: str = "addons"
    market: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Hooks:
    """场景钩子：只做插桩，不碰引擎内部。"""

    on_report_prepare: Optional[Callable] = None
    on_report_compressed: Optional[Callable] = None
    on_user_feedback: Optional[Callable] = None
    on_evolve: Optional[Callable] = None
    on_export: Optional[Callable] = None


@dataclass
class Addon:
    scene: SceneConfig
    hooks: Hooks

    def hook(self, name: str, *args: Any, **kwargs: Any):
        fn = getattr(self.hooks, name, None)
        if fn is not None:
            return fn(*args, **kwargs)
        return None


_REGISTRY: Dict[str, Addon] = {}


def register(scene: SceneConfig, hooks: Hooks) -> Addon:
    addon = Addon(scene=scene, hooks=hooks)
    _REGISTRY[scene.scene_id] = addon
    return addon


def get(scene_id: str) -> Optional[Addon]:
    return _REGISTRY.get(scene_id)


def list_scenes() -> List[Dict[str, Any]]:
    return [
        {
            "scene_id": addon.scene.scene_id,
            "name": addon.scene.name,
            "version": addon.scene.version,
        }
        for addon in _REGISTRY.values()
    ]


def load_addons() -> List[Dict[str, Any]]:
    """显式加载已内置的市场模块（平台不会反向 import addons）。"""
    try:
        importlib.import_module("addons.composition")
    except Exception:
        pass
    return list_scenes()
