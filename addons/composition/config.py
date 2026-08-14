"""作文模块场景配置。"""

from addons.base import SceneConfig


SCENE = SceneConfig(
    scene_id="composition",
    name="作文因材施教",
    version="0.1.0",
    roles=["阅卷老师", "语文名师", "认知科学家", "家长", "学生"],
    prompt_bundle={
        "diagnosis": "诊断作文失分点，给出可量化提升路径",
        "debate": "多角色辩论如何把当前作文从现有分数提到目标分数",
        "report": "五版报告模板：学生/家长/老师/专家/成长",
        "compress": "压缩版契约：≤400字，必须含结论/理由/下一步/止损",
    },
    report_schema={
        "versions": ["学生版", "家长版", "老师版", "专家版", "成长版"],
        "compressed": {
            "max_chars": 400,
            "must_have": ["结论", "理由", "下一步", "止损"],
        },
    },
    data_vault="addons/composition/data",
    market={
        "price": "9.9元/次",
        "channels": ["ima", "公众号", "教师社群"],
    },
)
