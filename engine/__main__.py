"""Thin execution entry point.

Run with:  python -m engine [--config config.yaml]

Everything here is wiring: load and validate the config, build the input,
build the analyzer, run it, print the outcome. No detection logic lives here.

Exit codes:
  0  run completed
  2  configuration missing, unparsable, or invalid (nothing was run)
"""

import argparse
import sys

from synthetic_generator import generate_synthetic_video

from engine.analyzer import FieldBoundaryAnalyzer
from engine.config import load_config
from engine.errors import ConfigError


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="engine", description="Pitch boundary detection pipeline")
    parser.add_argument("--config", default="config.yaml", help="path to the YAML config (default: config.yaml)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 2

    # Generate the input feed if it does not exist locally
    generate_synthetic_video(config.video_path)

    analyzer = FieldBoundaryAnalyzer(config)
    results = analyzer.process_video(config.video_path)
    print(f"Pipeline finished with {len(results) if results else 0} results.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
