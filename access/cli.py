"""Command-line entry for running configured flows."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from access.dependencies import (
    HarnessRunner,
    ProcessorRegistry,
    load_flows,
    register_default_processors,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="认知晶体树 5 可插拔自进化 CLI")
    parser.add_argument("--flow", default="daily", help="flow id")
    parser.add_argument("--config-dir", default=str(Path(__file__).resolve().parent.parent / "governance" / "config"))
    args = parser.parse_args()

    config_dir = Path(args.config_dir)
    registry = ProcessorRegistry()
    register_default_processors(registry)
    flows = load_flows(config_dir)
    if args.flow not in flows:
        print(f"flow not found: {args.flow}; available={sorted(flows)}", file=sys.stderr)
        return 1

    runner = HarnessRunner(registry)
    result = runner.run(flows[args.flow])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
