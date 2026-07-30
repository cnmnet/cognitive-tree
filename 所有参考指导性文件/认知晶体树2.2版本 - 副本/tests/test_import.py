# 在 Python 交互环境中测试
from crystal_tree_all_in_one_day8 import CrystalEngine, FileIO, Config

# 初始化引擎
engine = CrystalEngine(FileIO())

# 测试方法是否存在
print(hasattr(engine, 'get_skill_path'))          # 应该输出 True
print(hasattr(engine, 'validate_skill'))          # 应该输出 True
print(hasattr(engine, 'get_all_skills'))          # 应该输出 True

# 获取所有 Skill（初始应该为空）
skills = engine.get_all_skills()
print(f"当前 Skill 数量: {len(skills)}")          # 输出 0