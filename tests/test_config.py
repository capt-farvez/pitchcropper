"""Config loading must either return a valid model or fail with a clear message."""

import pytest
import yaml

from engine.config import PipelineConfig, load_config
from engine.errors import ConfigError
from tests.conftest import VALID_CONFIG as VALID


def write(tmp_path, data, name="config.yaml"):
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data) if not isinstance(data, str) else data, encoding="utf-8")
    return path


def test_valid_config_loads(tmp_path):
    cfg = load_config(write(tmp_path, VALID))
    assert isinstance(cfg, PipelineConfig)
    assert cfg.field_detector.min_area == 1000
    assert cfg.crop_search.aspect_ratio == "16:9"


def test_missing_file_is_config_error(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")


def test_unparsable_yaml_is_config_error(tmp_path):
    with pytest.raises(ConfigError, match="not valid YAML"):
        load_config(write(tmp_path, "video_path: [unclosed"))


def test_non_mapping_top_level_is_config_error(tmp_path):
    with pytest.raises(ConfigError, match="mapping at the top level"):
        load_config(write(tmp_path, "- just\n- a list\n"))


def test_unknown_key_is_rejected(tmp_path):
    data = {**VALID, "unexpected": 1}
    with pytest.raises(ConfigError, match="unexpected"):
        load_config(write(tmp_path, data))


def test_missing_required_key_is_rejected(tmp_path):
    data = {k: v for k, v in VALID.items() if k != "field_detector"}
    with pytest.raises(ConfigError, match="field_detector"):
        load_config(write(tmp_path, data))


def test_out_of_range_value_is_rejected(tmp_path):
    data = {**VALID, "field_detector": {**VALID["field_detector"], "min_area": 0}}
    with pytest.raises(ConfigError, match="min_area"):
        load_config(write(tmp_path, data))


def test_wrong_type_is_rejected(tmp_path):
    data = {**VALID, "confidence_threshold": "high"}
    with pytest.raises(ConfigError, match="confidence_threshold"):
        load_config(write(tmp_path, data))


def test_nested_out_of_range_value_names_its_path(tmp_path):
    data = {**VALID, "sampling": {**VALID["sampling"], "analysis_fps": 0}}
    with pytest.raises(ConfigError, match="sampling.analysis_fps"):
        load_config(write(tmp_path, data))


def test_unknown_detector_type_is_rejected(tmp_path):
    data = {**VALID, "field_detector": {**VALID["field_detector"], "type": "sam_mask_v1"}}
    with pytest.raises(ConfigError, match="field_detector.type"):
        load_config(write(tmp_path, data))


def test_error_message_lists_every_problem(tmp_path):
    data = {**VALID, "confidence_threshold": 5, "debug_mode": "maybe"}
    with pytest.raises(ConfigError) as info:
        load_config(write(tmp_path, data))
    message = str(info.value)
    assert "confidence_threshold" in message
    assert "debug_mode" in message
