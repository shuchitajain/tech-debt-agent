"""
notifiers/ — Pluggable notification integrations

Same pattern as trackers — define an interface, implement for each platform.

ADDING A NEW NOTIFIER
=====================
1. Create a new file (e.g., slack.py)
2. Inherit from BaseNotifier
3. Implement send_summary()
4. Register it in get_notifier()
"""

from tech_debt_finder.notifiers.base import BaseNotifier, NotifyResult
from tech_debt_finder.notifiers.email import EmailNotifier


def get_notifier(notifier_type: str, **config) -> BaseNotifier:
    """
    Factory function — returns the right notifier based on user's choice.
    
    Args:
        notifier_type: "email", "slack", "teams", etc.
        **config: Notifier-specific config
    
    Returns:
        A notifier instance ready to use
    """
    notifiers = {
        "email": EmailNotifier,
        # Future: "slack": SlackNotifier,
        # Future: "teams": TeamsNotifier,
    }
    
    if notifier_type not in notifiers:
        supported = ", ".join(notifiers.keys())
        raise ValueError(f"Unknown notifier: {notifier_type}. Supported: {supported}")
    
    return notifiers[notifier_type](**config)


__all__ = ["BaseNotifier", "NotifyResult", "get_notifier", "EmailNotifier"]
