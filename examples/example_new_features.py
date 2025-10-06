#!/usr/bin/env python3
"""
Example client demonstrating new overnight intelligence features:
- Commute planning with traffic analysis
- Energy consumption insights
- Task research and priming
"""

import asyncio
import os
import sys
import tempfile

# Set temp artifacts directory for demo (before imports)
os.environ.setdefault("ARTIFACTS_DIR", tempfile.mkdtemp())

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime

from overnight.crews.proactive_planning import ProactivePlanningCrew
from overnight.crews.pattern_analysis import PatternAnalysisCrew
from overnight.orchestrator import OvernightOrchestrator


async def example_commute_planning():
    """Example: Run commute planning for tomorrow's events"""
    print("\n" + "="*60)
    print("EXAMPLE 1: Commute Planning with Traffic Analysis")
    print("="*60 + "\n")
    
    crew = ProactivePlanningCrew()
    
    print("Running proactive planning for tomorrow...")
    result = await crew.run_daily_planning(
        user_location="Home",  # In production, get from device_tracker
        todo_entity_id="todo.tasks",
        days_ahead=1
    )
    
    print(f"\n📋 Task ID: {result.task_id}")
    print(f"📅 Calendar Events: {len(result.calendar_events)}")
    print(f"🚗 Commute Alerts: {len(result.commute_alerts)}")
    print(f"📚 Research Briefings: {len(result.research_briefings)}")
    
    if result.commute_alerts:
        print("\n🚨 COMMUTE ALERTS:")
        for alert in result.commute_alerts:
            print(f"\n  Event: {alert.event_title}")
            print(f"  📍 {alert.origin} → {alert.destination}")
            print(f"  ⏱️  Travel Time: {alert.predicted_travel_time_minutes} min")
            print(f"  🕐 Depart By: {alert.recommended_departure_time}")
            print(f"  💡 {alert.reasoning}")
    
    if result.research_briefings:
        print("\n📖 RESEARCH BRIEFINGS:")
        for task_title, briefing in list(result.research_briefings.items())[:3]:
            print(f"\n  Task: {task_title}")
            print(f"  Memory References: {len(briefing.memory_ids)}")
            print(f"  External URLs: {len(briefing.external_urls)}")
            print(f"  Confidence: {briefing.confidence:.2f}")
    
    print("\n" + result.summary)


async def example_energy_analysis():
    """Example: Analyze yesterday's energy consumption"""
    print("\n" + "="*60)
    print("EXAMPLE 2: Energy Consumption Analysis")
    print("="*60 + "\n")
    
    crew = PatternAnalysisCrew()
    
    print("Analyzing energy consumption for the last 24 hours...")
    result = await crew.run_daily_analysis()
    
    print(f"\n📊 Analysis ID: {result.task_id}")
    print(f"⚡ Total Consumption: {result.total_consumption_kwh:.2f} kWh")
    print(f"📆 Period: {result.analysis_period}")
    print(f"💡 Insights Generated: {len(result.energy_insights)}")
    
    if result.energy_insights:
        print("\n🔍 ENERGY INSIGHTS:")
        for insight in result.energy_insights[:5]:  # Show top 5
            severity_icon = "⚠️" if insight.severity == "warning" else "ℹ️"
            print(f"\n  {severity_icon} {insight.title}")
            print(f"     {insight.description}")
            if insight.device_name:
                print(f"     Device: {insight.device_name}")
            if insight.energy_kwh:
                print(f"     Energy: {insight.energy_kwh:.2f} kWh")
    
    print("\n" + result.summary)


async def example_full_overnight_cycle():
    """Example: Run a complete overnight intelligence cycle"""
    print("\n" + "="*60)
    print("EXAMPLE 3: Full Overnight Intelligence Cycle")
    print("="*60 + "\n")
    
    orchestrator = OvernightOrchestrator()
    
    print("Starting complete overnight intelligence cycle...")
    print("This includes:")
    print("  1. Memory consolidation")
    print("  2. Proactive planning (commute + tasks)")
    print("  3. Pattern analysis (energy)")
    print("  4. Calendar review")
    print("  5. Memory maintenance")
    print()
    
    results = await orchestrator.run_overnight_cycle()
    
    print(f"\n✅ CYCLE COMPLETE")
    print(f"Cycle ID: {results['cycle_id']}")
    print(f"Duration: {results['duration_seconds']:.2f}s")
    print(f"\nTasks Completed: {len(results['tasks_completed'])}")
    for task in results['tasks_completed']:
        print(f"  ✓ {task}")
    
    if results['tasks_failed']:
        print(f"\nTasks Failed: {len(results['tasks_failed'])}")
        for task in results['tasks_failed']:
            print(f"  ✗ {task}")
    
    # Show key results
    if 'commute_alerts_count' in results:
        print(f"\n🚗 Commute Alerts: {results['commute_alerts_count']}")
        if results.get('commute_alerts'):
            for alert in results['commute_alerts'][:3]:
                print(f"  - {alert['event']}: {alert['travel_time']} min ({alert['reason']})")
    
    if 'research_briefings_count' in results:
        print(f"\n📚 Research Briefings: {results['research_briefings_count']}")
    
    if 'energy_insights_count' in results:
        print(f"\n⚡ Energy Insights: {results['energy_insights_count']}")
        if results.get('energy_insights'):
            for insight in results['energy_insights'][:3]:
                print(f"  - {insight['title']}: {insight['description'][:80]}...")
    
    if 'total_energy_kwh' in results:
        print(f"\n📊 Total Energy: {results['total_energy_kwh']:.2f} kWh")
    
    if 'upcoming_events_count' in results:
        print(f"\n📅 Upcoming Events: {results['upcoming_events_count']}")
    
    if 'memories_evicted' in results:
        print(f"\n🧹 Memories Evicted: {results['memories_evicted']}")


async def main():
    """Run all examples"""
    print("\n" + "="*60)
    print("Overnight Intelligence System - Feature Examples")
    print("="*60)
    print("\nThese examples demonstrate the three new features:")
    print("  1. Intelligent Commute & Travel Preparation")
    print("  2. Deep Home Energy Analysis")
    print("  3. Task & Project Priming")
    print("\nNote: Using mock data when Home Assistant is not available")
    
    try:
        # Example 1: Commute Planning
        await example_commute_planning()
        
        # Example 2: Energy Analysis
        await example_energy_analysis()
        
        # Example 3: Full Cycle
        await example_full_overnight_cycle()
        
        print("\n" + "="*60)
        print("All examples completed successfully!")
        print("="*60 + "\n")
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
