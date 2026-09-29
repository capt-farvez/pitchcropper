"""Thin execution entry point.

Run with:  python -m engine [--config config.yaml]

Everything here is wiring: set up logging, load and validate the config,
build the reporter, build the input, build the analyzer, run it, report the
outcome. No detection logic lives here.

Environment:
  MOCK_API_URL  overrides reporting.base_url, re-validated like any config value

Exit codes:
  0  run completed
  1  run started but could not finish (video unreadable, stream broken, or an unexpected error)
  2  configuration missing, unparsable, or invalid (nothing was run)
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from synthetic_generator import generate_synthetic_video

from engine.analyzer import FieldBoundaryAnalyzer
from engine.config import PipelineConfig, load_config, with_overrides
from engine.detectors import build_detector
from engine.errors import ConfigError, PipelineError
from engine.logging_setup import configure_logging, new_run_id
from engine.reporting import HttpReporter, JobEvent, NullReporter, Reporter

log = logging.getLogger("engine.main")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="engine", description="Pitch boundary detection pipeline")
    parser.add_argument("--config", default="config.yaml", help="path to the YAML config (default: config.yaml)")
    return parser.parse_args(argv)


def build_reporter(config: PipelineConfig, run_id: str) -> Reporter:
    if not config.reporting.enabled:
        return NullReporter(job_id=config.reporting.job_id, run_id=run_id)
    return HttpReporter(
        base_url=config.reporting.base_url,
        job_id=config.reporting.job_id,
        run_id=run_id,
        timeout_s=config.reporting.timeout_s,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_id = new_run_id()
    configure_logging("INFO", run_id, "text")  # until the config says otherwise

    try:
        config = load_config(args.config)
        if os.environ.get("MOCK_API_URL"):
            config = with_overrides(config, base_url=os.environ["MOCK_API_URL"])
        detector = build_detector(config.field_detector)
    except ConfigError as exc:
        log.error("config.invalid", extra={"config_path": args.config, "detail": str(exc)})
        return 2

    configure_logging(config.logging.level, run_id, config.logging.format)
    # the run id is on every json record already; text mode omits it, so name it once here
    log.info("config.loaded", extra={"config_path": args.config, "run": run_id})

    reporter = build_reporter(config, run_id)
    ids = {"job_id": config.reporting.job_id, "run_id": run_id}
    reporter.event(JobEvent(**ids, event="started"))

    try:
        # Generate the synthetic feed only when nothing is at the path. The prototype
        # regenerated it on every run, which cost ~15 s and overwrote real inputs.
        if Path(config.video_path).exists():
            log.info("input.found", extra={"video_path": config.video_path})
        else:
            generate_synthetic_video(config.video_path)
            log.info("input.generated", extra={"video_path": config.video_path})

        analyzer = FieldBoundaryAnalyzer(config, detector, reporter)
        summary = analyzer.process_video(config.video_path)

        if config.output_path is not None:
            Path(config.output_path).write_text(summary.model_dump_json(indent=2), encoding="utf-8")
            log.info("output.written", extra={"output_path": config.output_path})
    except PipelineError as exc:
        # a known way for a run to fail: say which, exit 1
        log.error("run.failed", extra={"reason": type(exc).__name__, "detail": str(exc), "exit_code": 1})
        reporter.event(JobEvent(**ids, event="failed", detail=f"{type(exc).__name__}: {exc}"))
        return 1
    except Exception as exc:
        # an unknown way: keep the traceback, still exit 1, never pass silently
        log.exception("run.crashed", extra={"exit_code": 1})
        reporter.event(JobEvent(**ids, event="failed", detail=f"{type(exc).__name__}: {exc}"))
        return 1

    reporter.event(JobEvent(**ids, event="completed", summary=summary))
    log.info("run.finished", extra={"exit_code": 0, "valid": summary.valid, "inspected": summary.inspected})
    return 0


if __name__ == "__main__":
    sys.exit(main())
