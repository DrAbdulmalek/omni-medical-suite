"""
AI Fuel Engine - Active Learning Module

Provides a human-in-the-loop feedback mechanism for continuously improving
classifier accuracy.  Low-confidence classifications are queued for human
review; approved corrections are exported as training data for model
retraining.

Modules:
    review_queue:       SQLite-backed persistence for review samples.
    feedback_processor: Analyses corrections and suggests taxonomy updates.
"""

from active_learning.review_queue import HumanReviewQueue
from active_learning.feedback_processor import FeedbackProcessor

__all__ = [
    "HumanReviewQueue",
    "FeedbackProcessor",
]
