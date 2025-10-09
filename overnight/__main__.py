#!/usr/bin/env python3
"""
Overnight Intelligence System - Main Entry Point

This script runs the overnight intelligence system as a scheduled service.
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from overnight.orchestrator import OvernightOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point"""
    logger.info("Starting Overnight Intelligence System")
    
    orchestrator = OvernightOrchestrator()
    
    # Run overnight cycle
    try:
        results = await orchestrator.run_overnight_cycle()
        
        logger.info("=== Overnight Cycle Results ===")
        logger.info(f"Cycle ID: {results['cycle_id']}")
        logger.info(f"Duration: {results['duration_seconds']:.2f}s")
        logger.info(f"Tasks Completed: {', '.join(results['tasks_completed'])}")
        
        if results['tasks_failed']:
            logger.warning(f"Tasks Failed: {', '.join(results['tasks_failed'])}")
            
        if 'consolidation_insights' in results:
            logger.info(f"Insights Generated: {len(results['consolidation_insights'])}")
            for insight in results['consolidation_insights']:
                logger.info(f"  - {insight}")
                
        if 'upcoming_events_count' in results:
            logger.info(f"Upcoming Events: {results['upcoming_events_count']}")
            
        if 'memories_evicted' in results:
            logger.info(f"Memories Evicted: {results['memories_evicted']}")
            
        logger.info("===============================")
        
        # Exit with appropriate code
        if results['tasks_failed']:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Overnight cycle failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
