"""
base.py — Abstract base class for notifiers

Notifiers are simpler than trackers — they just send a message.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class NotifyResult:
    """Result of sending a notification."""
    success: bool
    error: Optional[str] = None


class BaseNotifier(ABC):
    """
    Abstract base class for notification channels.
    
    Notifiers are "fire and forget" — we send the message and move on.
    If it fails, we log the error but don't retry (to keep things simple).
    """
    
    @abstractmethod
    def send_summary(
        self,
        subject: str,
        body: str,
        issues_created: list[dict],
    ) -> NotifyResult:
        """
        Send a summary notification.
        
        Args:
            subject: Notification title/subject
            body: Main message body (markdown supported for some platforms)
            issues_created: List of created issues with {title, url, tracker}
        
        Returns:
            NotifyResult with success status
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Return the notifier name for display purposes."""
        pass
