"""
email.py — Email notifier implementation

HOW EMAIL SENDING WORKS IN PYTHON
=================================
Python has built-in modules for email:
- `smtplib` — handles the SMTP protocol (sending)
- `email` — helps construct the email message

SMTP (Simple Mail Transfer Protocol) is how email servers talk to each other.
When you send an email, your app connects to an SMTP server (like Gmail's)
and says "please send this message to X".

GMAIL SETUP
===========
To use Gmail:
1. Enable 2-factor authentication on your Google account
2. Go to: https://myaccount.google.com/apppasswords
3. Generate an "App Password" for "Mail"
4. Use that password (not your real password) as EMAIL_PASSWORD

Environment variables needed:
    EMAIL_HOST=smtp.gmail.com
    EMAIL_PORT=587
    EMAIL_USER=your.email@gmail.com
    EMAIL_PASSWORD=xxxx xxxx xxxx xxxx  (app password)
    EMAIL_TO=recipient@example.com

OTHER SMTP SERVERS
==================
- Outlook: smtp.office365.com:587
- Yahoo: smtp.mail.yahoo.com:587
- Custom: your-company.com's SMTP server

SECURITY NOTE
=============
Never hardcode passwords in code. Always use environment variables.
The .env file should be in .gitignore.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from tech_debt_finder.notifiers.base import BaseNotifier, NotifyResult


class EmailNotifier(BaseNotifier):
    """
    Email notifier using SMTP.
    
    Usage:
        notifier = EmailNotifier(
            to_address="team@company.com",
            # Other params from env vars
        )
        notifier.send_summary("Tech Debt Report", "...")
    """
    
    def __init__(
        self,
        to_address: str,
        host: str | None = None,
        port: int | None = None,
        username: str | None = None,
        password: str | None = None,
        from_address: str | None = None,
    ):
        """
        Initialize email notifier.
        
        Args:
            to_address: Recipient email address
            host: SMTP server hostname (default: from EMAIL_HOST env var)
            port: SMTP port (default: from EMAIL_PORT or 587)
            username: SMTP username (default: from EMAIL_USER)
            password: SMTP password (default: from EMAIL_PASSWORD)
            from_address: Sender address (default: same as username)
        """
        self.to_address = to_address
        
        # Load from environment if not provided
        # This is a common pattern — allow config via code OR env vars
        self.host = host or os.environ.get("EMAIL_HOST", "smtp.gmail.com")
        self.port = port or int(os.environ.get("EMAIL_PORT", "587"))
        self.username = username or os.environ.get("EMAIL_USER")
        self.password = password or os.environ.get("EMAIL_PASSWORD")
        self.from_address = from_address or self.username
        
        # Validate required fields
        if not self.username or not self.password:
            raise ValueError(
                "Email credentials required. Set environment variables:\n"
                "  EMAIL_USER=your.email@gmail.com\n"
                "  EMAIL_PASSWORD=your-app-password\n"
                "For Gmail, create an App Password at:\n"
                "  https://myaccount.google.com/apppasswords"
            )
    
    def get_name(self) -> str:
        return "Email"
    
    def send_summary(
        self,
        subject: str,
        body: str,
        issues_created: list[dict],
    ) -> NotifyResult:
        """
        Send summary email.
        
        This method:
        1. Constructs an HTML email with the summary
        2. Connects to SMTP server
        3. Sends the email
        4. Returns result
        """
        try:
            # Build HTML email body
            html_body = self._build_html_body(body, issues_created)
            
            # Create email message
            # MIMEMultipart allows both plain text and HTML versions
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_address
            msg["To"] = self.to_address
            
            # Attach plain text version (for email clients that don't support HTML)
            text_part = MIMEText(body, "plain")
            msg.attach(text_part)
            
            # Attach HTML version
            html_part = MIMEText(html_body, "html")
            msg.attach(html_part)
            
            # Connect to SMTP server and send
            # 'with' statement ensures connection is closed even if error occurs
            # This is like try-finally in Dart
            with smtplib.SMTP(self.host, self.port) as server:
                # STARTTLS upgrades the connection to encrypted
                # This is required by most modern SMTP servers
                server.starttls()
                
                # Login with credentials
                server.login(self.username, self.password)
                
                # Send the email
                server.send_message(msg)
            
            return NotifyResult(success=True)
        
        except smtplib.SMTPAuthenticationError:
            return NotifyResult(
                success=False,
                error="SMTP authentication failed. Check EMAIL_USER and EMAIL_PASSWORD.",
            )
        except smtplib.SMTPException as e:
            return NotifyResult(
                success=False,
                error=f"SMTP error: {str(e)}",
            )
        except Exception as e:
            return NotifyResult(
                success=False,
                error=f"Failed to send email: {str(e)}",
            )
    
    def _build_html_body(self, body: str, issues_created: list[dict]) -> str:
        """
        Build HTML email body with nice formatting.
        
        HTML emails look much better than plain text.
        We keep it simple — basic formatting, no fancy CSS.
        """
        # Start with the main message
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <h2>🔍 Tech Debt Agent Report</h2>
            <p>{body.replace(chr(10), '<br>')}</p>
        """
        
        # Add issues table if any were created
        if issues_created:
            html += """
            <h3>📋 Issues Created</h3>
            <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse;">
                <tr style="background-color: #f2f2f2;">
                    <th>Title</th>
                    <th>Tracker</th>
                    <th>Link</th>
                </tr>
            """
            
            for issue in issues_created:
                html += f"""
                <tr>
                    <td>{issue.get('title', 'N/A')}</td>
                    <td>{issue.get('tracker', 'N/A')}</td>
                    <td><a href="{issue.get('url', '#')}">View Issue</a></td>
                </tr>
                """
            
            html += "</table>"
        else:
            html += "<p><em>No new issues created (duplicates skipped or no high-priority items).</em></p>"
        
        # Footer
        html += """
            <hr>
            <p style="color: #666; font-size: 12px;">
                Generated by tech-debt-finder agent<br>
                <a href="https://github.com/your-org/tech-debt-finder">Documentation</a>
            </p>
        </body>
        </html>
        """
        
        return html
