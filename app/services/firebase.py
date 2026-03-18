"""
Firebase Admin SDK — push notification service.

Supports both single-device and broadcast (multicast) notifications.
Credentials are loaded from a JSON file path or an inline JSON string
(useful for Railway environment variables).
"""

import json
import logging
import os
from typing import List

logger = logging.getLogger(__name__)

_app = None


def _get_firebase_app():
    global _app
    if _app is not None:
        return _app

    try:
        import firebase_admin
        from firebase_admin import credentials

        from app.config import settings

        if settings.firebase_credentials_json:
            # Load from inline JSON string (Railway env var approach)
            cred_dict = json.loads(settings.firebase_credentials_json)
            cred = credentials.Certificate(cred_dict)
        elif os.path.exists(settings.firebase_credentials_path):
            cred = credentials.Certificate(settings.firebase_credentials_path)
        else:
            logger.warning(
                "Firebase credentials not configured. Push notifications disabled."
            )
            return None

        app_options = {}
        if settings.firebase_storage_bucket:
            app_options["storageBucket"] = settings.firebase_storage_bucket

        _app = firebase_admin.initialize_app(cred, options=app_options)
        logger.info("Firebase Admin SDK initialized.")
        return _app

    except Exception as e:
        logger.error("Firebase initialization error: %s", e)
        return None


async def send_notification(token: str, title: str, body: str, data: dict = None) -> bool:
    """Send a push notification to a single device token."""
    app = _get_firebase_app()
    if not app:
        return False

    try:
        from firebase_admin import messaging

        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            token=token,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    sound="default",
                    channel_id="disaster_alerts",
                ),
            ),
        )
        response = messaging.send(message)
        logger.debug("Firebase message sent: %s", response)
        return True
    except Exception as e:
        logger.warning("Firebase send error for token %s: %s", token[:12], e)
        return False


async def broadcast_notification(tokens: List[str], title: str, body: str, data: dict = None) -> int:
    """
    Send a push notification to multiple device tokens using FCM multicast.
    Returns the number of successfully sent messages.
    """
    if not tokens:
        return 0

    app = _get_firebase_app()
    if not app:
        return 0

    try:
        from firebase_admin import messaging

        # FCM multicast supports up to 500 tokens per request
        success_count = 0
        batch_size = 500
        for i in range(0, len(tokens), batch_size):
            batch = tokens[i : i + batch_size]
            multicast_msg = messaging.MulticastMessage(
                notification=messaging.Notification(title=title, body=body),
                data=data or {},
                tokens=batch,
                android=messaging.AndroidConfig(
                    priority="high",
                    notification=messaging.AndroidNotification(
                        sound="default",
                        channel_id="disaster_alerts",
                    ),
                ),
            )
            response = messaging.send_multicast(multicast_msg)
            success_count += response.success_count
            if response.failure_count:
                logger.warning(
                    "FCM multicast: %d failed out of %d",
                    response.failure_count, len(batch),
                )

        logger.info("FCM broadcast: %d/%d successful", success_count, len(tokens))
        return success_count

    except Exception as e:
        logger.error("FCM broadcast error: %s", e)
        return 0
