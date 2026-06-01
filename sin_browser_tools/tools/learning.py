"""Tools for sin-browser-learning skill: suggest/record/list/compare playbooks."""

from typing import Optional
from sin_browser_tools.playbook import PlaybookStore

_store = PlaybookStore()


async def browser_playbook_suggest(task: str, url: str, limit: int = 3) -> dict:
    """Retrieve top playbook variants for (task, url), ranked by success_rate."""
    variants = _store.load_variants(task, url)
    if not variants:
        return {
            "status": "not_found",
            "task": task,
            "url": url,
            "hint": "No prior playbook. Use sin-browser-automation skill and record after.",
        }
    return {
        "status": "ok",
        "task": task,
        "url": url,
        "variants": [
            {
                "id": v.variant_id,
                "steps": len(v.trajectory),
                "success_rate": round(v.metrics.success_rate, 2),
                "avg_latency": round(v.metrics.avg_latency, 1),
                "failure_video": v.failure_video,
                "trajectory": v.trajectory,
            }
            for v in variants[:limit]
        ],
    }


async def browser_playbook_record(
    task: str,
    url: str,
    trajectory: list[dict],
    success: bool = True,
    steps: int = 0,
    latency: float = 0.0,
    user_rating: float = 5.0,
    failure_video: Optional[str] = None,
) -> dict:
    """Record (or update) a playbook variant with metrics."""
    variant_id = _store.save_variant(
        task,
        url,
        trajectory,
        success,
        steps,
        latency,
        user_rating,
        failure_video=failure_video,
    )
    return {
        "status": "ok",
        "task": task,
        "url": url,
        "variant_id": variant_id,
        "message": "Playbook recorded and ranked",
    }


async def browser_playbook_list(task_filter: str = "") -> dict:
    """List all playbooks, optionally filtered by task name."""
    import json
    from pathlib import Path

    pb_dir = Path(".sin_playbooks")
    if not pb_dir.exists():
        return {"status": "ok", "playbooks": []}

    playbooks = []
    for task_dir in pb_dir.iterdir():
        if not task_dir.is_dir():
            continue
        task_name = task_dir.name.replace("_", ":")
        if task_filter and task_filter.lower() not in task_name.lower():
            continue
        for url_dir in task_dir.iterdir():
            if not url_dir.is_dir():
                continue
            variants_file = url_dir / "variants.json"
            if variants_file.exists():
                try:
                    data = json.load(open(variants_file))
                    playbooks.append(
                        {
                            "task": task_name,
                            "url": data.get("url", "?"),
                            "variant_count": len(data.get("variants", [])),
                        }
                    )
                except Exception:
                    pass
    return {"status": "ok", "playbooks": playbooks}


async def browser_playbook_compare(task: str, url: str) -> dict:
    """Compare all variants for (task, url): top 3 side-by-side."""
    variants = _store.load_variants(task, url)
    if not variants:
        return {"status": "not_found"}
    return {
        "status": "ok",
        "task": task,
        "url": url,
        "comparison": [
            {
                "variant_id": v.variant_id,
                "success_rate_pct": round(v.metrics.success_rate * 100, 1),
                "avg_steps": round(v.metrics.avg_steps, 1),
                "avg_latency_s": round(v.metrics.avg_latency, 1),
                "total_runs": v.metrics.total_runs,
            }
            for v in variants[:3]
        ],
    }
