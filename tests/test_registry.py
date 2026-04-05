"""Tests for BOM registry persistence."""

import json
from pathlib import Path

from agent_aibom.core.models import AgenticBOM, BOMMetadata
from agent_aibom.core.registry import BOMRegistry


def test_save_and_load(registry):
    bom = AgenticBOM(metadata=BOMMetadata(repository="/test"))
    path = registry.save(bom)
    assert path.exists()
    loaded = registry.load(bom.metadata.serial_number)
    assert loaded.metadata.serial_number == bom.metadata.serial_number
    assert loaded.metadata.repository == "/test"


def test_load_by_file_path(registry, tmp_dir):
    bom = AgenticBOM(metadata=BOMMetadata(repository="/test2"))
    path = registry.save(bom)
    loaded = registry.load(str(path))
    assert loaded.metadata.repository == "/test2"


def test_list_boms(registry):
    bom1 = AgenticBOM(metadata=BOMMetadata(repository="/a"))
    bom2 = AgenticBOM(metadata=BOMMetadata(repository="/b"))
    registry.save(bom1)
    registry.save(bom2)
    items = registry.list_boms()
    assert len(items) == 2


def test_delete(registry):
    bom = AgenticBOM()
    registry.save(bom)
    assert registry.delete(bom.metadata.serial_number)
    assert not registry.delete(bom.metadata.serial_number)


def test_diff(registry, sample_bom):
    from agent_aibom.core.models import AgentIdentity, AgentFramework
    bom_a = sample_bom
    registry.save(bom_a)

    # Create bom_b with one agent removed and one added
    bom_b = AgenticBOM(
        agents=[
            sample_bom.agents[0],  # keep test-agent
            AgentIdentity(name="new-agent", framework=AgentFramework.CUSTOM),
        ],
    )
    registry.save(bom_b)

    result = registry.diff(bom_a.metadata.serial_number, bom_b.metadata.serial_number)
    assert "new-agent" in result["added"]
    assert "orphan-agent" in result["removed"]


def test_is_file_path():
    assert BOMRegistry._is_file_path("/tmp/foo.json")
    assert BOMRegistry._is_file_path("./output/bom.json")
    assert not BOMRegistry._is_file_path("urn:uuid:abc-123")


def test_load_missing_raises(registry):
    import pytest
    with pytest.raises(FileNotFoundError):
        registry.load("nonexistent-serial")
