"""
Guard rails and validation for overnight intelligence system.

Provides safety checks and validation for operations.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when validation fails"""
    pass


class RateLimitError(Exception):
    """Raised when rate limit is exceeded"""
    pass


class GuardRails:
    """Guard rails for overnight operations"""
    
    def __init__(self):
        self.operation_counts: Dict[str, List[datetime]] = {}
        logger.info("Initialized GuardRails")
        
    def validate_memory_content(self, content: str, max_length: int = 10000) -> bool:
        """
        Validate memory content before storing.
        
        Args:
            content: Content to validate
            max_length: Maximum allowed length
            
        Returns:
            True if valid
            
        Raises:
            ValidationError: If validation fails
        """
        if not content or not content.strip():
            raise ValidationError("Content cannot be empty")
            
        if len(content) > max_length:
            raise ValidationError(f"Content exceeds maximum length of {max_length}")
            
        # Check for potentially sensitive patterns
        sensitive_patterns = [
            "password",
            "api_key",
            "secret",
            "token",
            "credit_card"
        ]
        
        content_lower = content.lower()
        for pattern in sensitive_patterns:
            if pattern in content_lower:
                logger.warning(f"Potentially sensitive content detected: {pattern}")
                
        return True
        
    def validate_task_data(self, task_data: Dict[str, Any]) -> bool:
        """
        Validate task data before execution.
        
        Args:
            task_data: Task data to validate
            
        Returns:
            True if valid
            
        Raises:
            ValidationError: If validation fails
        """
        required_fields = ["type", "id"]
        
        for field in required_fields:
            if field not in task_data:
                raise ValidationError(f"Missing required field: {field}")
                
        # Validate task type
        valid_types = ["enrichment", "consolidation", "calendar"]
        if task_data["type"] not in valid_types:
            raise ValidationError(f"Invalid task type: {task_data['type']}")
            
        return True
        
    def check_rate_limit(
        self,
        operation: str,
        max_per_hour: int = 100,
        max_per_minute: int = 10
    ) -> bool:
        """
        Check if operation is within rate limits.
        
        Args:
            operation: Operation name
            max_per_hour: Maximum operations per hour
            max_per_minute: Maximum operations per minute
            
        Returns:
            True if within limits
            
        Raises:
            RateLimitError: If rate limit exceeded
        """
        now = datetime.now()
        
        # Initialize tracking for this operation
        if operation not in self.operation_counts:
            self.operation_counts[operation] = []
            
        # Clean up old timestamps
        one_hour_ago = now - timedelta(hours=1)
        one_minute_ago = now - timedelta(minutes=1)
        
        self.operation_counts[operation] = [
            ts for ts in self.operation_counts[operation]
            if ts > one_hour_ago
        ]
        
        # Check hourly limit
        if len(self.operation_counts[operation]) >= max_per_hour:
            raise RateLimitError(
                f"Rate limit exceeded for {operation}: "
                f"{len(self.operation_counts[operation])} operations in last hour "
                f"(max: {max_per_hour})"
            )
            
        # Check minute limit
        recent_ops = [
            ts for ts in self.operation_counts[operation]
            if ts > one_minute_ago
        ]
        
        if len(recent_ops) >= max_per_minute:
            raise RateLimitError(
                f"Rate limit exceeded for {operation}: "
                f"{len(recent_ops)} operations in last minute "
                f"(max: {max_per_minute})"
            )
            
        # Record this operation
        self.operation_counts[operation].append(now)
        return True
        
    def validate_web_url(self, url: str) -> bool:
        """
        Validate URL for web scraping.
        
        Args:
            url: URL to validate
            
        Returns:
            True if valid
            
        Raises:
            ValidationError: If validation fails
        """
        if not url or not url.strip():
            raise ValidationError("URL cannot be empty")
            
        # Check for valid protocol
        if not url.startswith(("http://", "https://")):
            raise ValidationError("URL must use http or https protocol")
            
        # Blocked domains (add more as needed)
        blocked_domains = [
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "192.168.",
            "10.",
            "172.16."
        ]
        
        url_lower = url.lower()
        for domain in blocked_domains:
            if domain in url_lower:
                raise ValidationError(f"Access to {domain} is blocked")
                
        return True
        
    def validate_calendar_event(self, event_data: Dict[str, Any]) -> bool:
        """
        Validate calendar event data.
        
        Args:
            event_data: Event data to validate
            
        Returns:
            True if valid
            
        Raises:
            ValidationError: If validation fails
        """
        required_fields = ["summary", "start", "end"]
        
        for field in required_fields:
            if field not in event_data:
                raise ValidationError(f"Missing required field: {field}")
                
        # Validate that end is after start
        try:
            start = event_data["start"]
            end = event_data["end"]
            
            if isinstance(start, str):
                start = datetime.fromisoformat(start)
            if isinstance(end, str):
                end = datetime.fromisoformat(end)
                
            if end <= start:
                raise ValidationError("Event end time must be after start time")
                
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Invalid datetime format: {e}")
            
        return True
