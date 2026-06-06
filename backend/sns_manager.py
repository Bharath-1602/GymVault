"""
GymVault - AWS SNS Manager
Handles all SNS notifications:
  - Welcome notifications for new members
  - Membership expiry alerts
  - Payment confirmations
  - Bulk expiry alert processing
All messages sent to SNS topic; topic delivers to subscribed emails.
"""

import logging
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError
from secrets_manager import secrets_client
from config import SECRET_NAME, AWS_REGION

logger = logging.getLogger(__name__)


class SNSManager:
    """AWS SNS manager for GymVault notifications."""

    def __init__(self):
        self._client = None
        self._topic_arn = None

    def _get_client(self):
        """Lazy-initialize boto3 SNS client."""
        if self._client is None:
            try:
                self._client = boto3.client("sns", region_name=AWS_REGION)
            except Exception as e:
                logger.error(f"Failed to create SNS client: {e}")
                raise
        return self._client

    def _get_topic_arn(self):
        """Get SNS topic ARN from Secrets Manager."""
        if self._topic_arn is None:
            self._topic_arn = secrets_client.get_key(SECRET_NAME, "sns_topic_arn")
        return self._topic_arn

    def _publish(self, subject, message):
        """
        Publish a message to the SNS topic (or log locally if unavailable).

        Args:
            subject: Email subject line
            message: Email body text

        Returns:
            dict: SNS publish response or mock status dict
        """
        # If SNS is not available or topic ARN not set, fall back to local logging
        if not self.is_available():
            import uuid
            msg_id = f"mock-sns-{uuid.uuid4().hex[:8]}"
            logger.info(f"[MOCK SNS SENT] MsgID: {msg_id} | Subject: {subject}")
            
            try:
                import os
                log_path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "notifications.log"
                )
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"=== {datetime.utcnow().isoformat()} ===\n")
                    f.write(f"Message ID: {msg_id}\n")
                    f.write(f"Subject: {subject}\n")
                    f.write(f"Body:\n{message}\n")
                    f.write("="*60 + "\n\n")
            except Exception as e:
                logger.warning(f"Failed to log mock notification: {e}")
                
            return {"status": "sent", "message_id": msg_id}

        try:
            client = self._get_client()
            topic_arn = self._get_topic_arn()

            if not topic_arn:
                logger.warning("SNS topic ARN not configured")
                return {"status": "not_configured", "message": "SNS topic ARN not set"}

            response = client.publish(
                TopicArn=topic_arn,
                Subject=subject[:100],  # AWS SNS subject limit
                Message=message
            )

            message_id = response.get("MessageId", "")
            logger.info(f"SNS message sent: {message_id} | Subject: {subject}")
            return {"status": "sent", "message_id": message_id}

        except ClientError as e:
            error_code = e.response["Error"]["Code"]

            if error_code == "NotFoundException":
                logger.error(f"SNS topic not found: {topic_arn}")
            elif error_code == "AuthorizationErrorException":
                logger.error("Access denied to SNS topic. Check IAM permissions.")
            elif error_code == "InvalidParameterException":
                logger.error(f"Invalid SNS parameter: {e}")
            elif error_code == "InvalidParameterValueException":
                logger.error(f"Invalid SNS parameter value: {e}")
            elif error_code == "EndpointDisabledException":
                logger.error("SNS endpoint disabled")
            elif error_code == "PlatformApplicationDisabledException":
                logger.error("SNS platform application disabled")
            else:
                logger.error(f"SNS publish error: {error_code} - {e}")

            return {"status": "error", "error": str(e)}

        except Exception as e:
            logger.error(f"Unexpected SNS error: {e}")
            return {"status": "error", "error": str(e)}

    def send_welcome_notification(self, member_name, email, plan_name, end_date):
        """
        Send welcome notification for new member.

        Args:
            member_name: Full name of the new member
            email: Member's email address
            plan_name: Name of the selected plan
            end_date: Membership end date string
        """
        gym_name = secrets_client.get_key(SECRET_NAME, "gym_name") or "GymVault Fitness Center"

        subject = "Welcome to GymVault! 🏋️"
        message = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Welcome to {gym_name}! 🏋️‍♂️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Dear {member_name},

We're thrilled to welcome you to {gym_name}! Your membership is now active.

📋 Membership Details:
   • Plan: {plan_name}
   • Member Email: {email}
   • Valid Until: {end_date}

🏋️ What's Next?
   • Visit us anytime during operating hours
   • Check in at the front desk with your Member ID
   • Explore all facilities included in your plan

