"""Thin execution entry point.

Run with:  python -m engine [--config config.yaml]

Everything here is wiring: set up logging, load and validate the config,
build the input, build the analyzer, run it, report the outcome. No detection
logic lives here.

Exit codes:
  0  run completed
  1  run started but could not finish (video unreadable, stream broken, or an unexpected error)
  2  configuration missing, unparsable, or invalid (nothing was run)
"""

import argparse
import logging
import sys
from pathlib import Path

from synthetic_generator import generate_synthetic_video

from engine.analyzer import FieldBoundaryAnalyzer
from engine.config import load_config
from engine.detectors import build_detector
from engine.errors import ConfigError, PipelineError
from engine.logging_setup import configure_logging, new_run_id

log = logging.getLogger("engine.main")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="engine", description="Pitch boundary detection pipeline")
    parser.add_argument("--config", default="config.yaml", help="path to the YAML config (default: config.yaml)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_id = new_run_id()
    configure_logging("INFO", run_id, "text")  # until the config says otherwise

    try:
        config = load_config(args.config)
        detector = build_detector(config.field_detector)
    except ConfigError as exc:
        log.error("config.invalid", extra={"config_path": args.config, "detail": str(exc)})
        return 2

    configure_logging(config.logging.level, run_id, config.logging.format)
    # the run id is on every json record already; text mode omits it, so name it once here
    log.info("config.loaded", extra={"config_path": args.config, "run": run_id})

    try:
        # Generate the input feed if it does not exist locally
        generate_synthetic_video(config.video_path)
        log.info("input.ready", extra={"video_path": config.video_path})

        analyzer = FieldBoundaryAnalyzer(config, detector)
        summary = analyzer.process_video(config.video_path)

        if config.output_path is not None:
            Path(config.output_path).write_text(summary.model_dump_json(indent=2), encoding="utf-8")
            log.info("output.written", extra={"output_path": config.output_path})
    except PipelineError as exc:
        # a known way for a run to fail: say which, exit 1
        log.error("run.failed", extra={"reason": type(exc).__name__, "detail": str(exc), "exit_code": 1})
        return 1
    except Exception:
        # an unknown way: keep the traceback, still exit 1, never pass silently
        log.exception("run.crashed", extra={"exit_code": 1})
        return 1

    log.info("run.finished", extra={"exit_code": 0, "valid": summary.valid, "inspected": summary.inspected})
    return 0


if __name__ == "__main__":
    sys.exit(main())
