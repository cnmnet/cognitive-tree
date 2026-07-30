import subprocess
import sys
from pathlib import Path

# 使用测试中的路径
skill_dir = Path(r"C:\Users\Administrator\AppData\Local\Temp\test_day9_hkj8heyz\skills\C001")
validate_py = skill_dir / "validate.py"

print(f"validate.py 路径: {validate_py}")
print(f"文件存在: {validate_py.exists()}")

if validate_py.exists():
    print("\n文件内容:")
    print(validate_py.read_text(encoding='utf-8'))
    
    print("\n执行验证:")
    try:
        result = subprocess.run(
            [sys.executable, str(validate_py)],
            capture_output=True,
            text=True,
            cwd=str(skill_dir)
        )
        print(f"返回码: {result.returncode}")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
    except Exception as e:
        print(f"执行失败: {e}")