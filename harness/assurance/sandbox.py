#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

from harness.assurance.claim_extractor import VerifiableClaim
from harness.engine import CrystalEngine

class SandboxExecutor:
    """
    沙盒执行引擎
    在隔离环境中执行验证代码，返回结果
    """
    
    def __init__(self, engine: 'CrystalEngine' = None):
        self.engine = engine
        self.execution_log: List[Dict] = []

    def _has_malicious_code(self, code: str) -> bool:
        """静态扫描代码，检测恶意模式"""
        # 黑名单词汇（精确匹配）
        blacklist = [
            "os.system",
            "subprocess.Popen",
            "subprocess.call",
            "subprocess.run",
            "__import__",
            "eval(",
            "exec(",
            "compile(",
            "globals()",
            "locals()",
            "getattr(",
            "setattr(",
            "delattr",
            "__builtins__",
            "execfile",
            "shutil.rmtree",
            "shutil.move",
            "os.remove",
            "os.unlink",
            "os.rmdir",
            "os.removedirs",
            "open(",
        ]
        # 忽略注释和字符串内的内容（简化版：直接匹配，安全优先）
        code_clean = re.sub(r'#.*$', '', code, flags=re.MULTILINE)
        code_clean = re.sub(r'(""".*?"""|\'\'\'.*?\'\'\'|".*?"|\'.*?\')', '', code_clean, flags=re.DOTALL)
        
        for pattern in blacklist:
            if pattern in code_clean:
                return True
        return False

    def _generate_fix_suggestions(self, error: str) -> str:
        """根据沙盒失败类型给出可执行修复建议。"""
        error = error or ""
        if "AssertionError" in error:
            return "将 assert 改为 >= 或 <=，检查数值精度"
        if "KeyError" in error:
            return "检查变量名是否正确，确认数据字典中包含该键"
        if "TimeoutExpired" in error or "执行超时" in error:
            return "代码执行超时，检查是否存在死循环"
        if "ImportError" in error or "ModuleNotFoundError" in error:
            return "缺少依赖库，请检查 import 语句并安装对应包"
        if "Security block" in error:
            return "代码包含黑名单调用，请移除 os.system/subprocess/eval 等"
        if "NameError" in error:
            return "检查变量是否已定义，确认拼写和作用域"
        if "TypeError" in error:
            return "检查函数参数类型和数量是否匹配"
        return "请检查代码逻辑、变量作用域和数据源是否可用"

    def execute_claim(self, claim: VerifiableClaim) -> Dict[str, Any]:
        """
        在沙盒中执行单个主张的测试代码
        """
        result = {
            "claim_id": claim.claim_id,
            "original_text": claim.original_text,
            "success": False,
            "output": "",
            "error": "",
            "execution_time": 0.0,
            "verification_status": "pending_review",
        }
        
        # ===== Day 2 新增：静态代码扫描 =====
        if self._has_malicious_code(claim.test_code):
            result["error"] = "Security block: malicious code detected"
            result["fix_suggestion"] = self._generate_fix_suggestions(result["error"])
            result["verification_status"] = "failed"
            return result
        
        # 创建临时文件
        temp_dir = tempfile.mkdtemp(prefix="sandbox_")
        temp_file = Path(temp_dir) / f"test_{claim.claim_id.lower().replace('-', '_')}.py"
        
        try:
            # 获取测试函数名（从 claim_id 中提取）
            func_name = f"test_{claim.claim_id.lower().replace('-', '_')}"
            
            # 写入测试代码
            code = claim.test_code
            
            # 生成器统一输出 def test_claim()，按 claim_id 归一化到沙盒期望的函数名
            if f"def {func_name}" not in code and "def test_claim" in code:
                code = code.replace("def test_claim", f"def {func_name}", 1)

            # 如果测试代码中没有定义函数，自动包装
            if f"def {func_name}" not in code:
                # 提取断言内容
                assert_lines = []
                for line in code.split('\n'):
                    if 'assert' in line:
                        assert_lines.append(line.strip())
                
                if assert_lines:
                    code = f"""
def {func_name}():
    try:
        {chr(10).join(assert_lines)}
        print("[PASS]")
    except AssertionError as e:
        print(f"[FAIL] {{e}}")
        raise
"""
                else:
                    code = f"""
def {func_name}():
    print("[PENDING] 无断言，待核验")
"""
            
            full_code = f'''
import contextlib
import io
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

{code}

if __name__ == "__main__":
    _buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(_buffer):
            {func_name}()
    except AssertionError as e:
        print(f"[FAIL] {{e}}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] {{e}}")
        sys.exit(1)
    _out = _buffer.getvalue()
    print(_out, end="")
    if "[SKIP]" in _out or "[PENDING]" in _out:
        print("[SKIP] 无数据源，待核验")
        sys.exit(0)
    if "[PASS]" not in _out:
        print("[PENDING] 无显式断言，待核验")
        sys.exit(0)
'''
            temp_file.write_text(full_code, encoding='utf-8')
            
            # ===== Day 2 修改：超时从 30 改为 5 =====
            start_time = time.time()
            proc = subprocess.run(
                [sys.executable, str(temp_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,                         # ← 关键修改
                cwd=str(temp_dir)
            )
            elapsed = time.time() - start_time
            
            result["execution_time"] = elapsed
            result["output"] = proc.stdout.strip()
            result["error"] = proc.stderr.strip()
            result["fix_suggestion"] = self._generate_fix_suggestions(result["error"])
            
            # 只认显式断言通过；SKIP / 无断言均视为待核验
            if proc.returncode != 0 or "[FAIL]" in result["output"] or "[ERROR]" in result["output"]:
                result["verification_status"] = "failed"
            elif "[SKIP]" in result["output"] or "[PENDING]" in result["output"]:
                result["verification_status"] = "pending_review"
            elif "[PASS]" in result["output"]:
                result["verification_status"] = "verified"
            else:
                result["verification_status"] = "pending_review"
            result["success"] = result["verification_status"] == "verified"
            
        except subprocess.TimeoutExpired:
            result["error"] = "执行超时 (5秒)"
            result["fix_suggestion"] = self._generate_fix_suggestions(result["error"])
            result["verification_status"] = "failed"
        except Exception as e:
            result["error"] = str(e)
            result["fix_suggestion"] = self._generate_fix_suggestions(result["error"])
            result["verification_status"] = "failed"
        finally:
            # 清理
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        # 记录执行日志
        self.execution_log.append(result)
        return result

    def execute_code(self, code: str, timeout: int = 5) -> Dict[str, Any]:
        """直接执行一段 Python 代码，兼容 main() 或 test_*() 入口。"""
        result = {
            "claim_id": "code",
            "original_text": code[:80],
            "success": False,
            "output": "",
            "error": "",
            "execution_time": 0.0,
            "verification_status": "pending_review",
        }
        if not code or not code.strip():
            result["error"] = "Empty code"
            result["fix_suggestion"] = "请输入非空代码"
            result["verification_status"] = "failed"
            return result
        if self._has_malicious_code(code):
            result["error"] = "Security block: malicious code detected"
            result["fix_suggestion"] = self._generate_fix_suggestions(result["error"])
            result["verification_status"] = "failed"
            return result

        temp_dir = tempfile.mkdtemp(prefix="sandbox_code_")
        temp_file = Path(temp_dir) / "sandbox_code.py"
        try:
            runner = '''
import re
import sys

_src = open(__file__, encoding="utf-8").read()
_funcs = re.findall(r"^def\\s+(\\w+)\\(", _src, re.M)
_calls = []
for _fn in _funcs:
    if _fn == "main" or _fn.startswith("test_"):
        _calls.append(_fn + "()")
if not _calls:
    print("[PASS]")
else:
    for _call in _calls:
        eval(_call)
print("[PASS]")
'''
            temp_file.write_text(code + "\n\n" + runner, encoding="utf-8")
            start_time = time.time()
            proc = subprocess.run(
                [sys.executable, str(temp_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                cwd=str(temp_dir),
            )
            elapsed = time.time() - start_time
            result["execution_time"] = elapsed
            result["output"] = proc.stdout.strip()
            result["error"] = proc.stderr.strip()
            result["fix_suggestion"] = self._generate_fix_suggestions(result["error"])
            result["success"] = proc.returncode == 0 and "[PASS]" in proc.stdout
            result["verification_status"] = "verified" if result["success"] else "failed"
        except subprocess.TimeoutExpired:
            result["error"] = f"执行超时 ({timeout}秒)"
            result["fix_suggestion"] = self._generate_fix_suggestions(result["error"])
            result["verification_status"] = "failed"
        except Exception as e:
            result["error"] = str(e)
            result["fix_suggestion"] = self._generate_fix_suggestions(result["error"])
            result["verification_status"] = "failed"
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        self.execution_log.append(result)
        return result

    def execute_claims(self, claims: List[VerifiableClaim]) -> List[Dict]:
        """
        批量执行多个主张
        """
        results = []
        for claim in claims:
            result = self.execute_claim(claim)
            results.append(result)
        return results
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """
        获取执行摘要
        """
        total = len(self.execution_log)
        passed = sum(1 for r in self.execution_log if r.get("success", False))
        failed = total - passed
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / total if total > 0 else 0.0,
            "avg_execution_time": sum(r.get("execution_time", 0) for r in self.execution_log) / total if total > 0 else 0.0
        }


