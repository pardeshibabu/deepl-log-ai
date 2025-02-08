import requests
import os
from typing import Optional

class SlackNotifier:
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv('SLACK_WEBHOOK_URL')
        if not self.webhook_url:
            raise ValueError("Slack webhook URL is required")

    def send_notification(self, message: str) -> bool:
        try:
            response = requests.post(
                self.webhook_url,
                json={"text": message}
            )
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Failed to send Slack notification: {str(e)}")
            return False