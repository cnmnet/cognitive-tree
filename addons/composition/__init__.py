"""作文因材施教：第一个市场模块骨架。"""

from addons.base import register

from .config import SCENE
from .hooks import HOOKS

register(SCENE, HOOKS)
