"""
Artifact management for overnight intelligence system.

Handles storage and retrieval of enrichment artifacts.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import uuid

from .schemas import Artifact

logger = logging.getLogger(__name__)

# Configuration
ARTIFACTS_DIR = os.getenv("ARTIFACTS_DIR", "/data/artifacts")


class ArtifactManager:
    """Manages artifact storage and retrieval"""
    
    def __init__(self, base_dir: str = ARTIFACTS_DIR):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized ArtifactManager with base_dir: {self.base_dir}")
        
    def _get_artifact_path(self, artifact_id: str) -> Path:
        """Get file path for an artifact"""
        return self.base_dir / f"{artifact_id}.json"
        
    def save_artifact(self, artifact: Artifact) -> str:
        """
        Save an artifact to disk.
        
        Args:
            artifact: Artifact to save
            
        Returns:
            Artifact ID
        """
        try:
            path = self._get_artifact_path(artifact.id)
            
            with open(path, 'w') as f:
                json.dump(artifact.model_dump(), f, default=str, indent=2)
                
            logger.info(f"Saved artifact: {artifact.id} ({artifact.type})")
            return artifact.id
            
        except Exception as e:
            logger.error(f"Failed to save artifact {artifact.id}: {e}")
            raise
            
    def load_artifact(self, artifact_id: str) -> Optional[Artifact]:
        """
        Load an artifact from disk.
        
        Args:
            artifact_id: Artifact ID to load
            
        Returns:
            Artifact or None if not found
        """
        try:
            path = self._get_artifact_path(artifact_id)
            
            if not path.exists():
                logger.warning(f"Artifact not found: {artifact_id}")
                return None
                
            with open(path, 'r') as f:
                data = json.load(f)
                
            artifact = Artifact(**data)
            logger.debug(f"Loaded artifact: {artifact_id}")
            return artifact
            
        except Exception as e:
            logger.error(f"Failed to load artifact {artifact_id}: {e}")
            return None
            
    def list_artifacts(
        self,
        task_id: Optional[str] = None,
        artifact_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Artifact]:
        """
        List artifacts with optional filtering.
        
        Args:
            task_id: Filter by task ID
            artifact_type: Filter by artifact type
            limit: Maximum number of artifacts to return
            
        Returns:
            List of artifacts
        """
        try:
            artifacts = []
            
            for path in self.base_dir.glob("*.json"):
                if len(artifacts) >= limit:
                    break
                    
                try:
                    with open(path, 'r') as f:
                        data = json.load(f)
                    artifact = Artifact(**data)
                    
                    # Apply filters
                    if task_id and artifact.task_id != task_id:
                        continue
                    if artifact_type and artifact.type != artifact_type:
                        continue
                        
                    artifacts.append(artifact)
                    
                except Exception as e:
                    logger.warning(f"Failed to load artifact from {path}: {e}")
                    continue
                    
            # Sort by creation time (newest first)
            artifacts.sort(key=lambda x: x.created_at, reverse=True)
            
            logger.info(f"Listed {len(artifacts)} artifacts")
            return artifacts
            
        except Exception as e:
            logger.error(f"Failed to list artifacts: {e}")
            return []
            
    def delete_artifact(self, artifact_id: str) -> bool:
        """
        Delete an artifact.
        
        Args:
            artifact_id: Artifact ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        try:
            path = self._get_artifact_path(artifact_id)
            
            if not path.exists():
                logger.warning(f"Artifact not found for deletion: {artifact_id}")
                return False
                
            path.unlink()
            logger.info(f"Deleted artifact: {artifact_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete artifact {artifact_id}: {e}")
            return False
            
    def create_artifact(
        self,
        task_id: str,
        artifact_type: str,
        title: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None,
        confidence: float = 0.8,
        tags: Optional[List[str]] = None
    ) -> Artifact:
        """
        Create and save a new artifact.
        
        Args:
            task_id: Source task ID
            artifact_type: Type of artifact
            title: Artifact title
            content: Artifact content
            metadata: Optional metadata
            source: Optional source information
            confidence: Confidence score
            tags: Optional list of tags
            
        Returns:
            Created artifact
        """
        artifact = Artifact(
            id=str(uuid.uuid4()),
            task_id=task_id,
            type=artifact_type,
            title=title,
            content=content,
            metadata=metadata or {},
            source=source,
            confidence=confidence,
            tags=tags or []
        )
        
        self.save_artifact(artifact)
        return artifact
