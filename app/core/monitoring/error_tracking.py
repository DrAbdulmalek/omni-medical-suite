"""
OmniMedical Suite — Error Tracking (Sentry Integration).

Initializes Sentry SDK with appropriate integrations for the runtime environment.
Only activates when SENTRY_DSN environment variable is set, so it has zero impact
on local development or environments without Sentry configured.

Usage:
    from app.core.monitoring.error_tracking import init_sentry, capture_error
    init_sentry(dsn="https://xxx@sentry.io/xxx", environment="production")
    try:
        ...
    except Exception as e:
        capture_error(e, context={"user_id": 123})
"""

import os
from typing import Any, Dict, Optional


def init_sentry(
    dsn: Optional[str] = None,
    environment: str = "production",
    traces_sample_rate: float = 0.2,
    send_default_pii: bool = False,
) -> bool:
    """
    Initialize Sentry error tracking.

    Args:
        dsn: Sentry DSN. Falls back to SENTRY_DSN env var.
        environment: Environment label (production, staging, development).
        traces_sample_rate: Fraction of transactions to sample for performance.
        send_default_pii: Whether to send personally identifiable info.

    Returns:
        True if Sentry was initialized, False if skipped.
    """
    dsn = dsn or os.getenv("SENTRY_DSN", "")
    if not dsn:
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration

        # Only send ERROR and above from logging
        logging_integration = LoggingIntegration(
            level=logging.ERROR,  # Capture errors
            event_level=logging.ERROR,  # Send errors as events
        )

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            integrations=[logging_integration],
            traces_sample_rate=traces_sample_rate,
            send_default_pii=send_default_pii,
            # Group similar errors together
            max_breadcrumbs=50,
            attach_stacktrace=True,
        )
        return True
    except ImportError:
        return False
    except Exception:
        return False


def capture_error(exc: Exception, context: Optional[Dict[str, Any]] = None):
    """
    Capture an exception with optional context.

    If Sentry is not initialized, this is a no-op.

    Args:
        exc: The exception to capture.
        context: Additional context tags (e.g., user_id, engine, image_size).
    """
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            if context:
                for key, value in context.items():
                    scope.set_tag(key, value)
            sentry_sdk.capture_exception(exc)
    except Exception:
        pass  # Never let error tracking crash the app