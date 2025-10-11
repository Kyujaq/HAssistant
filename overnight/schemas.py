"""
Data schemas and models for overnight intelligence system.

Defines Pydantic models for:
- Task definitions
- Memory consolidation
- Information enrichment
- Artifact management
"""

from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class TaskPriority(str, Enum):
    """Task priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(str, Enum):
    """Task execution status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MemoryTier(str, Enum):
    """Memory tier levels"""
    SESSION = "session"
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"
    PERMANENT = "permanent"


class Task(BaseModel):
    """Base task model"""
    id: str = Field(description="Unique task identifier")
    type: str = Field(description="Task type (enrichment, consolidation, etc.)")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM)
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class EnrichmentTask(Task):
    """Information enrichment task"""
    type: Literal["enrichment"] = "enrichment"
    query: str = Field(description="Query to enrich")
    sources: List[str] = Field(default_factory=list, description="Sources to use")
    max_results: int = Field(default=5, description="Maximum results to gather")


class ConsolidationTask(Task):
    """Memory consolidation task"""
    type: Literal["consolidation"] = "consolidation"
    time_window_hours: int = Field(default=24, description="Time window for consolidation")
    min_confidence: float = Field(default=0.7, description="Minimum confidence threshold")


class CalendarTask(Task):
    """Calendar integration task"""
    type: Literal["calendar"] = "calendar"
    action: Literal["fetch", "create", "update", "delete"] = "fetch"
    event_data: Optional[Dict[str, Any]] = None


class Artifact(BaseModel):
    """Enrichment artifact"""
    id: str = Field(description="Unique artifact identifier")
    task_id: str = Field(description="Source task ID")
    type: str = Field(description="Artifact type")
    title: str = Field(description="Artifact title")
    content: str = Field(description="Artifact content")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    source: Optional[str] = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    tags: List[str] = Field(default_factory=list)


class ConsolidatedMemory(BaseModel):
    """Consolidated memory result"""
    id: str = Field(description="Unique memory identifier")
    summary: str = Field(description="Memory summary")
    insights: List[str] = Field(default_factory=list)
    related_memories: List[str] = Field(default_factory=list)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    tier: MemoryTier = Field(default=MemoryTier.MEDIUM)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WebSearchResult(BaseModel):
    """Web search result"""
    title: str
    url: str
    snippet: str
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    source: str = "web"


class EnrichmentResult(BaseModel):
    """Information enrichment result"""
    task_id: str
    query: str
    results: List[WebSearchResult] = Field(default_factory=list)
    summary: str
    artifacts: List[Artifact] = Field(default_factory=list)
    completed_at: datetime = Field(default_factory=datetime.utcnow)


# ========================================
# To-Do #1: Commute & Travel Schemas
# ========================================

class CommuteAlert(BaseModel):
    """Alert for commute/travel conditions"""
    event_title: str = Field(description="Title of the calendar event")
    predicted_travel_time_minutes: int = Field(description="Predicted travel time in minutes")
    recommended_departure_time: str = Field(description="Recommended departure time (ISO format)")
    reasoning: str = Field(description="Explanation of the alert (e.g., 'Heavy traffic expected')")
    origin: Optional[str] = None
    destination: Optional[str] = None
    baseline_time_minutes: Optional[int] = None


class ProactivePlanningOutput(BaseModel):
    """Output from the Proactive Planning Crew"""
    task_id: str
    calendar_events: List[Dict[str, Any]] = Field(default_factory=list)
    commute_alerts: List[CommuteAlert] = Field(default_factory=list)
    research_briefings: Dict[str, "ResearchBriefing"] = Field(default_factory=dict)
    summary: str
    completed_at: datetime = Field(default_factory=datetime.utcnow)


# ========================================
# To-Do #2: Energy Analysis Schemas
# ========================================

class EnergyInsight(BaseModel):
    """Energy consumption insight"""
    title: str = Field(description="Short title for the insight")
    description: str = Field(description="Detailed description of the insight")
    severity: Literal["info", "warning"] = Field(default="info", description="Severity level")
    device_name: Optional[str] = None
    energy_kwh: Optional[float] = None
    time_period: Optional[str] = None


class PatternAnalysisOutput(BaseModel):
    """Output from the Pattern Analysis Crew"""
    task_id: str
    energy_insights: List[EnergyInsight] = Field(default_factory=list)
    analysis_period: str
    total_consumption_kwh: Optional[float] = None
    summary: str
    completed_at: datetime = Field(default_factory=datetime.utcnow)


# ========================================
# To-Do #3: Task Priming Schemas
# ========================================

class ResearchBriefing(BaseModel):
    """Research briefing for a to-do task"""
    task_title: str = Field(description="Title of the to-do task")
    briefing: str = Field(description="Markdown briefing with summary and links")
    memory_ids: List[str] = Field(default_factory=list, description="Relevant internal memory IDs")
    external_urls: List[str] = Field(default_factory=list, description="Relevant external URLs")
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
