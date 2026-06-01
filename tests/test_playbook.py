"""Tests for playbook system and learning tools."""

import json
import pytest
import tempfile
from pathlib import Path

from sin_browser_tools.playbook import PlaybookStore, Metrics, PlaybookVariant


@pytest.fixture
def temp_store():
    """Create a temporary playbook store for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield PlaybookStore(tmpdir)


def test_playbook_save_and_load_single_variant(temp_store):
    """Save a variant and load it back."""
    trajectory = [
        {"tool": "navigate", "args": {"url": "https://example.com"}},
        {"tool": "wait", "args": {"text": "Loaded"}},
    ]
    variant_id = temp_store.save_variant(
        task="test-task",
        url="https://example.com",
        trajectory=trajectory,
        success=True,
        steps=2,
        latency=1.5,
    )
    assert variant_id is not None

    variants = temp_store.load_variants("test-task", "https://example.com")
    assert len(variants) == 1
    assert variants[0].variant_id == variant_id
    assert variants[0].metrics.success_rate == 1.0
    assert variants[0].metrics.avg_steps == 2.0


def test_playbook_metrics_merge_on_update(temp_store):
    """Save same trajectory twice; metrics merge correctly."""
    trajectory = [{"tool": "click", "args": {"ref": "@e1"}}]
    
    # First run: success
    temp_store.save_variant(
        "task", "https://test.com", trajectory, success=True,
        steps=1, latency=0.5, user_rating=5.0,
    )
    
    # Second run: failure
    temp_store.save_variant(
        "task", "https://test.com", trajectory, success=False,
        steps=1, latency=1.0, user_rating=2.0,
    )
    
    variants = temp_store.load_variants("task", "https://test.com")
    assert len(variants) == 1
    v = variants[0]
    assert v.metrics.success_rate == 0.5  # (1 + 0) / 2
    assert v.metrics.total_runs == 2
    assert v.metrics.avg_latency == 0.75  # (0.5 + 1.0) / 2


def test_playbook_ranking_by_success_rate(temp_store):
    """Multiple variants ranked by success_rate, then avg_steps."""
    traj1 = [{"tool": "a"}]
    traj2 = [{"tool": "b"}]
    
    # Save traj2 with lower success rate
    temp_store.save_variant("task", "url", traj2, success=False, steps=1, latency=0.5)
    
    # Save traj1 with higher success rate
    temp_store.save_variant("task", "url", traj1, success=True, steps=2, latency=1.0)
    
    variants = temp_store.load_variants("task", "url")
    assert len(variants) == 2
    assert variants[0].metrics.success_rate == 1.0  # traj1 first
    assert variants[1].metrics.success_rate == 0.0  # traj2 second


def test_playbook_keep_top_n(temp_store):
    """keep_top=2 trims variants to top 2."""
    for i in range(4):
        traj = [{"tool": f"action_{i}"}]
        temp_store.save_variant(
            "task", "url", traj, success=bool(i % 2),
            steps=1, latency=0.1, keep_top=2
        )
    
    variants = temp_store.load_variants("task", "url")
    assert len(variants) <= 2


@pytest.mark.asyncio
async def test_learning_tools_suggest_not_found():
    """playbook_suggest on empty playbook returns not_found."""
    from sin_browser_tools.tools import learning
    
    result = await learning.browser_playbook_suggest("nonexistent", "https://example.com")
    assert result["status"] == "not_found"


@pytest.mark.asyncio
async def test_learning_tools_record_and_suggest():
    """playbook_record saves; playbook_suggest retrieves it."""
    from sin_browser_tools.tools import learning
    import tempfile
    import os
    
    # Save playbooks in a temp dir for this test
    old_pb = Path(".sin_playbooks")
    with tempfile.TemporaryDirectory() as tmpdir:
        # Monkey-patch for this test
        learning._store = PlaybookStore(tmpdir)
        
        trajectory = [{"tool": "navigate"}]
        record_result = await learning.browser_playbook_record(
            task="test", url="https://example.com",
            trajectory=trajectory, success=True, steps=1, latency=0.5
        )
        assert record_result["status"] == "ok"
        
        suggest_result = await learning.browser_playbook_suggest("test", "https://example.com")
        assert suggest_result["status"] == "ok"
        assert len(suggest_result["variants"]) >= 1
