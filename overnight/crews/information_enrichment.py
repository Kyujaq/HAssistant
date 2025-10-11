"""
Information gathering and enrichment crew.

Uses Qwen-Agent to gather and enrich information from various sources.
"""

import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from schemas import EnrichmentTask, EnrichmentResult, WebSearchResult, Artifact
from tools import web_tools, memory_tools
from artifacts import ArtifactManager
from guards import GuardRails

logger = logging.getLogger(__name__)


class InformationEnrichmentCrew:
    """
    Crew for gathering and enriching information.
    
    This crew:
    1. Searches for information on a given topic
    2. Gathers content from multiple sources
    3. Creates enrichment artifacts
    4. Stores results in memory
    """
    
    def __init__(self):
        self.artifact_manager = ArtifactManager()
        self.guards = GuardRails()
        logger.info("Initialized InformationEnrichmentCrew")
        
    async def enrich_topic(
        self,
        topic: str,
        max_sources: int = 3,
        save_to_memory: bool = True
    ) -> EnrichmentResult:
        """
        Enrich information about a topic.
        
        Args:
            topic: Topic to enrich
            max_sources: Maximum number of sources to consult
            save_to_memory: Whether to save results to memory
            
        Returns:
            EnrichmentResult with gathered information
        """
        task_id = str(uuid.uuid4())
        logger.info(f"Starting enrichment for topic: {topic} (task_id: {task_id})")
        
        try:
            # Check rate limits
            self.guards.check_rate_limit("enrichment", max_per_hour=50, max_per_minute=5)
            
            # Research the topic
            research_results = await web_tools.research_topic(topic, num_sources=max_sources)
            
            # Convert sources to WebSearchResults
            web_results = []
            for source in research_results.get("sources", []):
                web_results.append(WebSearchResult(
                    title=source.get("title", ""),
                    url=source.get("url", ""),
                    snippet=source.get("summary", "")[:200],  # First 200 chars
                    relevance_score=0.8,
                    source="web"
                ))
                
            # Create summary
            summary_parts = []
            for source in research_results.get("sources", []):
                summary_parts.append(f"- {source.get('title', 'Unknown')}: {source.get('summary', '')[:200]}")
                
            summary = f"Research on '{topic}':\n" + "\n".join(summary_parts)
            
            if not summary_parts:
                summary = f"No detailed information found for topic: {topic}"
                
            # Create artifacts
            artifacts = []
            for idx, source in enumerate(research_results.get("sources", [])):
                artifact = self.artifact_manager.create_artifact(
                    task_id=task_id,
                    artifact_type="research",
                    title=f"{topic} - Source {idx + 1}",
                    content=source.get("summary", ""),
                    metadata={
                        "url": source.get("url", ""),
                        "source_title": source.get("title", "")
                    },
                    source=source.get("url", ""),
                    confidence=0.75,
                    tags=["enrichment", "research", topic.lower()]
                )
                artifacts.append(artifact)
                
            # Save to memory if requested
            if save_to_memory and artifacts:
                try:
                    await memory_tools.add_memory(
                        title=f"Research: {topic}",
                        content=summary,
                        mem_type="insight",
                        tier="medium",
                        tags=["enrichment", "research", topic.lower()],
                        confidence=0.8
                    )
                    logger.info(f"Saved enrichment to memory for topic: {topic}")
                except Exception as e:
                    logger.error(f"Failed to save to memory: {e}")
                    
            result = EnrichmentResult(
                task_id=task_id,
                query=topic,
                results=web_results,
                summary=summary,
                artifacts=artifacts
            )
            
            logger.info(f"Enrichment completed for topic: {topic} ({len(artifacts)} artifacts)")
            return result
            
        except Exception as e:
            logger.error(f"Enrichment failed for topic '{topic}': {e}")
            # Return empty result on failure
            return EnrichmentResult(
                task_id=task_id,
                query=topic,
                results=[],
                summary=f"Enrichment failed: {str(e)}",
                artifacts=[]
            )
            
    async def process_enrichment_task(self, task: EnrichmentTask) -> EnrichmentResult:
        """
        Process an enrichment task.
        
        Args:
            task: EnrichmentTask to process
            
        Returns:
            EnrichmentResult
        """
        logger.info(f"Processing enrichment task: {task.id}")
        
        return await self.enrich_topic(
            topic=task.query,
            max_sources=task.max_results,
            save_to_memory=True
        )
