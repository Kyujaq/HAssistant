#!/usr/bin/env python3
"""
Example client for overnight intelligence system.

This script demonstrates how to use the overnight system programmatically.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from overnight.orchestrator import OvernightOrchestrator
from overnight.crews import InformationEnrichmentCrew, MemoryConsolidationCrew


async def example_full_cycle():
    """Run a complete overnight cycle"""
    print("=== Example: Full Overnight Cycle ===\n")
    
    orchestrator = OvernightOrchestrator()
    results = await orchestrator.run_overnight_cycle()
    
    print(f"Cycle ID: {results['cycle_id']}")
    print(f"Duration: {results['duration_seconds']:.2f}s")
    print(f"Tasks Completed: {len(results['tasks_completed'])}")
    print(f"Tasks Failed: {len(results['tasks_failed'])}")
    
    if 'consolidation_insights' in results:
        print(f"\nInsights Generated:")
        for insight in results['consolidation_insights']:
            print(f"  - {insight}")
    
    return results


async def example_enrichment():
    """Example: Information enrichment"""
    print("\n=== Example: Information Enrichment ===\n")
    
    crew = InformationEnrichmentCrew()
    
    # Enrich a topic
    result = await crew.enrich_topic(
        topic="home automation trends 2024",
        max_sources=3,
        save_to_memory=True
    )
    
    print(f"Query: {result.query}")
    print(f"Results: {len(result.results)}")
    print(f"Artifacts: {len(result.artifacts)}")
    print(f"\nSummary:\n{result.summary}")
    
    return result


async def example_consolidation():
    """Example: Memory consolidation"""
    print("\n=== Example: Memory Consolidation ===\n")
    
    crew = MemoryConsolidationCrew()
    
    # Consolidate recent memories
    result = await crew.consolidate_memories(
        time_window_hours=24,
        min_confidence=0.7
    )
    
    print(f"Consolidation ID: {result.id}")
    print(f"Importance: {result.importance:.2f}")
    print(f"Tier: {result.tier.value}")
    print(f"Related Memories: {len(result.related_memories)}")
    
    print(f"\nSummary:\n{result.summary}")
    
    if result.insights:
        print(f"\nInsights:")
        for insight in result.insights:
            print(f"  - {insight}")
    
    return result


async def example_scheduled_tasks():
    """Example: Schedule tasks"""
    print("\n=== Example: Scheduled Tasks ===\n")
    
    orchestrator = OvernightOrchestrator()
    
    # Schedule enrichment
    enrich_id = await orchestrator.schedule_enrichment(
        query="smart home security",
        max_results=5
    )
    print(f"Scheduled enrichment task: {enrich_id}")
    
    # Schedule consolidation
    consolidate_id = await orchestrator.schedule_consolidation(
        time_window_hours=48,
        min_confidence=0.8
    )
    print(f"Scheduled consolidation task: {consolidate_id}")
    
    # Wait a bit for tasks to complete
    await asyncio.sleep(2)
    
    # Check status
    enrich_status = orchestrator.get_task_status(enrich_id)
    print(f"\nEnrichment task status: {enrich_status['status']}")
    
    consolidate_status = orchestrator.get_task_status(consolidate_id)
    print(f"Consolidation task status: {consolidate_status['status']}")
    
    # List all tasks
    all_tasks = orchestrator.list_tasks(limit=5)
    print(f"\nTotal tasks: {len(all_tasks)}")
    
    return all_tasks


async def example_tools():
    """Example: Using individual tools"""
    print("\n=== Example: Individual Tools ===\n")
    
    from overnight.tools import memory_tools, calendar_tools, web_tools
    
    # Memory tools
    print("1. Searching memories...")
    memories = await memory_tools.search_memories(
        query="automation",
        k=5
    )
    print(f"   Found {len(memories)} memories")
    
    # Calendar tools
    print("\n2. Getting upcoming events...")
    events = await calendar_tools.get_upcoming_events(days=3)
    print(f"   Found {len(events)} upcoming events")
    
    # Web tools
    print("\n3. Researching topic...")
    research = await web_tools.research_topic(
        topic="home assistant automation",
        num_sources=2
    )
    print(f"   Sources: {research['source_count']}")
    
    return {
        "memories": len(memories),
        "events": len(events),
        "sources": research['source_count']
    }


async def main():
    """Main function"""
    print("Overnight Intelligence System - Example Client\n")
    print("=" * 60)
    
    try:
        # Run examples
        # Note: Comment out examples you don't want to run
        
        # Full cycle (runs all tasks)
        await example_full_cycle()
        
        # Individual examples
        # await example_enrichment()
        # await example_consolidation()
        # await example_scheduled_tasks()
        # await example_tools()
        
        print("\n" + "=" * 60)
        print("Examples completed successfully!")
        
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
