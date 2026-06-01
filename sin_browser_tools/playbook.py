"""Playbook system: record, retrieve, rank browser-automation trajectories.

Stores successful runs with metrics; auto-ranks by success_rate + avg_steps.
Supports failure videos for visual debugging.
"""

import json
import time
import hashlib
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, asdict

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class Metrics:
    """Run quality metrics; auto-computed on record."""
    success_rate: float = 1.0
    avg_steps: float = 0.0
    avg_latency: float = 0.0
    avg_user_rating: float = 5.0
    total_runs: int = 1
    last_used: float = 0.0


@dataclass
class PlaybookVariant:
    """One trajectory for a (task, url) pair."""
    variant_id: str
    trajectory: list[dict[str, Any]]
    created_at: float
    last_updated: float
    metrics: Metrics
    feedback: Optional[str] = None
    failure_video: Optional[str] = None


class PlaybookStore:
    """File-based storage in `.sin_playbooks/<task>/<url_hash>/variants.json`."""

    def __init__(self, base_dir: str = ".sin_playbooks"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)

    def _task_dir(self, task: str) -> Path:
        safe = task.replace("/", "_").replace(":", "_").lower()
        return self.base_dir / safe

    def _url_hash(self, url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()[:8]

    def _variant_file(self, task: str, url: str) -> Path:
        task_dir = self._task_dir(task)
        url_hash = self._url_hash(url)
        variants_dir = task_dir / url_hash
        variants_dir.mkdir(parents=True, exist_ok=True)
        return variants_dir / "variants.json"

    def load_variants(self, task: str, url: str) -> list[PlaybookVariant]:
        """Load all variants for (task, url), sorted by success_rate."""
        path = self._variant_file(task, url)
        if not path.exists():
            return []
        try:
            with open(path) as f:
                data = json.load(f)
            variants = [
                PlaybookVariant(
                    variant_id=v["variant_id"],
                    trajectory=v["trajectory"],
                    created_at=v["created_at"],
                    last_updated=v["last_updated"],
                    metrics=Metrics(**v["metrics"]),
                    feedback=v.get("feedback"),
                    failure_video=v.get("failure_video"),
                )
                for v in data.get("variants", [])
            ]
            variants.sort(
                key=lambda v: (-v.metrics.success_rate, v.metrics.avg_steps)
            )
            return variants
        except Exception as e:
            logger.warning("failed to load variants", path=str(path), error=str(e))
            return []

    def save_variant(
        self,
        task: str,
        url: str,
        trajectory: list[dict],
        success: bool,
        steps: int,
        latency: float,
        user_rating: float = 5.0,
        failure_video: Optional[str] = None,
        keep_top: int = 5,
    ) -> str:
        """Save/update a playbook variant with metrics; auto-updates ranking."""
        path = self._variant_file(task, url)
        variants = self.load_variants(task, url)

        trajectory_hash = hashlib.sha256(
            json.dumps(trajectory, sort_keys=True).encode()
        ).hexdigest()[:16]

        existing = next((v for v in variants if v.variant_id == trajectory_hash), None)
        now = time.time()

        if existing:
            m = existing.metrics
            n = m.total_runs
            m.success_rate = (m.success_rate * n + (1.0 if success else 0.0)) / (n + 1)
            m.avg_steps = (m.avg_steps * n + steps) / (n + 1)
            m.avg_latency = (m.avg_latency * n + latency) / (n + 1)
            m.avg_user_rating = (m.avg_user_rating * n + user_rating) / (n + 1)
            m.total_runs = n + 1
            m.last_used = now
            existing.last_updated = now
            if failure_video:
                existing.failure_video = failure_video
        else:
            variants.append(
                PlaybookVariant(
                    variant_id=trajectory_hash,
                    trajectory=trajectory,
                    created_at=now,
                    last_updated=now,
                    failure_video=failure_video,
                    metrics=Metrics(
                        success_rate=1.0 if success else 0.0,
                        avg_steps=float(steps),
                        avg_latency=latency,
                        avg_user_rating=user_rating,
                        total_runs=1,
                        last_used=now,
                    ),
                )
            )

        variants.sort(
            key=lambda v: (-v.metrics.success_rate, v.metrics.avg_steps)
        )
        variants = variants[:keep_top]

        with open(path, "w") as f:
            json.dump(
                {
                    "task": task,
                    "url": url,
                    "updated": now,
                    "variants": [
                        {
                            "variant_id": v.variant_id,
                            "trajectory": v.trajectory,
                            "created_at": v.created_at,
                            "last_updated": v.last_updated,
                            "metrics": asdict(v.metrics),
                            "feedback": v.feedback,
                            "failure_video": v.failure_video,
                        }
                        for v in variants
                    ],
                },
                f,
                indent=2,
            )
        return trajectory_hash
