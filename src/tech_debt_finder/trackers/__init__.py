"""
trackers/ — Pluggable issue tracker integrations

WHY THIS DESIGN?
================
We use the "Strategy Pattern" here. Instead of hardcoding one tracker
(like Jira), we define an interface (BaseTracker) and let users choose
which implementation to use at runtime.

This is similar to how Flutter's Provider/Riverpod works — you define
an abstract class, then provide concrete implementations.

ADDING A NEW TRACKER
====================
1. Create a new file (e.g., jira.py)
2. Inherit from BaseTracker
3. Implement create_issue() and check_duplicate()
4. Register it in get_tracker()

Example:
    class JiraTracker(BaseTracker):
        def create_issue(self, title, body, labels):
            # Jira API call here
            pass
"""

from tech_debt_finder.trackers.base import BaseTracker, TrackerResult
from tech_debt_finder.trackers.github import GitHubTracker


def get_tracker(tracker_type: str, **config) -> BaseTracker:
    """
    Factory function — returns the right tracker based on user's choice.
    
    This is a common pattern in Python. Instead of:
        if tracker == "github":
            tracker = GitHubTracker(...)
        elif tracker == "jira":
            tracker = JiraTracker(...)
    
    We centralize it here so the CLI stays clean.
    
    Args:
        tracker_type: "github", "jira", "azure", etc.
        **config: Tracker-specific config (token, project, etc.)
    
    Returns:
        A tracker instance ready to use
    
    Raises:
        ValueError: If tracker_type is not supported
    """
    trackers = {
        "github": GitHubTracker,
        # Future: "jira": JiraTracker,
        # Future: "azure": AzureBoardsTracker,
    }
    
    if tracker_type not in trackers:
        supported = ", ".join(trackers.keys())
        raise ValueError(f"Unknown tracker: {tracker_type}. Supported: {supported}")
    
    return trackers[tracker_type](**config)


__all__ = ["BaseTracker", "TrackerResult", "get_tracker", "GitHubTracker"]
