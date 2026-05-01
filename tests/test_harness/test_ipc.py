import json
from pathlib import Path

import pytest

from src.pylon.harness.ipc import (
    has_answers,
    list_round_files,
    read_result,
    read_round_file,
    write_answers_file,
    write_config,
)


def test_write_and_read_config(tmp_path: Path):
    write_config(tmp_path, "pipeline-123", "investigate")
    config = json.loads((tmp_path / "config.json").read_text())
    assert config["pipeline_id"] == "pipeline-123"
    assert config["phase"] == "investigate"


def test_write_and_read_answers(tmp_path: Path):
    answers = {
        "round": 1,
        "answers": [{"id": "d001", "choice": "A", "note": ""}],
    }
    write_answers_file(tmp_path, 1, answers)
    assert has_answers(tmp_path, 1)
    assert not has_answers(tmp_path, 2)


def test_read_result_missing(tmp_path: Path):
    assert read_result(tmp_path) is None


def test_read_result_exists(tmp_path: Path):
    result = {"phase": "investigate", "status": "complete"}
    (tmp_path / "result.json").write_text(json.dumps(result))
    assert read_result(tmp_path) == result


def test_list_round_files(tmp_path: Path):
    decisions_dir = tmp_path / "decisions"
    decisions_dir.mkdir()
    (decisions_dir / "round-1.json").write_text("{}")
    (decisions_dir / "round-1-answers.json").write_text("{}")
    (decisions_dir / "round-2.json").write_text("{}")

    rounds = list_round_files(tmp_path)
    assert rounds == [1, 2]


def test_read_round_file(tmp_path: Path):
    decisions_dir = tmp_path / "decisions"
    decisions_dir.mkdir()
    data = {"round": 1, "decisions": []}
    (decisions_dir / "round-1.json").write_text(json.dumps(data))

    assert read_round_file(tmp_path, 1) == data
    assert read_round_file(tmp_path, 2) is None
