"""
Tests for new overnight intelligence features (commute, energy, todos).
"""

import pytest
from datetime import datetime, timedelta

from overnight.schemas import (
    CommuteAlert,
    ProactivePlanningOutput,
    EnergyInsight,
    PatternAnalysisOutput,
    ResearchBriefing
)


def test_commute_alert_creation():
    """Test CommuteAlert schema creation"""
    alert = CommuteAlert(
        event_title="Team Meeting",
        predicted_travel_time_minutes=45,
        recommended_departure_time="2024-01-15T08:00:00",
        reasoning="Heavy traffic expected on I-5",
        origin="Home",
        destination="Office",
        baseline_time_minutes=30
    )
    
    assert alert.event_title == "Team Meeting"
    assert alert.predicted_travel_time_minutes == 45
    assert alert.baseline_time_minutes == 30
    assert "Heavy traffic" in alert.reasoning


def test_proactive_planning_output():
    """Test ProactivePlanningOutput schema"""
    alert1 = CommuteAlert(
        event_title="Morning Standup",
        predicted_travel_time_minutes=40,
        recommended_departure_time="2024-01-15T08:30:00",
        reasoning="Moderate traffic"
    )
    
    briefing1 = ResearchBriefing(
        task_title="Review documentation",
        briefing="# Research Briefing\n\nSummary here",
        memory_ids=["mem-1", "mem-2"],
        external_urls=["https://example.com"],
        confidence=0.8
    )
    
    output = ProactivePlanningOutput(
        task_id="plan-123",
        calendar_events=[{"summary": "Event 1"}],
        commute_alerts=[alert1],
        research_briefings={"Review documentation": briefing1},
        summary="Planning complete"
    )
    
    assert output.task_id == "plan-123"
    assert len(output.commute_alerts) == 1
    assert len(output.research_briefings) == 1
    assert "Review documentation" in output.research_briefings


def test_energy_insight_creation():
    """Test EnergyInsight schema"""
    insight = EnergyInsight(
        title="High HVAC Usage",
        description="HVAC consumed 12.5 kWh in 24 hours",
        severity="warning",
        device_name="HVAC System",
        energy_kwh=12.5,
        time_period="24h"
    )
    
    assert insight.title == "High HVAC Usage"
    assert insight.severity == "warning"
    assert insight.device_name == "HVAC System"
    assert insight.energy_kwh == 12.5


def test_pattern_analysis_output():
    """Test PatternAnalysisOutput schema"""
    insight1 = EnergyInsight(
        title="Normal Consumption",
        description="Energy within normal range",
        severity="info"
    )
    
    insight2 = EnergyInsight(
        title="High Usage Alert",
        description="Consumption 25% above average",
        severity="warning"
    )
    
    output = PatternAnalysisOutput(
        task_id="analysis-123",
        energy_insights=[insight1, insight2],
        analysis_period="24h",
        total_consumption_kwh=28.5,
        summary="Analysis complete"
    )
    
    assert output.task_id == "analysis-123"
    assert len(output.energy_insights) == 2
    assert output.total_consumption_kwh == 28.5
    assert output.analysis_period == "24h"


def test_research_briefing():
    """Test ResearchBriefing schema"""
    briefing = ResearchBriefing(
        task_title="Setup automation",
        briefing="# Research Briefing\n\n## Internal Notes\n- Note 1\n\n## External Resources\n- [Link](url)",
        memory_ids=["id-1", "id-2", "id-3"],
        external_urls=["https://example.com/1", "https://example.com/2"],
        confidence=0.85
    )
    
    assert briefing.task_title == "Setup automation"
    assert len(briefing.memory_ids) == 3
    assert len(briefing.external_urls) == 2
    assert briefing.confidence == 0.85
    assert "Research Briefing" in briefing.briefing


@pytest.mark.asyncio
async def test_traffic_analysis_mock():
    """Test traffic analysis with mock data"""
    from overnight.tools.traffic_tools import (
        get_predicted_travel_time,
        analyze_commute_impact
    )
    
    # Test during rush hour
    rush_hour = datetime.now().replace(hour=8, minute=0)
    result = await get_predicted_travel_time(
        origin="Home",
        destination="Office",
        departure_time=rush_hour
    )
    
    assert result["source"] == "mock"
    assert result["predicted_duration_minutes"] > 0
    assert result["baseline_duration_minutes"] > 0
    
    # Test impact analysis
    impact = await analyze_commute_impact(
        predicted_minutes=45,
        baseline_minutes=30,
        threshold_percent=20.0
    )
    
    assert impact["should_alert"] is True
    assert impact["delay_percent"] == 50.0
    assert impact["delay_minutes"] == 15


