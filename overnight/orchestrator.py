"""
Main orchestration logic for overnight intelligence system.

Coordinates overnight tasks including:
- Information enrichment
- Memory consolidation
- Calendar integration
"""

import os
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import uuid

from .schemas import (
    Task, TaskStatus, TaskPriority,
    EnrichmentTask, ConsolidationTask, CalendarTask
)
from .crews import InformationEnrichmentCrew, MemoryConsolidationCrew
from .tools import calendar_tools, memory_tools
from .guards import GuardRails

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OvernightOrchestrator:
    """
    Main orchestrator for overnight intelligence operations.
    
    Coordinates:
    - Task scheduling and execution
    - Crew management
    - Error handling and recovery
    """
    
    def __init__(self):
        self.enrichment_crew = InformationEnrichmentCrew()
        self.consolidation_crew = MemoryConsolidationCrew()
        self.guards = GuardRails()
        self.tasks: Dict[str, Task] = {}
        logger.info("Initialized OvernightOrchestrator")
        
    async def run_overnight_cycle(self):
        """
        Run a complete overnight intelligence cycle.
        
        This includes:
        1. Memory consolidation
        2. Calendar review
        3. Maintenance tasks
        """
        logger.info("Starting overnight intelligence cycle")
        cycle_start = datetime.now()
        
        results = {
            "cycle_id": str(uuid.uuid4()),
            "started_at": cycle_start.isoformat(),
            "tasks_completed": [],
            "tasks_failed": [],
            "errors": []
        }
        
        try:
            # Task 1: Memory consolidation
            logger.info("Running memory consolidation...")
            try:
                consolidation_result = await self.consolidation_crew.consolidate_memories(
                    time_window_hours=24
                )
                results["tasks_completed"].append("memory_consolidation")
                results["consolidation_insights"] = consolidation_result.insights
            except Exception as e:
                logger.error(f"Memory consolidation failed: {e}")
                results["tasks_failed"].append("memory_consolidation")
                results["errors"].append(str(e))
                
            # Task 2: Calendar review
            logger.info("Reviewing calendar...")
            try:
                upcoming_events = await calendar_tools.get_upcoming_events(days=7)
                results["tasks_completed"].append("calendar_review")
                results["upcoming_events_count"] = len(upcoming_events)
                
                # Store calendar summary in memory
                if upcoming_events:
                    event_summary = f"Found {len(upcoming_events)} upcoming events in the next 7 days"
                    await memory_tools.add_memory(
                        title="Calendar Review",
                        content=event_summary,
                        mem_type="event",
                        tier="short",
                        tags=["calendar", "overnight"],
                        confidence=0.9
                    )
            except Exception as e:
                logger.error(f"Calendar review failed: {e}")
                results["tasks_failed"].append("calendar_review")
                results["errors"].append(str(e))
                
            # Task 3: Memory maintenance
            logger.info("Running memory maintenance...")
            try:
                maintenance_result = await memory_tools.run_maintenance()
                results["tasks_completed"].append("memory_maintenance")
                results["memories_evicted"] = maintenance_result.get("total_evicted", 0)
            except Exception as e:
                logger.error(f"Memory maintenance failed: {e}")
                results["tasks_failed"].append("memory_maintenance")
                results["errors"].append(str(e))
                
        except Exception as e:
            logger.error(f"Overnight cycle failed: {e}")
            results["errors"].append(str(e))
            
        cycle_end = datetime.now()
        duration = (cycle_end - cycle_start).total_seconds()
        
        results["completed_at"] = cycle_end.isoformat()
        results["duration_seconds"] = duration
        
        logger.info(f"Overnight cycle completed in {duration:.2f}s")
        logger.info(f"Tasks completed: {len(results['tasks_completed'])}, Failed: {len(results['tasks_failed'])}")
        
        return results
        
    async def schedule_enrichment(
        self,
        query: str,
        max_results: int = 5,
        priority: TaskPriority = TaskPriority.MEDIUM
    ) -> str:
        """
        Schedule an information enrichment task.
        
        Args:
            query: Query to enrich
            max_results: Maximum results to gather
            priority: Task priority
            
        Returns:
            Task ID
        """
        task = EnrichmentTask(
            id=str(uuid.uuid4()),
            query=query,
            max_results=max_results,
            priority=priority
        )
        
        self.tasks[task.id] = task
        logger.info(f"Scheduled enrichment task: {task.id} for query: {query}")
        
        # Execute immediately in background
        asyncio.create_task(self._execute_enrichment(task))
        
        return task.id
        
    async def _execute_enrichment(self, task: EnrichmentTask):
        """Execute an enrichment task"""
        try:
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.now()
            
            result = await self.enrichment_crew.process_enrichment_task(task)
            
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result.model_dump()
            
            logger.info(f"Enrichment task completed: {task.id}")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            logger.error(f"Enrichment task failed: {task.id} - {e}")
            
    async def schedule_consolidation(
        self,
        time_window_hours: int = 24,
        min_confidence: float = 0.7,
        priority: TaskPriority = TaskPriority.HIGH
    ) -> str:
        """
        Schedule a memory consolidation task.
        
        Args:
            time_window_hours: Time window for consolidation
            min_confidence: Minimum confidence threshold
            priority: Task priority
            
        Returns:
            Task ID
        """
        task = ConsolidationTask(
            id=str(uuid.uuid4()),
            time_window_hours=time_window_hours,
            min_confidence=min_confidence,
            priority=priority
        )
        
        self.tasks[task.id] = task
        logger.info(f"Scheduled consolidation task: {task.id}")
        
        # Execute immediately in background
        asyncio.create_task(self._execute_consolidation(task))
        
        return task.id
        
    async def _execute_consolidation(self, task: ConsolidationTask):
        """Execute a consolidation task"""
        try:
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.now()
            
            result = await self.consolidation_crew.process_consolidation_task(task)
            
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result.model_dump()
            
            logger.info(f"Consolidation task completed: {task.id}")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            logger.error(f"Consolidation task failed: {task.id} - {e}")
            
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a task.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task status dictionary or None if not found
        """
        task = self.tasks.get(task_id)
        if not task:
            return None
            
        return {
            "id": task.id,
            "type": task.type,
            "status": task.status.value,
            "priority": task.priority.value,
            "created_at": task.created_at.isoformat(),
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "error": task.error
        }
        
    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List tasks with optional filtering.
        
        Args:
            status: Filter by status
            limit: Maximum number of tasks to return
            
        Returns:
            List of task status dictionaries
        """
        tasks = list(self.tasks.values())
        
        if status:
            tasks = [t for t in tasks if t.status == status]
            
        # Sort by creation time (newest first)
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        
        return [self.get_task_status(t.id) for t in tasks[:limit]]
