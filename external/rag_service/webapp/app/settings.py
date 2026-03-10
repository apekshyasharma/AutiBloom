from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WebSettings:
    project_root: Path
    configs_dir: Path
    artifacts_dir: Path

    @staticmethod
    def load() -> "WebSettings":
        # webapp/app/settings.py -> webapp/app -> webapp -> rag/
        root = Path(__file__).resolve().parent.parent.parent
        return WebSettings(
            project_root=root,
            configs_dir=root / "configs",
            artifacts_dir=root / "artifacts",
        )
