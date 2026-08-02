#!/usr/bin/env python3
"""生成、列出和作废 Boss Automation 邀请码。"""

import argparse
from datetime import datetime
import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.state_store import StateStore


def _positive_count(raw: str) -> int:
    """解析 1-50 的生成数量；参数为命令行文本，返回合法整数。"""
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("数量必须是整数") from exc
    if not 1 <= value <= 50:
        raise argparse.ArgumentTypeError("数量必须在 1-50 之间")
    return value


def _format_time(timestamp) -> str:
    """把可空 Unix 时间戳转成本地可读文本；空值返回短横线。"""
    if timestamp is None:
        return "-"
    return datetime.fromtimestamp(float(timestamp)).strftime("%Y-%m-%d %H:%M:%S")


def build_parser() -> argparse.ArgumentParser:
    """创建 CLI 参数解析器并返回，不读取或修改数据库。"""
    parser = argparse.ArgumentParser(description="管理 Boss Automation 邀请码")
    parser.add_argument(
        "--db",
        default=os.environ.get("BOSS_STATE_DB", str(PROJECT_ROOT / "data/state.db")),
        help="state.db 路径（默认 data/state.db）",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="生成未使用邀请码")
    generate.add_argument("--count", type=_positive_count, default=1)

    list_parser = subparsers.add_parser("list", help="列出邀请码")
    list_parser.add_argument(
        "--status", choices=("unused", "used", "revoked"), default=None
    )

    revoke = subparsers.add_parser("revoke", help="作废未使用邀请码")
    revoke.add_argument("code", help="要作废的 8 字符邀请码")
    return parser


def _normalize_argv(argv=None) -> list[str]:
    """保护以连字符开头的邀请码；参数为原始 argv，返回 argparse 可解析副本。"""
    values = list(sys.argv[1:] if argv is None else argv)
    try:
        revoke_index = values.index("revoke")
    except ValueError:
        return values
    code_index = revoke_index + 1
    if (
        code_index < len(values)
        and values[code_index].startswith("-")
        and values[code_index] not in {"-h", "--help"}
    ):
        values.insert(code_index, "--")
    return values


def main(argv=None) -> int:
    """执行邀请码命令；参数为可选 argv，返回进程退出码。"""
    args = build_parser().parse_args(_normalize_argv(argv))
    store = StateStore(db_path=args.db)
    store.init_schema()

    if args.command == "generate":
        for _ in range(args.count):
            print(store.create_invite())
        return 0

    if args.command == "list":
        print("CODE\tSTATUS\tUSER_ID\tCREATED_AT\tUSED_AT")
        for row in store.list_invites(status=args.status):
            print(
                f"{row['code']}\t{row['status']}\t{row['user_id'] or '-'}\t"
                f"{_format_time(row['created_at'])}\t{_format_time(row['used_at'])}"
            )
        return 0

    if store.revoke_invite(args.code):
        print(f"已作废: {args.code}")
        return 0
    print("作废失败：邀请码不存在、已使用或已作废", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
