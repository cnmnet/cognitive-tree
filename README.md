# 认知晶体树 / Cognitive Crystal Tree

一个可插拔、自进化的多角色辩论与认知沉淀引擎。

A pluggable, self-evolving multi-role debate and cognitive crystallization engine.

## 它解决什么问题

AI 让内容生产和决策变得更快，但团队往往只沉淀了提示词，没有沉淀“为什么这么做”的判断依据。

认知晶体树把“可交给 AI 的流程知识”和“必须由人内化的决策认知”分开，把每次项目实践沉淀为可检索、可迭代、可验证的认知晶体，而不是散落的提示词素材。

## 和普通提示词库 / RAG 的区别

| 方案 | 沉淀什么 | 能否验证 | 能否迭代 |
| --- | --- | --- | --- |
| 提示词库 | 怎么问 AI | 弱 | 弱 |
| RAG | 已有文本 | 部分 | 中 |
| 认知晶体树 | 决策依据、反例、失效边界 | 强 | 强 |

## 快速开始 / Quick Start

```bash
pip install -e ".[server,test]"
crystal-tree-cli --flow daily
crystal-tree-web
```

Web 默认端口 8000：`http://127.0.0.1:8000`

Docker：

```bash
docker build -t cognitive-crystal-tree .
docker run -p 8000:8000 cognitive-crystal-tree
```

## 架构 / Architecture

```text
access       接入层：CLI / Web / GUI（公开版不含 GUI）
harness      大脑：多角色辩论、审计、报告、验证
evolution    自进化：Gödel、元层、双环、策略
core         基石：模型、接口、持久化
data         数据：存储、向量、服务
external     外部：AI、搜索、抓取、证据
governance   治理：配置、Prompt、审计规则
```

## 三种入口 / Entry Points

- CLI：`crystal-tree-cli`
- Web：`crystal-tree-web`
- GUI：仅保留私有工作区，不进入公开版

## 环境变量 / Environment

复制 `.env.example` 为 `.env`，填写 DeepSeek / 百度千帆 Key。

`.env` 和密钥绝不进入打包产物或镜像。

## 验证 / Verification

```bash
python tools/regression_check.py
```

## License

商业保留（All Rights Reserved），见 [LICENSE](LICENSE)。
