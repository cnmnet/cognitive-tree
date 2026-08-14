# 认知晶体树 / Cognitive Crystal Tree

可插拔自进化的认知与决策引擎：多角色辩论、晶体知识库、检索、报告、自进化与验证闭环。

Pluggable self-evolving cognitive and decision engine: multi-role debate, crystal knowledge base, retrieval, reporting, self-evolution and verification loop.

> 商业保留（All Rights Reserved）。本仓库仅用于授权协作，公开版本不含 GUI 源码。
> Commercial use reserved. The public version does not include GUI source code.

## 快速开始 / Quick Start

```bash
pip install -e ".[server,test]"
crystal-tree-cli --help
crystal-tree-web
```

Web 默认端口 8000：`http://127.0.0.1:8000`

Docker：

```bash
docker build -t cognitive-crystal-tree .
docker run -p 8000:8000 cognitive-crystal-tree
```

## 公开版 / Public Release

GUI 源码只保留在私有工作区，不进入公开包。发布前执行：

```bash
python tools/export_public.py
cd dist_public
pip install .
```

`dist_public/` 不含 GUI 源码、旧版 parity 参考、`.env` 与密钥。完整回归和 parity 只在私有工作区运行。

The public build keeps GUI source private. Run `python tools/export_public.py`, then install from `dist_public/`.

## 环境变量 / Environment

复制 `.env.example` 为 `.env` 后填写 DeepSeek / 百度千帆 Key。`.env` 与密钥绝不进入打包产物或镜像。

Copy `.env.example` to `.env` and fill in DeepSeek / Baidu Qianfan keys. `.env` and secrets are never packaged.

## 目录 / Layout

- `access` 接入层（公开版不含 GUI）
- `harness` 大脑：辩论、报告、验证
- `evolution` 自进化：Gödel、元层、双环、策略
- `core` 基石：模型、接口、持久化
- `data` / `external` / `governance` 支撑层

## 验证 / Verification

```bash
python tools/regression_check.py
```

## License

见 [LICENSE](LICENSE)。
