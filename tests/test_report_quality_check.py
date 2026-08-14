import unittest

from tools.report_quality_check import DEFAULT_ROLES, VERSION_MARKERS, check_report


def build_sample_report() -> str:
    lines = ["# 测试报告", ""]
    for role in DEFAULT_ROLES:
        lines.append(f"### {role}")
        lines.append("")
        lines.append(f"{role} 的压缩观点。")
        lines.append("")
    for marker in VERSION_MARKERS:
        lines.append(f"### {marker} - 示例")
        lines.append("")
        lines.append(f"{marker} 内容。")
        lines.append("")
    return "\n".join(lines)


class TestReportQualityCheck(unittest.TestCase):
    def test_complete_report_passes(self):
        self.assertEqual(check_report(build_sample_report()), [])

    def test_missing_version_section_fails(self):
        report = "\n".join(
            line for line in build_sample_report().splitlines() if "新人版" not in line
        )
        missing = check_report(report)
        self.assertIn("缺少版本章节：新人版", missing)

    def test_missing_role_section_fails(self):
        report = build_sample_report().replace("### 大法官\n", "")
        missing = check_report(report)
        self.assertIn("缺少角色压缩内容：大法官", missing)


if __name__ == "__main__":
    unittest.main()
