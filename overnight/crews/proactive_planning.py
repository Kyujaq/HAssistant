"""
Proactive planning crew for overnight intelligence system.

Handles commute planning and task research preparation.
"""

import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from schemas import (
    ProactivePlanningOutput,
    CommuteAlert,
    ResearchBriefing
)
from tools import (
    calendar_tools,
    traffic_tools,
    todo_tools,
    memory_tools,
    web_tools
)
from guards import GuardRails

logger = logging.getLogger(__name__)


class CommutePlannerAgent:
    """
    Agent for analyzing commute conditions and generating alerts.
    
    This agent:
    1. Reviews calendar events with locations
    2. Gets current user location from Home Assistant
    3. Predicts traffic conditions
    4. Generates alerts for heavy traffic
    """
    
    def __init__(self):
        self.guards = GuardRails()
        logger.info("Initialized CommutePlannerAgent")
    
    async def analyze_event_commute(
        self,
        event: Dict[str, Any],
        user_location: str,
        traffic_threshold_percent: float = 20.0
    ) -> Optional[CommuteAlert]:
        """
        Analyze commute for a calendar event.
        
        Args:
            event: Calendar event dict
            user_location: User's current location (from device_tracker)
            traffic_threshold_percent: Alert threshold
            
        Returns:
            CommuteAlert if traffic warrants alert, None otherwise
        """
        try:
            event_title = event.get("summary", "Unknown Event")
            event_location = event.get("location")
            
            if not event_location:
                logger.debug(f"Event '{event_title}' has no location, skipping commute analysis")
                return None
            
            # Get event start time
            start_time_str = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date")
            if not start_time_str:
                logger.warning(f"Event '{event_title}' has no start time")
                return None
            
            try:
                event_start = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                logger.warning(f"Could not parse start time: {start_time_str}")
                return None
            
            # Calculate recommended departure time (assume 15 min buffer)
            # We'll get traffic prediction for 30 minutes before event
            departure_time = event_start - timedelta(minutes=30)
            
            # Only analyze events in the future
            if departure_time < datetime.now():
                logger.debug(f"Event '{event_title}' departure time has passed")
                return None
            
            # Get traffic prediction
            logger.info(f"Analyzing commute for '{event_title}' from {user_location} to {event_location}")
            traffic_data = await traffic_tools.get_predicted_travel_time(
                origin=user_location,
                destination=event_location,
                departure_time=departure_time
            )
            
            # Analyze if we should alert
            impact = await traffic_tools.analyze_commute_impact(
                predicted_minutes=traffic_data["predicted_duration_minutes"],
                baseline_minutes=traffic_data["baseline_duration_minutes"],
                threshold_percent=traffic_threshold_percent
            )
            
            if not impact["should_alert"]:
                logger.debug(f"No alert needed for '{event_title}' - traffic is normal")
                return None
            
            # Calculate recommended departure time based on predicted travel
            recommended_departure = event_start - timedelta(
                minutes=traffic_data["predicted_duration_minutes"] + 15  # 15 min buffer
            )
            
            alert = CommuteAlert(
                event_title=event_title,
                predicted_travel_time_minutes=traffic_data["predicted_duration_minutes"],
                recommended_departure_time=recommended_departure.isoformat(),
                reasoning=impact["reasoning"],
                origin=traffic_data.get("origin", user_location),
                destination=traffic_data.get("destination", event_location),
                baseline_time_minutes=traffic_data["baseline_duration_minutes"]
            )
            
            logger.info(f"Generated commute alert for '{event_title}': {alert.reasoning}")
            return alert
            
        except Exception as e:
            logger.error(f"Failed to analyze commute for event: {e}")
            return None


