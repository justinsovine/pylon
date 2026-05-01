from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://pylon:pylon@localhost:5432/pylon"
    redis_url: str = "redis://localhost:6379/0"

    asana_token: str = ""
    asana_project_gid: str = ""
    asana_ready_section_gid: str = ""

    slack_webhook_url: str = ""

    pylon_internal_key: str = "change-me"
    pylon_secret_key: str = "change-me"

    repos_base_path: str = ""
    notes_base_path: str = ""
    worktrees_path: str = "worktrees"

    repo_paths: dict[str, str] = {
        "esign": "esign",
        "onboard": "onboard",
        "scriptus-web": "scriptus-web",
    }

    skip_phpstan: bool = False

    phase_timeouts: dict[str, int] = {
        "investigate": 1200,
        "refine": 600,
        "plan": 900,
        "critique": 600,
        "implement": 2700,
        "test": 1200,
        "pr": 600,
    }

    max_workers: int = 3
    max_tickets_per_batch: int = 4
    asana_poll_interval_seconds: int = 900

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
