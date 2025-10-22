"""
K80 GPU Preprocessor with GroundingDINO for continuous object detection.

This module provides GPU-accelerated object detection for UI elements,
running continuously on the Tesla K80 to detect buttons, dialogs, and other
interactive elements without calling the heavy Qwen VL model every frame.
"""

import os
import time
import logging
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass

import numpy as np
import cv2
import torch
from groundingdino.util.inference import load_model

logger = logging.getLogger(__name__)


@dataclass
class Detection:
    """A single detected object."""
    label: str
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    confidence: float


class K80Preprocessor:
    """
    GPU-accelerated object detection using GroundingDINO on Tesla K80.

    Detects UI elements (buttons, dialogs, windows) continuously at 5-10 FPS
    to enable smart triggering of the heavy Qwen VL model only when needed.
    """

    def __init__(
        self,
        device: str = "cuda:2",  # K80 GPU
        model_config_path: Optional[str] = None,
        model_checkpoint_path: Optional[str] = None,
        box_threshold: float = 0.35,
        text_threshold: float = 0.25,
    ):
        """
        Initialize the K80 preprocessor with GroundingDINO.

        Args:
            device: CUDA device to use (default: cuda:2 for K80)
            model_config_path: Path to GroundingDINO config (auto-downloads if None)
            model_checkpoint_path: Path to model weights (auto-downloads if None)
            box_threshold: Confidence threshold for bounding boxes
            text_threshold: Confidence threshold for text matching
        """
        self.device = device
        self.box_threshold = box_threshold
        self.text_threshold = text_threshold

        logger.info(f"Initializing K80Preprocessor on device: {device}")

        # Verify GPU access
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA not available - K80 GPU required")

        gpu_id = int(device.split(":")[-1])
        if gpu_id >= torch.cuda.device_count():
            raise RuntimeError(f"GPU {gpu_id} not available (only {torch.cuda.device_count()} GPUs found)")

        gpu_name = torch.cuda.get_device_name(gpu_id)
        logger.info(f"Using GPU {gpu_id}: {gpu_name}")

        # Load GroundingDINO model
        try:
            logger.info("Loading GroundingDINO model...")
            # Use downloaded model paths if not specified
            if model_config_path is None:
                model_config_path = "/app/models/GroundingDINO/groundingdino/config/GroundingDINO_SwinT_OGC.py"
            if model_checkpoint_path is None:
                model_checkpoint_path = "/app/models/weights/groundingdino_swint_ogc.pth"

            # Check if model files exist
            if not os.path.exists(model_config_path) or not os.path.exists(model_checkpoint_path):
                raise FileNotFoundError(
                    f"Model files not found. Please run download_models.sh first.\n"
                    f"Config: {model_config_path}\n"
                    f"Weights: {model_checkpoint_path}"
                )

            self.model = load_model(
                model_config_path=model_config_path,
                model_checkpoint_path=model_checkpoint_path,
                device=device
            )
            logger.info("GroundingDINO model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load GroundingDINO model: {e}")
            logger.info("Will use simplified detection mode (no model)")
            logger.info("Run download_models.sh to enable K80 preprocessing")
            self.model = None

        # Performance tracking
        self.frame_count = 0
        self.total_time = 0.0
        self.last_fps_log = time.time()

    def detect_elements(
        self,
        frame: np.ndarray,
        prompts: List[str] = None,
    ) -> List[Detection]:
        """
        Detect UI elements in a frame using GroundingDINO.

        Args:
            frame: Input image as numpy array (BGR format from OpenCV)
            prompts: List of text prompts to detect (e.g., ["button", "dialog", "send button"])

        Returns:
            List of Detection objects with labels, bounding boxes, and confidence scores
        """
        if prompts is None:
            prompts = [
                "button",
                "send button",
                "accept button",
                "join button",
                "dialog box",
                "window",
                "text field",
            ]

        start_time = time.time()

        # If model isn't loaded, return empty detections
        if self.model is None:
            logger.warning("GroundingDINO model not loaded - returning empty detections")
            return []

        try:
            # Convert BGR (OpenCV) to RGB tensor on the target GPU
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_tensor = torch.from_numpy(frame_rgb).float()
            frame_tensor = frame_tensor.permute(2, 0, 1).contiguous() / 255.0
            frame_tensor = frame_tensor.to(self.device)

            # Create text prompt (GroundingDINO uses " . " separator)
            text_prompt = " . ".join(prompts)

            # Run detection on K80
            from groundingdino.util.inference import predict as gdino_predict
            boxes, logits, phrases = gdino_predict(
                model=self.model,
                image=frame_tensor,
                caption=text_prompt,
                box_threshold=self.box_threshold,
                text_threshold=self.text_threshold,
            )

            # Convert to Detection objects
            detections = []
            h, w = frame.shape[:2]

            for box, confidence, label in zip(boxes, logits, phrases):
                # Convert normalized coords [0,1] (xyxy) to pixel coords
                x0, y0, x1, y1 = box.tolist()

                # Clamp to valid range to avoid negative values from jitter
                x0 = min(max(x0, 0.0), 1.0)
                y0 = min(max(y0, 0.0), 1.0)
                x1 = min(max(x1, 0.0), 1.0)
                y1 = min(max(y1, 0.0), 1.0)

                px0 = int(x0 * w)
                py0 = int(y0 * h)
                px1 = int(x1 * w)
                py1 = int(y1 * h)

                w_box = max(1, px1 - px0)
                h_box = max(1, py1 - py0)

                detections.append(Detection(
                    label=label,
                    bbox=(px0, py0, w_box, h_box),
                    confidence=float(confidence),
                ))

            # Performance tracking
            elapsed = time.time() - start_time
            self.frame_count += 1
            self.total_time += elapsed

            # Log FPS every 10 seconds
            if time.time() - self.last_fps_log > 10.0:
                avg_fps = self.frame_count / self.total_time if self.total_time > 0 else 0
                logger.info(
                    f"K80 Detection: {len(detections)} elements found | "
                    f"Avg FPS: {avg_fps:.1f} | Frame time: {elapsed*1000:.1f}ms"
                )
                self.frame_count = 0
                self.total_time = 0.0
                self.last_fps_log = time.time()

            return detections

        except Exception as e:
            logger.error(f"Error during K80 detection: {e}")
            return []

    def get_detection_summary(self, detections: List[Detection]) -> Dict[str, Any]:
        """
        Create a summary of detections for comparison and scene change detection.

        Args:
            detections: List of Detection objects

        Returns:
            Dictionary with detection summary (labels, counts, bboxes)
        """
        summary = {
            "count": len(detections),
            "labels": [d.label for d in detections],
            "bboxes": [d.bbox for d in detections],
            "confidences": [d.confidence for d in detections],
            "timestamp": time.time(),
        }
        return summary

    def compute_scene_similarity(
        self,
        prev_summary: Dict[str, Any],
        curr_summary: Dict[str, Any],
    ) -> float:
        """
        Compute similarity between two detection summaries (0.0 = completely different, 1.0 = identical).

        Uses a combination of:
        - Label overlap (Jaccard similarity)
        - Bounding box IoU
        - Detection count difference

        Args:
            prev_summary: Previous frame detection summary
            curr_summary: Current frame detection summary

        Returns:
            Similarity score between 0.0 and 1.0
        """
        if prev_summary is None or curr_summary is None:
            return 0.0

        # Label similarity (Jaccard index)
        prev_labels = set(prev_summary["labels"])
        curr_labels = set(curr_summary["labels"])

        if len(prev_labels) == 0 and len(curr_labels) == 0:
            return 1.0

        label_intersection = len(prev_labels & curr_labels)
        label_union = len(prev_labels | curr_labels)
        label_similarity = label_intersection / label_union if label_union > 0 else 0.0

        # Count similarity
        prev_count = prev_summary["count"]
        curr_count = curr_summary["count"]
        max_count = max(prev_count, curr_count)
        count_similarity = 1.0 - abs(prev_count - curr_count) / max_count if max_count > 0 else 1.0

        # Weighted combination
        similarity = 0.7 * label_similarity + 0.3 * count_similarity

        return similarity


