import json
from datetime import datetime
from pathlib import Path


def write_config(pylon_dir: Path, pipeline_id: str, phase: str):
    config = {
        "pipeline_id": pipeline_id,
        "phase": phase,
        "created_at": datetime.utcnow().isoformat(),
    }
    (pylon_dir / "config.json").write_text(json.dumps(config, indent=2))


def write_answers_file(pylon_dir: Path, round_number: int, answers: dict):
    decisions_dir = pylon_dir / "decisions"
    decisions_dir.mkdir(exist_ok=True)
    path = decisions_dir / f"round-{round_number}-answers.json"
    path.write_text(json.dumps(answers, indent=2))


def read_result(pylon_dir: Path) -> dict | None:
    path = pylon_dir / "result.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def read_round_file(pylon_dir: Path, round_number: int) -> dict | None:
    path = pylon_dir / "decisions" / f"round-{round_number}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def read_status(pylon_dir: Path) -> dict | None:
    path = pylon_dir / "status.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def list_round_files(pylon_dir: Path) -> list[int]:
    decisions_dir = pylon_dir / "decisions"
    if not decisions_dir.exists():
        return []
    rounds = []
    for f in decisions_dir.glob("round-*.json"):
        if "answers" not in f.name:
            num = f.stem.replace("round-", "")
            if num.isdigit():
                rounds.append(int(num))
    return sorted(rounds)


def has_answers(pylon_dir: Path, round_number: int) -> bool:
    path = pylon_dir / "decisions" / f"round-{round_number}-answers.json"
    return path.exists()
