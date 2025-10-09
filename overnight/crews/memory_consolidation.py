"""
Memory processing and consolidation crew.

Uses Qwen-Agent to consolidate and process memories.
"""

import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from ..schemas import ConsolidationTask, ConsolidatedMemory, MemoryTier
from ..tools import memory_tools
from ..guards import GuardRails

logger = logging.getLogger(__name__)


class MemoryConsolidationCrew:
    """
    Crew for memory consolidation and processing.
    
    This crew:
    1. Reviews recent memories
    2. Identifies patterns and insights
    3. Consolidates related memories
    4. Promotes important memories to higher tiers
    """
    
    def __init__(self):
        self.guards = GuardRails()
        logger.info("Initialized MemoryConsolidationCrew")
        
    async def consolidate_memories(
        self,
        time_window_hours: int = 24,
        min_confidence: float = 0.7
    ) -> ConsolidatedMemory:
        """
        Consolidate recent memories.
        
        Args:
            time_window_hours: Time window to consider (in hours)
            min_confidence: Minimum confidence threshold
            
        Returns:
            ConsolidatedMemory with insights
        """
        consolidation_id = str(uuid.uuid4())
        logger.info(f"Starting memory consolidation (id: {consolidation_id})")
        
        try:
            # Check rate limits
            self.guards.check_rate_limit("consolidation", max_per_hour=10, max_per_minute=2)
            
            # Get daily brief
            brief = await memory_tools.get_daily_brief()
            
            memories = brief.get("memories", [])
            
            if not memories:
                logger.info("No memories to consolidate")
                return ConsolidatedMemory(
                    id=consolidation_id,
                    summary="No memories to consolidate",
                    insights=[],
                    related_memories=[],
                    importance=0.0
                )
                
            # Filter by confidence
            filtered_memories = [
                m for m in memories
                if m.get("confidence", 0) >= min_confidence
            ]
            
            logger.info(f"Consolidating {len(filtered_memories)} memories (filtered from {len(memories)})")
            
            # Generate insights from memories
            insights = await self._generate_insights(filtered_memories)
            
            # Calculate importance based on memory count and confidence
            avg_confidence = sum(m.get("confidence", 0) for m in filtered_memories) / len(filtered_memories)
            importance = min(1.0, (len(filtered_memories) / 10) * avg_confidence)
            
            # Determine tier based on importance
            tier = self._determine_tier(importance)
            
            # Create summary
            summary = self._create_summary(filtered_memories, insights)
            
            # Get related memory IDs
            related_ids = [m.get("id", "") for m in filtered_memories if m.get("id")]
            
            result = ConsolidatedMemory(
                id=consolidation_id,
                summary=summary,
                insights=insights,
                related_memories=related_ids,
                importance=importance,
                tier=tier
            )
            
            # Save consolidated memory
            if insights:
                try:
                    await memory_tools.add_memory(
                        title=f"Consolidated Insights - {datetime.now().strftime('%Y-%m-%d')}",
                        content=summary,
                        mem_type="insight",
                        tier=tier.value,
                        tags=["consolidation", "insights"],
                        confidence=importance,
                        pin=(importance > 0.8)
                    )
                    logger.info("Saved consolidated memory")
                except Exception as e:
                    logger.error(f"Failed to save consolidated memory: {e}")
                    
            logger.info(f"Consolidation completed: {len(insights)} insights, importance: {importance:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"Memory consolidation failed: {e}")
            return ConsolidatedMemory(
                id=consolidation_id,
                summary=f"Consolidation failed: {str(e)}",
                insights=[],
                related_memories=[],
                importance=0.0
            )
            
    async def _generate_insights(self, memories: List[Dict[str, Any]]) -> List[str]:
        """
        Generate insights from memories.
        
        Args:
            memories: List of memory dictionaries
            
        Returns:
            List of insights
        """
        insights = []
        
        # Count memory types
        type_counts: Dict[str, int] = {}
        for memory in memories:
            mem_type = memory.get("type", "unknown")
            type_counts[mem_type] = type_counts.get(mem_type, 0) + 1
            
        # Generate type-based insights
        for mem_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            if count > 1:
                insights.append(f"Multiple {mem_type} events recorded ({count} occurrences)")
                
        # Check for high-confidence memories
        high_conf_memories = [m for m in memories if m.get("confidence", 0) > 0.9]
        if high_conf_memories:
            insights.append(f"Found {len(high_conf_memories)} high-confidence memories")
            
        # Check for pinned memories
        pinned_memories = [m for m in memories if m.get("pinned", False)]
        if pinned_memories:
            insights.append(f"Found {len(pinned_memories)} pinned memories requiring attention")
            
        # Extract common tags
        all_tags = []
        for memory in memories:
            all_tags.extend(memory.get("tags", []))
            
        if all_tags:
            tag_counts = {}
            for tag in all_tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
                
            common_tags = [tag for tag, count in tag_counts.items() if count > 1]
            if common_tags:
                insights.append(f"Common themes: {', '.join(common_tags[:3])}")
                
        return insights
        
    def _determine_tier(self, importance: float) -> MemoryTier:
        """
        Determine appropriate memory tier based on importance.
        
        Args:
            importance: Importance score (0.0-1.0)
            
        Returns:
            Appropriate MemoryTier
        """
        if importance >= 0.9:
            return MemoryTier.PERMANENT
        elif importance >= 0.7:
            return MemoryTier.LONG
        elif importance >= 0.5:
            return MemoryTier.MEDIUM
        else:
            return MemoryTier.SHORT
            
    def _create_summary(self, memories: List[Dict[str, Any]], insights: List[str]) -> str:
        """
        Create a summary of consolidated memories.
        
        Args:
            memories: List of memories
            insights: List of insights
            
        Returns:
            Summary text
        """
        summary_parts = [
            f"Consolidated {len(memories)} memories",
            "",
            "Key Insights:",
        ]
        
        for insight in insights:
            summary_parts.append(f"- {insight}")
            
        if not insights:
            summary_parts.append("- No significant patterns detected")
            
        summary_parts.extend([
            "",
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ])
        
        return "\n".join(summary_parts)
        
    async def process_consolidation_task(self, task: ConsolidationTask) -> ConsolidatedMemory:
        """
        Process a consolidation task.
        
        Args:
            task: ConsolidationTask to process
            
        Returns:
            ConsolidatedMemory result
        """
        logger.info(f"Processing consolidation task: {task.id}")
        
        return await self.consolidate_memories(
            time_window_hours=task.time_window_hours,
            min_confidence=task.min_confidence
        )
