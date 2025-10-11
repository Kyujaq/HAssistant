"""
Tools module for overnight intelligence system.

Exports all available tools for memory, calendar, web, traffic, energy, and todo operations.
"""

from tools.memory_tools import (
    add_memory,
    search_memories,
    get_daily_brief,
    pin_memory,
    run_maintenance
)

from tools.calendar_tools import (
    get_calendar_events,
    create_calendar_event,
    get_upcoming_events
)

from tools.web_tools import (
    web_search,
    fetch_url_content,
    extract_main_content,
    summarize_web_content,
    research_topic
)

from tools.traffic_tools import (
    get_predicted_travel_time,
    analyze_commute_impact
)

from tools.energy_tools import (
    get_energy_consumption_24h,
    get_device_energy_breakdown,
    get_weekly_average_consumption
)

from tools.todo_tools import (
    get_todo_items,
    get_upcoming_tasks,
    create_todo_item,
    update_todo_item
)

__all__ = [
    # Memory tools
    "add_memory",
    "search_memories",
    "get_daily_brief",
    "pin_memory",
    "run_maintenance",
    # Calendar tools
    "get_calendar_events",
    "create_calendar_event",
    "get_upcoming_events",
    # Web tools
    "web_search",
    "fetch_url_content",
    "extract_main_content",
    "summarize_web_content",
    "research_topic",
    # Traffic tools
    "get_predicted_travel_time",
    "analyze_commute_impact",
    # Energy tools
    "get_energy_consumption_24h",
    "get_device_energy_breakdown",
    "get_weekly_average_consumption",
    # Todo tools
    "get_todo_items",
    "get_upcoming_tasks",
    "create_todo_item",
    "update_todo_item",
]