💪 Tips for Getting Started:
   • Start with a warm-up routine
   • Try different equipment and classes
   • Stay hydrated and consistent

Thank you for choosing {gym_name}!
We're excited to be part of your fitness journey.

Best regards,
{gym_name} Team

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This is an automated notification from {gym_name}.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        return self._publish(subject, message)

    def send_expiry_alert(self, member_name, email, days_remaining, end_date):
        """
        Send membership expiry warning.

        Args:
            member_name: Full name of the member
            email: Member's email address
            days_remaining: Days until expiry
            end_date: Membership end date string
        """
        gym_name = secrets_client.get_key(SECRET_NAME, "gym_name") or "GymVault Fitness Center"

        subject = "GymVault Membership Expiring Soon ⚠️"
        message = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ⚠️ Membership Expiry Alert
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Dear {member_name},

Your membership at {gym_name} is expiring soon!

⏰ Expiry Details:
   • Member Email: {email}
   • Days Remaining: {days_remaining} day(s)
   • Expires On: {end_date}

🔄 Renewal Options:
   • Visit the front desk to renew your membership
   • Choose from our available plans
   • Payment accepted: Cash, Card, or UPI

Don't let your fitness journey stop!
Renew today to continue enjoying all our facilities.

Best regards,
{gym_name} Team

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This is an automated notification from {gym_name}.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        return self._publish(subject, message)

    def send_payment_confirmation(self, member_name, email, amount, receipt_number, plan_name):
        """
        Send payment confirmation notification.

        Args:
            member_name: Full name of the member
            email: Member's email address
            amount: Payment amount
            receipt_number: Generated receipt number
            plan_name: Name of the plan paid for
        """
        gym_name = secrets_client.get_key(SECRET_NAME, "gym_name") or "GymVault Fitness Center"

        subject = "Payment Confirmed - GymVault 💳"
        message = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  💳 Payment Confirmation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Dear {member_name},

Your payment has been successfully processed!

🧾 Payment Details:
   • Receipt Number: {receipt_number}
   • Member Email: {email}
   • Plan: {plan_name}
   • Amount Paid: ${amount:.2f}
   • Date: {datetime.utcnow().strftime('%B %d, %Y')}

✅ Your membership has been updated accordingly.

Please keep this receipt for your records.
If you have any questions, contact us at the front desk.

Thank you for your continued membership!

Best regards,
{gym_name} Team

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This is an automated notification from {gym_name}.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        return self._publish(subject, message)

    def send_bulk_expiry_alerts(self):
        """
        Send expiry alerts to all members expiring within the configured alert period.
        Queries MongoDB for members whose membership expires in exactly 7 days (or configured days).

        Returns:
            int: Count of alerts sent
        """
        try:
            from database import db

            alert_days = int(secrets_client.get_key(SECRET_NAME, "alert_days_before") or 7)
            target_date = datetime.utcnow() + timedelta(days=alert_days)

            # Find members expiring within the alert window
            start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)

            database = db.get_db()
            expiring_members = list(database.members.find({
                "membership_end": {
                    "$gte": start_of_day,
                    "$lte": end_of_day
                }
            }))

            alerts_sent = 0
            for member in expiring_members:
                end_date = member.get("membership_end")
                if end_date:
                    days_remaining = (end_date - datetime.utcnow()).days
                    result = self.send_expiry_alert(
                        member_name=member.get("full_name", "Member"),
                        email=member.get("email", ""),
                        days_remaining=max(0, days_remaining),
                        end_date=end_date.strftime("%B %d, %Y")
                    )
                    if result.get("status") == "sent":
                        alerts_sent += 1

            logger.info(f"Bulk expiry alerts: {alerts_sent} sent out of {len(expiring_members)} expiring members")
            return alerts_sent

        except Exception as e:
            logger.error(f"Error sending bulk expiry alerts: {e}")
            return 0

    def is_available(self):
        """Check if SNS topic is accessible."""
        try:
            client = self._get_client()
            topic_arn = self._get_topic_arn()
            if not topic_arn:
                return False
            client.get_topic_attributes(TopicArn=topic_arn)
            return True
        except Exception:
            # If Secrets Manager is not available, we are in local fallback simulation mode
            return not secrets_client.is_available()

    def refresh(self):
        """Force refresh of SNS topic ARN from Secrets Manager."""
        self._topic_arn = None


# ─── Singleton Instance ──────────────────────────────────────
sns_manager = SNSManager()
