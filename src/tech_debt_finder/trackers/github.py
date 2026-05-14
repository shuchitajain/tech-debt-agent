"""
github.py — GitHub Issues tracker implementation

HOW GITHUB API WORKS
====================
GitHub has a REST API for everything. To create an issue:

    POST https://api.github.com/repos/{owner}/{repo}/issues
    Headers: Authorization: Bearer {token}
    Body: {"title": "...", "body": "...", "labels": [...]}

We use Python's `requests` library (like Dart's http package).

AUTHENTICATION
==============
GitHub uses Personal Access Tokens (PAT) or GitHub App tokens.
The user sets GITHUB_TOKEN environment variable.

To create a token:
1. Go to github.com → Settings → Developer settings → Personal access tokens
2. Generate new token (classic)
3. Select scopes: repo (for private repos) or public_repo (for public)
4. Copy the token and set: export GITHUB_TOKEN=ghp_...

RATE LIMITS
===========
GitHub allows 5000 requests/hour for authenticated users.
Our agent makes ~2-3 requests per issue (check duplicate + create),
so we can handle hundreds of issues per run.
"""

import os
from typing import Optional

import requests

from tech_debt_finder.trackers.base import BaseTracker, TrackerResult


class GitHubTracker(BaseTracker):
    """
    GitHub Issues tracker implementation.
    
    Usage:
        tracker = GitHubTracker(owner="myuser", repo="myrepo")
        result = tracker.create_issue("Bug found", "Description here")
        print(result.issue_url)
    """
    
    # GitHub API base URL
    API_BASE = "https://api.github.com"
    
    def __init__(
        self,
        owner: str,
        repo: str,
        token: str | None = None,
    ):
        """
        Initialize GitHub tracker.
        
        Args:
            owner: GitHub username or organization (e.g., "shuchitajain")
            repo: Repository name (e.g., "tech-debt-finder")
            token: GitHub token. If not provided, reads from GITHUB_TOKEN env var.
        
        Raises:
            ValueError: If no token is provided or found in environment
        """
        self.owner = owner
        self.repo = repo
        
        # Try to get token from parameter or environment
        self.token = token or os.environ.get("GITHUB_TOKEN")
        
        if not self.token:
            raise ValueError(
                "GitHub token required. Set GITHUB_TOKEN environment variable "
                "or pass token parameter.\n"
                "Create one at: https://github.com/settings/tokens"
            )
        
        # Set up headers for all requests
        # This is like setting default headers in Dio (Flutter)
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    
    def get_name(self) -> str:
        """Return tracker name for display."""
        return "GitHub Issues"
    
    def create_issue(
        self,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> TrackerResult:
        """
        Create an issue in GitHub.
        
        This method:
        1. First checks if a duplicate exists (to avoid spam)
        2. If no duplicate, creates the issue
        3. Returns the result with URL or error
        """
        # Check for duplicate first
        existing_url = self.check_duplicate(title)
        if existing_url:
            return TrackerResult(
                success=False,
                skipped_reason=f"Duplicate exists: {existing_url}",
            )
        
        # Build the API URL
        # Example: https://api.github.com/repos/shuchitajain/myrepo/issues
        url = f"{self.API_BASE}/repos/{self.owner}/{self.repo}/issues"
        
        # Build request payload
        payload = {
            "title": title,
            "body": body,
        }
        
        if labels:
            payload["labels"] = labels
        
        try:
            # Make the POST request
            # This is like http.post() in Dart
            response = requests.post(
                url,
                headers=self.headers,
                json=payload,  # Automatically serializes dict to JSON
                timeout=30,    # 30 second timeout
            )
            
            # Check for errors
            # 201 = Created (success for POST)
            if response.status_code == 201:
                data = response.json()
                return TrackerResult(
                    success=True,
                    issue_id=str(data["number"]),
                    issue_url=data["html_url"],
                )
            else:
                # GitHub returns error details in response body
                error_msg = response.json().get("message", response.text)
                return TrackerResult(
                    success=False,
                    error=f"GitHub API error ({response.status_code}): {error_msg}",
                )
        
        except requests.exceptions.Timeout:
            return TrackerResult(
                success=False,
                error="Request timed out. Check your internet connection.",
            )
        except requests.exceptions.RequestException as e:
            return TrackerResult(
                success=False,
                error=f"Request failed: {str(e)}",
            )
    
    def check_duplicate(self, title: str) -> Optional[str]:
        """
        Search for existing issue with same title.
        
        GitHub's search API lets us search issues by title.
        We use the `in:title` qualifier to match exact title.
        
        Returns:
            Issue URL if found, None otherwise
        """
        # GitHub search API
        # https://docs.github.com/en/search-github/searching-on-github/searching-issues-and-pull-requests
        url = f"{self.API_BASE}/search/issues"
        
        # Build search query
        # Example: "Tech Debt: auth module" in:title repo:owner/repo is:issue
        query = f'"{title}" in:title repo:{self.owner}/{self.repo} is:issue'
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                params={"q": query},
                timeout=30,
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if any issues found
                if data.get("total_count", 0) > 0:
                    # Return URL of first match
                    return data["items"][0]["html_url"]
            
            return None
        
        except requests.exceptions.RequestException:
            # If search fails, return None (don't block issue creation)
            return None
