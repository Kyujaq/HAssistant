"""
K80 Real-World Processor

Lightweight detection on K80 GPU 3 for:
- Person detection (YOLOv8n)
- Face detection (RetinaFace)
- Pose estimation (MediaPipe)
- Gesture recognition (simple gestures)
- Scene change tracking

Only calls heavy Qwen model when scene changes significantly.
"""

import os
import time
from typing import List, Dict, Any, Tuple
import numpy as np
import cv2
import torch

# Detection result class
class Detection:
    def __init__(self, label: str, bbox: List[float], confidence: float, metadata: Dict[str, Any] = None):
        self.label = label
        self.bbox = bbox  # [x, y, w, h]
        self.confidence = confidence
        self.metadata = metadata or {}

    def to_dict(self):
        return {
            "label": self.label,
            "bbox": self.bbox,
            "confidence": self.confidence,
            "metadata": self.metadata
        }


class SceneTracker:
    """
    Tracks scene changes based on detection similarity
    Similar to vision-gateway's scene tracker
    """
    def __init__(self, change_threshold: float = 0.3):
        self.change_threshold = change_threshold
        self.last_summary = None
        self.last_change_time = time.time()
        self.min_time_between_changes = 2.0  # Seconds

    def has_changed(self, current_summary: Dict[str, Any]) -> bool:
        """
        Determine if scene has changed significantly

        Args:
            current_summary: Current detection summary from get_detection_summary()

        Returns:
            True if scene has changed significantly
        """
        now = time.time()

        # Always trigger on first detection
        if self.last_summary is None:
            self.last_summary = current_summary
            self.last_change_time = now
            return True

        # Rate limit: Don't trigger too frequently
        if (now - self.last_change_time) < self.min_time_between_changes:
            return False

        # Compare summaries
        similarity = self._compute_similarity(self.last_summary, current_summary)

        if similarity < (1.0 - self.change_threshold):
            print(f"[scene_tracker] Scene changed! Similarity: {similarity:.3f}", flush=True)
            self.last_summary = current_summary
            self.last_change_time = now
            return True

        return False

    def _compute_similarity(self, prev: Dict[str, Any], curr: Dict[str, Any]) -> float:
        """
        Compute similarity between two detection summaries

        Returns:
            Similarity score [0.0 - 1.0], where 1.0 is identical
        """
        # Compare counts
        prev_people = prev.get("people_count", 0)
        curr_people = curr.get("people_count", 0)
        prev_faces = prev.get("face_count", 0)
        curr_faces = curr.get("face_count", 0)

        # Person count change
        if prev_people == 0 and curr_people > 0:
            return 0.0  # New person entered
        if prev_people > 0 and curr_people == 0:
            return 0.0  # Person left

        if prev_people != curr_people:
            return 0.5  # Person count changed

        # Face count change
        if abs(prev_faces - curr_faces) > 0:
            return 0.6  # Face visibility changed

        # Compare gestures
        prev_gestures = set(prev.get("gesture_types", []))
        curr_gestures = set(curr.get("gesture_types", []))
        if prev_gestures != curr_gestures:
            return 0.7  # Gesture changed

        # Compare poses (simplified: just check if anyone is standing vs sitting)
        prev_standing = prev.get("standing_count", 0)
        curr_standing = curr.get("standing_count", 0)
        if prev_standing != curr_standing:
            return 0.75  # Pose changed

        # Scene is similar
        return 0.95