class ResearcherAgent:
    """
    Agent for researching and priming to-do tasks.
    
    This agent:
    1. Reads to-do list items
    2. Searches internal memory for relevant context
    3. Searches web for relevant articles
    4. Creates research briefings with links
    """
    
    def __init__(self):
        self.guards = GuardRails()
        logger.info("Initialized ResearcherAgent")
    
    async def research_task(
        self,
        task: Dict[str, Any],
        max_memory_results: int = 3,
        max_web_results: int = 3
    ) -> ResearchBriefing:
        """
        Research a to-do task and create a briefing.
        
        Args:
            task: To-do task dict
            max_memory_results: Max results from memory search
            max_web_results: Max results from web search
            
        Returns:
            ResearchBriefing with summary and links
        """
        try:
            task_title = task.get("summary", "Unknown Task")
            task_description = task.get("description", "")
            
            # Combine title and description for search query
            search_query = f"{task_title} {task_description}".strip()
            
            logger.info(f"Researching task: {task_title}")
            
            # Search internal memory
            memory_results = []
            memory_ids = []
            try:
                memories = await memory_tools.search_memories(
                    query=search_query,
                    k=max_memory_results
                )
                for mem in memories[:max_memory_results]:
                    memory_results.append({
                        "id": mem.get("id", ""),
                        "title": mem.get("title", ""),
                        "preview": mem.get("preview", "")
                    })
                    memory_ids.append(mem.get("id", ""))
                
                logger.info(f"Found {len(memory_results)} relevant memories")
            except Exception as e:
                logger.warning(f"Memory search failed: {e}")
            
            # Search web for external resources
            web_results = []
            external_urls = []
            try:
                web_data = await web_tools.research_topic(
                    topic=search_query,
                    num_sources=max_web_results
                )
                for source in web_data.get("sources", [])[:max_web_results]:
                    web_results.append({
                        "title": source.get("title", ""),
                        "url": source.get("url", ""),
                        "summary": source.get("summary", "")
                    })
                    external_urls.append(source.get("url", ""))
                
                logger.info(f"Found {len(web_results)} relevant web sources")
            except Exception as e:
                logger.warning(f"Web search failed: {e}")
            
            # Create markdown briefing
            briefing_parts = [
                f"# Research Briefing: {task_title}",
                "",
            ]
            
            if task_description:
                briefing_parts.extend([
                    "## Task Description",
                    task_description,
                    ""
                ])
            
            # Add internal memory references
            if memory_results:
                briefing_parts.extend([
                    "## Relevant Internal Notes",
                    ""
                ])
                for mem in memory_results:
                    briefing_parts.append(f"- **{mem['title']}** (ID: `{mem['id']}`)")
                    briefing_parts.append(f"  {mem['preview']}")
                    briefing_parts.append("")
            
            # Add external resources
            if web_results:
                briefing_parts.extend([
                    "## Relevant External Resources",
                    ""
                ])
                for result in web_results:
                    briefing_parts.append(f"- [{result['title']}]({result['url']})")
                    if result['summary']:
                        briefing_parts.append(f"  {result['summary'][:200]}")
                    briefing_parts.append("")
            
            if not memory_results and not web_results:
                briefing_parts.extend([
                    "## No Resources Found",
                    "No relevant internal notes or external resources were found for this task.",
                    ""
                ])
            
            briefing_text = "\n".join(briefing_parts)
            
            # Calculate confidence based on resources found
            confidence = min(1.0, (len(memory_results) + len(web_results)) / 6.0)
            
            briefing = ResearchBriefing(
                task_title=task_title,
                briefing=briefing_text,
                memory_ids=memory_ids,
                external_urls=external_urls,
                confidence=confidence
            )
            
            logger.info(f"Created research briefing for '{task_title}' (confidence: {confidence:.2f})")
            return briefing
            
        except Exception as e:
            logger.error(f"Failed to research task: {e}")
            # Return empty briefing on failure
            return ResearchBriefing(
                task_title=task.get("summary", "Unknown Task"),
                briefing=f"# Research Briefing\n\nFailed to generate briefing: {str(e)}",
                memory_ids=[],
                external_urls=[],
                confidence=0.0
            )


