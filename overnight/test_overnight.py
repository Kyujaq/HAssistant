"""
Tests for overnight intelligence system.
"""

import pytest
import asyncio
from datetime import datetime

from overnight.schemas import (
    Task, TaskStatus, TaskPriority,
    EnrichmentTask, ConsolidationTask,
    Artifact, ConsolidatedMemory, MemoryTier
)
from overnight.guards import GuardRails, ValidationError, RateLimitError
from overnight.artifacts import ArtifactManager


def test_task_creation():
    """Test basic task creation"""
    task = Task(
        id="test-123",
        type="enrichment",
        priority=TaskPriority.HIGH
    )
    
    assert task.id == "test-123"
    assert task.type == "enrichment"
    assert task.priority == TaskPriority.HIGH
    assert task.status == TaskStatus.PENDING


def test_enrichment_task():
    """Test enrichment task creation"""
    task = EnrichmentTask(
        id="enrich-123",
        query="home automation",
        max_results=5
    )
    
    assert task.type == "enrichment"
    assert task.query == "home automation"
    assert task.max_results == 5


def test_consolidation_task():
    """Test consolidation task creation"""
    task = ConsolidationTask(
        id="consolidate-123",
        time_window_hours=24,
        min_confidence=0.7
    )
    
    assert task.type == "consolidation"
    assert task.time_window_hours == 24
    assert task.min_confidence == 0.7


def test_artifact_creation():
    """Test artifact creation"""
    artifact = Artifact(
        id="artifact-123",
        task_id="task-123",
        type="research",
        title="Test Artifact",
        content="Test content",
        confidence=0.8,
        tags=["test"]
    )
    
    assert artifact.id == "artifact-123"
    assert artifact.task_id == "task-123"
    assert artifact.type == "research"
    assert artifact.confidence == 0.8


def test_consolidated_memory():
    """Test consolidated memory creation"""
    memory = ConsolidatedMemory(
        id="memory-123",
        summary="Test summary",
        insights=["insight 1", "insight 2"],
        importance=0.9,
        tier=MemoryTier.LONG
    )
    
    assert memory.id == "memory-123"
    assert len(memory.insights) == 2
    assert memory.importance == 0.9
    assert memory.tier == MemoryTier.LONG


def test_guard_rails_content_validation():
    """Test content validation"""
    guards = GuardRails()
    
    # Valid content
    assert guards.validate_memory_content("Valid content")
    
    # Empty content
    with pytest.raises(ValidationError):
        guards.validate_memory_content("")
        
    # Too long content
    with pytest.raises(ValidationError):
        guards.validate_memory_content("x" * 20000)


def test_guard_rails_task_validation():
    """Test task validation"""
    guards = GuardRails()
    
    # Valid task
    valid_task = {
        "type": "enrichment",
        "id": "task-123"
    }
    assert guards.validate_task_data(valid_task)
    
    # Missing field
    invalid_task = {"type": "enrichment"}
    with pytest.raises(ValidationError):
        guards.validate_task_data(invalid_task)
        
    # Invalid type
    invalid_type_task = {
        "type": "invalid",
        "id": "task-123"
    }
    with pytest.raises(ValidationError):
        guards.validate_task_data(invalid_type_task)


def test_guard_rails_url_validation():
    """Test URL validation"""
    guards = GuardRails()
    
    # Valid URLs
    assert guards.validate_web_url("https://example.com")
    assert guards.validate_web_url("http://example.com")
    
    # Invalid URLs
    with pytest.raises(ValidationError):
        guards.validate_web_url("")
        
    with pytest.raises(ValidationError):
        guards.validate_web_url("ftp://example.com")
        
    with pytest.raises(ValidationError):
        guards.validate_web_url("https://localhost")


def test_guard_rails_rate_limiting():
    """Test rate limiting"""
    guards = GuardRails()
    
    # Should allow first 10 operations
    for i in range(10):
        assert guards.check_rate_limit("test_op", max_per_hour=100, max_per_minute=10)
        
    # 11th operation should fail
    with pytest.raises(RateLimitError):
        guards.check_rate_limit("test_op", max_per_hour=100, max_per_minute=10)


def test_artifact_manager():
    """Test artifact manager"""
    import tempfile
    import shutil
    
    # Create temporary directory
    temp_dir = tempfile.mkdtemp()
    
    try:
        manager = ArtifactManager(base_dir=temp_dir)
        
        # Create artifact
        artifact = manager.create_artifact(
            task_id="task-123",
            artifact_type="test",
            title="Test Artifact",
            content="Test content",
            tags=["test"]
        )
        
        assert artifact.task_id == "task-123"
        assert artifact.type == "test"
        
        # Load artifact
        loaded = manager.load_artifact(artifact.id)
        assert loaded is not None
        assert loaded.id == artifact.id
        assert loaded.content == "Test content"
        
        # List artifacts
        artifacts = manager.list_artifacts()
        assert len(artifacts) == 1
        assert artifacts[0].id == artifact.id
        
        # Delete artifact
        assert manager.delete_artifact(artifact.id)
        assert manager.load_artifact(artifact.id) is None
        
    finally:
        # Clean up
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