class K80RealWorldProcessor:
    """
    Real-world vision processor using K80 GPU

    Runs lightweight models continuously:
    - YOLOv8n for person detection
    - RetinaFace for face detection
    - MediaPipe for pose estimation
    - Simple gesture recognition

    Only triggers Qwen when scene changes significantly.
    """

    def __init__(
        self,
        device: str = "cuda:3",
        scene_change_threshold: float = 0.3,
        yolo_confidence: float = 0.4,
        face_confidence: float = 0.5
    ):
        self.device = device
        self.scene_tracker = SceneTracker(change_threshold=scene_change_threshold)
        self.yolo_confidence = yolo_confidence
        self.face_confidence = face_confidence

        print(f"[k80_realworld] Initializing on {device}...", flush=True)

        # Initialize models
        self._init_yolo()
        self._init_face_detector()
        self._init_pose_estimator()

        print(f"[k80_realworld] Initialization complete!", flush=True)

    def _init_yolo(self):
        """Initialize YOLOv8n for person detection"""
        try:
            from ultralytics import YOLO
            print(f"[k80_realworld] Loading YOLOv8n...", flush=True)
            self.yolo = YOLO("yolov8n.pt")  # Lightweight model
            self.yolo.to(self.device)
            print(f"[k80_realworld] YOLOv8n loaded on {self.device}", flush=True)
        except Exception as e:
            print(f"[k80_realworld] WARNING: YOLOv8 failed to load: {e}", flush=True)
            self.yolo = None

    def _init_face_detector(self):
        """Initialize RetinaFace for face detection"""
        try:
            from retinaface import RetinaFace as RF
            print(f"[k80_realworld] Loading RetinaFace...", flush=True)
            self.retinaface = RF
            # RetinaFace doesn't need explicit device setup - it detects GPU automatically
            print(f"[k80_realworld] RetinaFace loaded", flush=True)
        except Exception as e:
            print(f"[k80_realworld] WARNING: RetinaFace failed to load: {e}", flush=True)
            self.retinaface = None

    def _init_pose_estimator(self):
        """Initialize MediaPipe for pose estimation"""
        try:
            import mediapipe as mp
            print(f"[k80_realworld] Loading MediaPipe Pose...", flush=True)
            self.mp_pose = mp.solutions.pose
            self.pose = self.mp_pose.Pose(
                static_image_mode=False,
                model_complexity=0,  # Lightweight model
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            print(f"[k80_realworld] MediaPipe Pose loaded", flush=True)
        except Exception as e:
            print(f"[k80_realworld] WARNING: MediaPipe failed to load: {e}", flush=True)
            self.pose = None

    def detect_people(self, image: np.ndarray) -> List[Detection]:
        """
        Detect people using YOLOv8n

        Args:
            image: BGR image from OpenCV

        Returns:
            List of Detection objects for detected people
        """
        if self.yolo is None:
            return []

        try:
            results = self.yolo(image, verbose=False, conf=self.yolo_confidence)
            detections = []

            for result in results:
                boxes = result.boxes
                for box in boxes:
                    # Only keep person class (class_id=0 in COCO)
                    if int(box.cls) == 0:
                        xyxy = box.xyxy[0].cpu().numpy()
                        x, y, x2, y2 = xyxy
                        w, h = x2 - x, y2 - y
                        conf = float(box.conf)

                        detections.append(Detection(
                            label="person",
                            bbox=[float(x), float(y), float(w), float(h)],
                            confidence=conf
                        ))

            return detections
        except Exception as e:
            print(f"[k80_realworld] Person detection error: {e}", flush=True)
            return []

    def detect_faces(self, image: np.ndarray) -> List[Detection]:
        """
        Detect faces using RetinaFace

        Args:
            image: BGR image from OpenCV

        Returns:
            List of Detection objects for detected faces
        """
        if self.retinaface is None:
            return []

        try:
            # RetinaFace expects RGB
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            faces = self.retinaface.detect_faces(rgb)

            detections = []
            if faces:
                for key, face_data in faces.items():
                    facial_area = face_data.get("facial_area", [])
                    if len(facial_area) == 4:
                        x, y, x2, y2 = facial_area
                        w, h = x2 - x, y2 - y
                        confidence = face_data.get("score", 1.0)

                        if confidence >= self.face_confidence:
                            detections.append(Detection(
                                label="face",
                                bbox=[float(x), float(y), float(w), float(h)],
                                confidence=float(confidence),
                                metadata={
                                    "landmarks": face_data.get("landmarks", {})
                                }
                            ))

            return detections
        except Exception as e:
            # RetinaFace returns None when no faces detected, which raises exception
            # This is normal - just return empty list
            return []

    def estimate_pose(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Estimate pose using MediaPipe

        Args:
            image: BGR image from OpenCV

        Returns:
            List of pose estimates with landmarks
        """
        if self.pose is None:
            return []

        try:
            # MediaPipe expects RGB
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = self.pose.process(rgb)

            if results.pose_landmarks:
                landmarks = []
                for i, lm in enumerate(results.pose_landmarks.landmark):
                    landmarks.append({
                        "id": i,
                        "x": lm.x,
                        "y": lm.y,
                        "z": lm.z,
                        "visibility": lm.visibility
                    })

                # Analyze pose
                is_standing = self._is_standing(landmarks)

                return [{
                    "landmarks": landmarks,
                    "standing": is_standing
                }]

            return []
        except Exception as e:
            print(f"[k80_realworld] Pose estimation error: {e}", flush=True)
            return []

    def _is_standing(self, landmarks: List[Dict[str, Any]]) -> bool:
        """
        Determine if person is standing based on pose landmarks

        Args:
            landmarks: List of pose landmarks from MediaPipe

        Returns:
            True if person appears to be standing
        """
        try:
            # Get key points: hips and knees
            # MediaPipe landmark indices: 23=left_hip, 24=right_hip, 25=left_knee, 26=right_knee
            left_hip = landmarks[23]
            right_hip = landmarks[24]
            left_knee = landmarks[25]
            right_knee = landmarks[26]

            # Calculate hip-knee distance (vertical)
            avg_hip_y = (left_hip["y"] + right_hip["y"]) / 2
            avg_knee_y = (left_knee["y"] + right_knee["y"]) / 2

            # If knees are significantly below hips, likely standing
            # (y increases downward in image coordinates)
            hip_knee_dist = avg_knee_y - avg_hip_y

            # Threshold: if knees are more than 0.15 below hips (relative to image height), standing
            return hip_knee_dist > 0.15
        except Exception:
            return False

    def detect_gestures(self, poses: List[Dict[str, Any]]) -> List[str]:
        """
        Detect simple gestures from pose landmarks

        Args:
            poses: List of pose estimates

        Returns:
            List of detected gesture labels
        """
        if not poses:
            return []

        gestures = []

        for pose in poses:
            landmarks = pose.get("landmarks", [])
            if not landmarks or len(landmarks) < 33:
                continue

            # Check for wave (hand raised above shoulder)
            try:
                left_shoulder = landmarks[11]
                right_shoulder = landmarks[12]
                left_wrist = landmarks[15]
                right_wrist = landmarks[16]

                # Left hand wave
                if left_wrist["y"] < left_shoulder["y"] and left_wrist["visibility"] > 0.5:
                    gestures.append("wave_left")

                # Right hand wave
                if right_wrist["y"] < right_shoulder["y"] and right_wrist["visibility"] > 0.5:
                    gestures.append("wave_right")

            except Exception:
                pass

        return gestures

    def process_frame(self, image: np.ndarray) -> Dict[str, Any]:
        """
        Process a frame with all detection models

        Args:
            image: BGR image from OpenCV

        Returns:
            Dictionary with detection results and scene change flag
        """
        # Run all detections
        people = self.detect_people(image)
        faces = self.detect_faces(image)
        poses = self.estimate_pose(image)
        gestures = self.detect_gestures(poses)

        # Create summary
        summary = self.get_detection_summary({
            "people": people,
            "faces": faces,
            "poses": poses,
            "gestures": gestures
        })

        # Check for scene changes
        scene_changed = self.scene_tracker.has_changed(summary)

        return {
            "people": [p.to_dict() for p in people],
            "people_count": len(people),
            "faces": [f.to_dict() for f in faces],
            "face_count": len(faces),
            "poses": poses,
            "gestures": gestures,
            "gesture_types": list(set(gestures)),
            "standing_count": sum(1 for p in poses if p.get("standing", False)),
            "scene_changed": scene_changed
        }

    def get_detection_summary(self, detections: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a summary of detections for scene tracking

        Args:
            detections: Raw detection results

        Returns:
            Summary dictionary for scene comparison
        """
        people = detections.get("people", [])
        faces = detections.get("faces", [])
        poses = detections.get("poses", [])
        gestures = detections.get("gestures", [])

        return {
            "people_count": len(people),
            "face_count": len(faces),
            "standing_count": sum(1 for p in poses if p.get("standing", False)),
            "gesture_types": list(set(gestures))
        }
