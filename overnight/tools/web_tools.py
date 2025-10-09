"""
Web research and scraping tools for overnight intelligence system.

Provides tools for gathering information from the web.
"""

import os
import logging
from typing import List, Dict, Any, Optional
import httpx
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

# Configuration
USER_AGENT = "HAssistant-OvernightCrew/1.0"


async def web_search(
    query: str,
    max_results: int = 5,
    search_engine: str = "duckduckgo"
) -> List[Dict[str, Any]]:
    """
    Perform web search using DuckDuckGo.
    
    Args:
        query: Search query
        max_results: Maximum number of results
        search_engine: Search engine to use (default: duckduckgo)
        
    Returns:
        List of search results
    """
    try:
        # Use DuckDuckGo HTML search (no API key needed)
        encoded_query = quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(
                url,
                headers={"User-Agent": USER_AGENT}
            )
            response.raise_for_status()
            
            # For now, return a placeholder structure
            # In production, you'd parse the HTML response
            results = []
            logger.info(f"Web search completed for: {query}")
            
            # Note: Actual HTML parsing would be implemented here
            # This is a simplified version
            return results[:max_results]
            
    except Exception as e:
        logger.error(f"Web search failed for '{query}': {e}")
        return []


async def fetch_url_content(url: str) -> Optional[str]:
    """
    Fetch content from a URL.
    
    Args:
        url: URL to fetch
        
    Returns:
        Page content or None if failed
    """
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(
                url,
                headers={"User-Agent": USER_AGENT}
            )
            response.raise_for_status()
            
            content = response.text
            logger.info(f"Fetched content from: {url} ({len(content)} chars)")
            return content
            
    except Exception as e:
        logger.error(f"Failed to fetch URL '{url}': {e}")
        return None


async def extract_main_content(html: str) -> str:
    """
    Extract main content from HTML.
    
    Args:
        html: HTML content
        
    Returns:
        Extracted text content
    """
    try:
        # Simple text extraction - in production use libraries like BeautifulSoup
        # Remove HTML tags
        import re
        text = re.sub(r'<[^>]+>', '', html)
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        logger.debug(f"Extracted {len(text)} chars of text content")
        return text[:5000]  # Limit to first 5000 chars
        
    except Exception as e:
        logger.error(f"Failed to extract content: {e}")
        return ""


async def summarize_web_content(
    url: str,
    max_length: int = 500
) -> Optional[str]:
    """
    Fetch and summarize content from a URL.
    
    Args:
        url: URL to fetch and summarize
        max_length: Maximum summary length
        
    Returns:
        Summary of the content
    """
    try:
        content = await fetch_url_content(url)
        if not content:
            return None
            
        text = await extract_main_content(content)
        
        # Simple summarization: take first sentences up to max_length
        # In production, use proper summarization
        sentences = text.split('. ')
        summary = ""
        for sentence in sentences:
            if len(summary) + len(sentence) <= max_length:
                summary += sentence + ". "
            else:
                break
                
        logger.info(f"Generated summary for {url}: {len(summary)} chars")
        return summary.strip()
        
    except Exception as e:
        logger.error(f"Failed to summarize content from '{url}': {e}")
        return None


async def research_topic(
    topic: str,
    num_sources: int = 3
) -> Dict[str, Any]:
    """
    Research a topic by gathering information from multiple sources.
    
    Args:
        topic: Topic to research
        num_sources: Number of sources to consult
        
    Returns:
        Research results with sources and summary
    """
    try:
        # Search for the topic
        search_results = await web_search(topic, max_results=num_sources)
        
        # Fetch and summarize content from top results
        sources = []
        for result in search_results:
            url = result.get("url")
            if not url:
                continue
                
            summary = await summarize_web_content(url)
            if summary:
                sources.append({
                    "url": url,
                    "title": result.get("title", ""),
                    "summary": summary
                })
                
        logger.info(f"Completed research on '{topic}' with {len(sources)} sources")
        
        return {
            "topic": topic,
            "sources": sources,
            "source_count": len(sources)
        }
        
    except Exception as e:
        logger.error(f"Research failed for topic '{topic}': {e}")
        return {
            "topic": topic,
            "sources": [],
            "source_count": 0,
            "error": str(e)
        }
