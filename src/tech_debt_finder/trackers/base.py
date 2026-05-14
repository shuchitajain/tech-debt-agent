"""
base.py — Abstract base class for issue trackers

WHAT IS AN ABSTRACT BASE CLASS (ABC)?
=====================================
An ABC defines a "contract" — it says "any tracker MUST have these methods".
If you create a JiraTracker but forget to implement create_issue(), 
Python will raise an error immediately.

This is like Dart's abstract classes:
    abstract class Tracker {
        Future<Issue> createIssue(String title, String body);
    }

In Python, we use the `abc` module and @abstractmethod decorator.

WHY USE THIS?
=============
1. Self-documenting — anyone can see what methods a tracker needs
2. Fail fast — errors at import time, not runtime
3. Type hints work — your IDE knows what methods exist
4. Easy to add new trackers — just implement the contract
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class TrackerResult:
    """
    Result of creating an issue.
    
    We use a dataclass to return structured data instead of a dict.
    This gives us:
    - Type hints (IDE autocomplete works)
    - Immutability (by default)
    - Nice __repr__ for debugging
    
    Similar to Dart's freezed or built_value.
    """
    success: bool
    issue_id: Optional[str] = None
    issue_url: Optional[str] = None
    error: Optional[str] = None
    skipped_reason: Optional[str] = None  # e.g., "duplicate exists"


class BaseTracker(ABC):
    """
    Abstract base class for issue trackers.
    
    Any tracker (GitHub, Jira, Azure Boards) must implement these methods.
    The agent code doesn't care WHICH tracker it's using — it just calls
    these methods and trusts the implementation to handle the details.
    
    This is called "Dependency Inversion" — high-level code (agent) depends
    on abstractions (BaseTracker), not concrete implementations (GitHubTracker).
    """
    
    @abstractmethod
    def create_issue(
        self,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> TrackerResult:
        """
        Create an issue in the tracker.
        
        Args:
            title: Issue title (e.g., "Tech Debt: 5 high-priority TODOs in auth module")
            body: Issue body (markdown supported)
            labels: Optional labels (e.g., ["tech-debt", "auto-generated"])
        
        Returns:
            TrackerResult with success status and issue URL
        """
        pass
    
    @abstractmethod
    def check_duplicate(self, title: str) -> Optional[str]:
        """
        Check if an issue with this title already exists.
        
        This prevents the agent from creating duplicate tickets every time
        it runs. We search by title since that's the most reliable way.
        
        Args:
            title: The title to search for
        
        Returns:
            Issue URL if duplicate exists, None otherwise
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """
        Return the tracker name for display purposes.
        
        Example: "GitHub Issues", "Jira", "Azure Boards"
        """
        pass