@pytest.mark.asyncio
async def test_energy_tools_mock():
    """Test energy tools with mock data"""
    from overnight.tools.energy_tools import (
        get_energy_consumption_24h,
        get_device_energy_breakdown
    )
    
    # Test total consumption
    consumption = await get_energy_consumption_24h()
    
    assert consumption["source"] == "mock"
    assert consumption["total_kwh"] > 0
    assert consumption["period_hours"] == 24
    
    # Test device breakdown
    breakdown = await get_device_energy_breakdown()
    
    assert len(breakdown) > 0
    assert all("device_name" in d for d in breakdown)
    assert all("consumption_kwh" in d for d in breakdown)
    
    # Verify devices are sorted by consumption (highest first)
    consumptions = [d["consumption_kwh"] for d in breakdown]
    assert consumptions == sorted(consumptions, reverse=True)


@pytest.mark.asyncio
async def test_todo_tools_mock():
    """Test todo list tools with mock data"""
    from overnight.tools.todo_tools import (
        get_todo_items,
        get_upcoming_tasks
    )
    
    # Test getting all items
    items = await get_todo_items()
    
    assert len(items) > 0
    assert all("summary" in item for item in items)
    assert all("status" in item for item in items)
    
    # Test getting upcoming tasks
    upcoming = await get_upcoming_tasks(days_ahead=1)
    
    assert len(upcoming) > 0
    # All should be needs_action
    assert all(item.get("status") == "needs_action" for item in upcoming)


@pytest.mark.asyncio
async def test_commute_planner_agent():
    """Test CommutePlannerAgent"""
    from overnight.crews.proactive_planning import CommutePlannerAgent
    
    agent = CommutePlannerAgent()
    
    # Test event without location (should return None)
    event_no_location = {
        "summary": "Remote Meeting",
        "start": {"dateTime": (datetime.now() + timedelta(days=1)).isoformat()}
    }
    
    result = await agent.analyze_event_commute(
        event=event_no_location,
        user_location="Home"
    )
    
    assert result is None
    
    # Test event with location (should generate alert during rush hour)
    tomorrow_morning = datetime.now().replace(hour=9, minute=0) + timedelta(days=1)
    event_with_location = {
        "summary": "Office Meeting",
        "location": "123 Main St",
        "start": {"dateTime": tomorrow_morning.isoformat()}
    }
    
    result = await agent.analyze_event_commute(
        event=event_with_location,
        user_location="Home"
    )
    
    # With rush hour timing, should get an alert (mock returns 50% delay)
    assert result is not None
    assert isinstance(result, CommuteAlert)
    assert result.event_title == "Office Meeting"
    assert result.predicted_travel_time_minutes > 0


@pytest.mark.asyncio
async def test_researcher_agent():
    """Test ResearcherAgent"""
    from overnight.crews.proactive_planning import ResearcherAgent
    
    agent = ResearcherAgent()
    
    task = {
        "summary": "Setup home automation",
        "description": "Configure automation rules for lighting"
    }
    
    result = await agent.research_task(task)
    
    assert isinstance(result, ResearchBriefing)
    assert result.task_title == "Setup home automation"
    assert len(result.briefing) > 0
    assert "Research Briefing" in result.briefing


@pytest.mark.asyncio
async def test_energy_auditor_agent():
    """Test EnergyAuditorAgent"""
    from overnight.crews.pattern_analysis import EnergyAuditorAgent
    
    agent = EnergyAuditorAgent()
    
    insights = await agent.analyze_daily_energy()
    
    assert len(insights) > 0
    assert all(isinstance(i, EnergyInsight) for i in insights)
    
    # Should have at least one insight about consumption
    assert any("consumption" in i.description.lower() for i in insights)


@pytest.mark.asyncio
async def test_proactive_planning_crew():
    """Test ProactivePlanningCrew integration"""
    from overnight.crews.proactive_planning import ProactivePlanningCrew
    
    crew = ProactivePlanningCrew()
    
    result = await crew.run_daily_planning(
        user_location="Home",
        todo_entity_id="todo.tasks",
        days_ahead=1
    )
    
    assert isinstance(result, ProactivePlanningOutput)
    assert len(result.task_id) > 0
    assert len(result.summary) > 0


@pytest.mark.asyncio
async def test_pattern_analysis_crew():
    """Test PatternAnalysisCrew integration"""
    from overnight.crews.pattern_analysis import PatternAnalysisCrew
    
    crew = PatternAnalysisCrew()
    
    result = await crew.run_daily_analysis()
    
    assert isinstance(result, PatternAnalysisOutput)
    assert len(result.task_id) > 0
    assert result.analysis_period == "24h"
    assert len(result.energy_insights) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
