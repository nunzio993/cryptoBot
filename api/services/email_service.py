"""
Email Service - Send emails via SMTP (Brevo)
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via SMTP"""
    
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp-relay.brevo.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.from_email = os.getenv("SMTP_FROM", "noreply@orderdash.cloud")
        self.frontend_url = os.getenv("FRONTEND_URL", "https://orderdash.cloud")
    
    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        """
        Send a plain text email.
        
        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.smtp_user or not self.smtp_password:
            logger.error("SMTP credentials not configured")
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
    def send_password_reset_email(self, to_email: str, reset_token: str, username: str) -> bool:
        """
        Send password reset email with reset link.
        
        Args:
            to_email: Recipient email address
            reset_token: The password reset token
            username: Username for personalization
            
        Returns:
            True if email sent successfully
        """
        reset_url = f"{self.frontend_url}/reset-password?token={reset_token}"
        
        subject = "Password Reset Request - CryptoBot"
        
        body = f"""Hello {username},

You requested a password reset for your CryptoBot account.

Click the link below to reset your password:
{reset_url}

This link will expire in 1 hour.

If you did not request this password reset, please ignore this email.
Your password will remain unchanged.

---
CryptoBot Team
"""
        
        return self.send_email(to_email, subject, body)


# Singleton instance
email_service = EmailService()
