"""
Memory Policy - Heuristics for storage decisions and PII redaction
Step 2.5: Memory ↔ LLM Integration
"""
import os
import re
import hashlib
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Configuration from environment
AUTOSAVE = os.getenv("MEMORY_AUTOSAVE_ON", "1") == "1"
MIN_LEN = int(os.getenv("MEMORY_MIN_LENGTH", "12"))
DURABLE_THRESHOLD = int(os.getenv("MEMORY_DURABLE_THRESHOLD", "80"))

# Pattern for boring/trivial responses that shouldn't be saved
BORING_PAT = re.compile(
    r"^(ok|okay|thanks?|thx|thank you|k|cool|yes|yeah|yep|no|nope|"
    r"hmm|uh|um|ah|sure|fine|alright|got it)\W*$",
    re.IGNORECASE
)

# Patterns for "remember that" signals
REMEMBER_SIGNALS = [
    "remember that",
    "remember this",
    "save this",
    "don't forget",
    "keep in mind",
    "note that",
    "important:"
]

# PII patterns (belt & suspenders - applied during storage)
EMAIL_PAT = re.compile(r'\b[\w\.-]+@[\w\.-]+\.\w+\b')
PHONE_PAT = re.compile(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b')
SSN_PAT = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
CREDIT_CARD_PAT = re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b')


def worth_saving(text: str, role: str, ctx_hits: int = 0) -> Tuple[bool, Optional[str]]:
    """
    Determine if a piece of text is worth saving to memory.

    Heuristics:
    - User queries: Always saved (unless autosave is off)
    - Assistant replies:
      - < DURABLE_THRESHOLD chars → chat_ephemeral (can be pruned later)
      - ≥ DURABLE_THRESHOLD chars → chat_assistant (durable)
      - Contains "remember that" signal → force durable
    - Too short (< MIN_LEN chars) → not saved
    - Boring patterns ("ok", "thanks", etc.) → not saved

    Args:
        text: The text to evaluate
        role: Either 'user' or 'assistant'
        ctx_hits: Number of context hits (not currently used in heuristics)

    Returns:
        Tuple of (should_save: bool, kind: Optional[str])
        - If should_save is False, kind will be None
        - If should_save is True, kind will be the memory type
          (e.g., 'chat_user', 'chat_assistant', 'chat_ephemeral')
    """
    # Check if autosave is enabled
    if not AUTOSAVE:
        return False, None

    # Basic validation
    if not text or not text.strip():
        return False, None

    cleaned = text.strip()

    # Length check
    if len(cleaned) < MIN_LEN:
        logger.debug(f"Text too short to save ({len(cleaned)} < {MIN_LEN}): {cleaned[:30]}")
        return False, None

    # Boring pattern check
    if BORING_PAT.match(cleaned):
        logger.debug(f"Boring pattern matched, not saving: {cleaned}")
        return False, None

    # User queries are always durable (they're questions/commands)
    if role == "user":
        return True, "chat_user"

    # Assistant replies: ephemeral vs durable logic
    if role == "assistant":
        # Check for explicit "remember that" signals
        text_lower = text.lower()
        if any(signal in text_lower for signal in REMEMBER_SIGNALS):
            logger.debug(f"'Remember that' signal detected, forcing durable")
            return True, "chat_assistant"

        # Length-based classification
        if len(cleaned) < DURABLE_THRESHOLD:
            # Short replies are ephemeral (can be pruned in night job)
            return True, "chat_ephemeral"
        else:
            # Long, detailed replies are durable
            return True, "chat_assistant"

    # Fallback (shouldn't reach here normally)
    logger.warning(f"Unexpected role '{role}', defaulting to not saving")
    return False, None


def compute_hash(text: str) -> str:
    """
    Compute a stable hash for deduplication.

    The hash is based on normalized (lowercase, stripped) text
    to catch near-duplicates.

    Args:
        text: The text to hash

    Returns:
        16-character hex hash string
    """
    normalized = text.lower().strip()
    hash_bytes = hashlib.sha256(normalized.encode('utf-8')).digest()
    # Return first 16 characters of hex digest
    return hash_bytes.hex()[:16]


def redact(text: str) -> str:
    """
    Redact PII from text before storage (belt & suspenders approach).

    Patterns:
    - Email addresses → [email]
    - Phone numbers → [phone]
    - SSN → [ssn]
    - Credit card numbers → [card]

    Note: This is a basic implementation. For production, consider:
    - More sophisticated PII detection (e.g., using NER models)
    - Configurable redaction patterns
    - Audit logging when PII is detected

    Args:
        text: The text to redact

    Returns:
        Text with PII replaced by placeholders
    """
    redacted = text

    # Email addresses
    redacted = EMAIL_PAT.sub('[email]', redacted)

    # Phone numbers (US format)
    redacted = PHONE_PAT.sub('[phone]', redacted)

    # Social Security Numbers
    redacted = SSN_PAT.sub('[ssn]', redacted)

    # Credit card numbers
    redacted = CREDIT_CARD_PAT.sub('[card]', redacted)

    # Log if any redactions were made
    if redacted != text:
        logger.info(f"PII redaction applied to text")

    return redacted


def classify_by_structure(text: str) -> str:
    """
    Classify text by structural patterns.

    This can be used to assign more specific kinds based on content:
    - Lists → 'note'
    - Questions → 'question'
    - Commands → 'command'
    - etc.

    Args:
        text: The text to classify

    Returns:
        Suggested kind string (currently just returns 'auto')
    """
    # TODO: Add more sophisticated classification if needed
    # For now, just a placeholder for future enhancement

    # Has bullet points or numbered list?
    if re.search(r'(^|\n)\s*[-•*\d]+[\.\)]\s', text):
        return 'note'

    # Has question marks?
    if '?' in text:
        return 'question'

    # Default
    return 'auto'


def should_promote_to_permanent(text: str, metadata: dict) -> bool:
    """
    Determine if a memory should be promoted to permanent tier.

    Criteria:
    - Explicitly tagged as important
    - Contains task/reminder keywords
    - Referenced multiple times
    - etc.

    Args:
        text: The memory text
        metadata: Memory metadata (tags, hits, etc.)

    Returns:
        True if should be promoted to permanent tier
    """
    # Check for importance markers
    text_lower = text.lower()
    importance_markers = [
        "important:",
        "critical:",
        "urgent:",
        "don't forget:",
        "reminder:",
        "todo:",
        "must remember"
    ]

    if any(marker in text_lower for marker in importance_markers):
        return True

    # Check metadata for importance tags
    tags = metadata.get("tags", [])
    if any(tag in ["important", "critical", "permanent"] for tag in tags):
        return True

    # Check if it's been hit/referenced multiple times
    hit_count = metadata.get("hit_count", 0)
    if hit_count >= 5:  # Referenced 5+ times
        return True

    return False
