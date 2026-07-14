"""Command-line entry point for Content Engine."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from content_engine.app.runtime import (
    run_app,
    run_autopost,
    run_demo,
    run_health_check,
    run_linkedin_login,
    run_mark_ready,
    run_publish,
    run_report,
)


REPORT_COMMANDS = ("list-assets", "show-latest-asset", "show-experiment", "show-pipeline", "show-statistics")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Content Engine runtime")
    parser.add_argument(
        "command",
        nargs="?",
        choices=("run", "health", "demo", "autopost", "linkedin-login", "mark-ready", "publish", *REPORT_COMMANDS),
        default="run",
        help="Command to execute. Defaults to run.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional path to a TOML configuration file.",
    )
    parser.add_argument(
        "--id",
        default=None,
        help="Optional content item or experiment ID for reporting commands.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum rows for list reports.",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=None,
        help="Seconds to sleep between successful autopost iterations.",
    )
    parser.add_argument(
        "--max-posts",
        type=int,
        default=None,
        help="Optional cap for autopost iterations. Omit for unbounded autoposting.",
    )
    parser.add_argument(
        "--max-consecutive-failures",
        type=int,
        default=None,
        help="Stop autopost after this many consecutive non-limit failures.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "health":
        return run_health_check(config_path=args.config)
    if args.command == "demo":
        return run_demo(config_path=args.config)
    if args.command == "publish":
        return run_publish(config_path=args.config)
    if args.command == "autopost":
        return run_autopost(
            config_path=args.config,
            delay_seconds=args.delay_seconds,
            max_posts=args.max_posts,
            max_consecutive_failures=args.max_consecutive_failures,
        )
    if args.command == "mark-ready":
        return run_mark_ready(config_path=args.config, identifier=args.id)
    if args.command == "linkedin-login":
        return run_linkedin_login(config_path=args.config)
    if args.command in REPORT_COMMANDS:
        return run_report(args.command, config_path=args.config, identifier=args.id, limit=args.limit)
    return run_app(config_path=args.config)


if __name__ == "__main__":
    sys.exit(main())