class ProactivePlanningCrew:
    """
    Crew for proactive planning operations.
    
    This crew:
    1. Reviews tomorrow's calendar
    2. Analyzes commute conditions
    3. Researches to-do tasks
    4. Prepares daily briefings
    """
    
    def __init__(self):
        self.commute_planner = CommutePlannerAgent()
        self.researcher = ResearcherAgent()
        self.guards = GuardRails()
        logger.info("Initialized ProactivePlanningCrew")
    
    async def run_daily_planning(
        self,
        user_location: str = "Home",
        todo_entity_id: str = "todo.tasks",
        days_ahead: int = 1
    ) -> ProactivePlanningOutput:
        """
        Run daily proactive planning cycle.
        
        Args:
            user_location: User's current location (for commute planning)
            todo_entity_id: Home Assistant To-Do list entity
            days_ahead: Days to look ahead for planning
            
        Returns:
            ProactivePlanningOutput with all planning results
        """
        task_id = str(uuid.uuid4())
        logger.info(f"Starting proactive planning cycle (id: {task_id})")
        
        try:
            # Check rate limits
            self.guards.check_rate_limit("planning", max_per_hour=20, max_per_minute=2)
            
            # Get tomorrow's calendar events
            logger.info("Fetching calendar events...")
            tomorrow = datetime.now() + timedelta(days=1)
            day_after = tomorrow + timedelta(days=1)
            
            calendar_events = await calendar_tools.get_calendar_events(
                start_date=tomorrow,
                end_date=day_after
            )
            
            logger.info(f"Found {len(calendar_events)} calendar events for tomorrow")
            
            # Analyze commute for each event with location
            commute_alerts = []
            for event in calendar_events:
                alert = await self.commute_planner.analyze_event_commute(
                    event=event,
                    user_location=user_location,
                    traffic_threshold_percent=20.0
                )
                if alert:
                    commute_alerts.append(alert)
            
            logger.info(f"Generated {len(commute_alerts)} commute alerts")
            
            # Get upcoming tasks
            logger.info("Fetching upcoming tasks...")
            upcoming_tasks = await todo_tools.get_upcoming_tasks(
                entity_id=todo_entity_id,
                days_ahead=days_ahead
            )
            
            logger.info(f"Found {len(upcoming_tasks)} upcoming tasks")
            
            # Research each task
            research_briefings = {}
            for task in upcoming_tasks[:10]:  # Limit to 10 tasks to avoid overload
                task_title = task.get("summary", "")
                if task_title:
                    briefing = await self.researcher.research_task(task)
                    research_briefings[task_title] = briefing
            
            logger.info(f"Created {len(research_briefings)} research briefings")
            
            # Create summary
            summary_parts = [
                f"Daily Planning Summary for {tomorrow.strftime('%Y-%m-%d')}:",
                f"- {len(calendar_events)} calendar events",
                f"- {len(commute_alerts)} commute alerts",
                f"- {len(upcoming_tasks)} upcoming tasks",
                f"- {len(research_briefings)} tasks researched"
            ]
            
            summary = "\n".join(summary_parts)
            
            result = ProactivePlanningOutput(
                task_id=task_id,
                calendar_events=calendar_events,
                commute_alerts=commute_alerts,
                research_briefings=research_briefings,
                summary=summary
            )
            
            # Save summary to memory
            try:
                await memory_tools.add_memory(
                    title=f"Daily Planning - {tomorrow.strftime('%Y-%m-%d')}",
                    content=summary,
                    mem_type="insight",
                    tier="medium",
                    tags=["planning", "daily_brief", "proactive"],
                    confidence=0.85
                )
                logger.info("Saved planning summary to memory")
            except Exception as e:
                logger.error(f"Failed to save planning summary: {e}")
            
            logger.info(f"Proactive planning completed: {len(commute_alerts)} alerts, {len(research_briefings)} briefings")
            return result
            
        except Exception as e:
            logger.error(f"Proactive planning failed: {e}")
            return ProactivePlanningOutput(
                task_id=task_id,
                calendar_events=[],
                commute_alerts=[],
                research_briefings={},
                summary=f"Planning failed: {str(e)}"
            )