class SceneTracker:
    """
    Tracks scene changes to trigger heavy Qwen VL model only when needed.
    """

    def __init__(self, change_threshold: float = 0.3):
        """
        Initialize scene tracker.

        Args:
            change_threshold: Similarity threshold below which a scene is considered "changed"
        """
        self.change_threshold = change_threshold
        self.last_summary: Optional[Dict[str, Any]] = None
        self.last_significant_change: float = time.time()

    def has_changed(
        self,
        current_summary: Dict[str, Any],
        preprocessor: K80Preprocessor,
    ) -> bool:
        """
        Check if the scene has changed significantly.

        Args:
            current_summary: Current frame detection summary
            preprocessor: K80Preprocessor instance to compute similarity

        Returns:
            True if scene has changed significantly, False otherwise
        """
        if self.last_summary is None:
            self.last_summary = current_summary
            return True  # First frame always triggers

        similarity = preprocessor.compute_scene_similarity(
            self.last_summary,
            current_summary,
        )

        changed = similarity < (1.0 - self.change_threshold)

        if changed:
            self.last_summary = current_summary
            self.last_significant_change = time.time()
            logger.info(f"Scene change detected! Similarity: {similarity:.3f}")

        return changed

    def time_since_last_change(self) -> float:
        """Get time in seconds since last significant scene change."""
        return time.time() - self.last_significant_change
