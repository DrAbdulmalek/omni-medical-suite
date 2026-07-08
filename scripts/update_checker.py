"""
Automatic update checker and notifier.

Periodically checks the GitHub repository for new releases and logs
when an update is available. Designed to run as a background service
in the Docker deployment.
"""
import asyncio
import json
import logging
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

REPO = "DrAbdulmalek/omni-medical-suite"
RELEASES_URL = f"https://api.github.com/repos/{REPO}/releases/latest"


def _get_current_version() -> str:
    """Read current version from VERSION file or env var."""
    # Try VERSION file first
    version_file = os.path.join(os.path.dirname(__file__), "..", "VERSION")
    if os.path.isfile(version_file):
        with open(version_file) as f:
            return f.read().strip()
    # Fall back to env
    return os.getenv("VERSION", "v0.0.0")


class UpdateChecker:
    """Checks GitHub releases for newer versions."""

    def __init__(self) -> None:
        self.last_check: Optional[datetime] = None
        self.current_version: str = _get_current_version()
        self.latest_version: Optional[str] = None
        self.update_available: bool = False

    def check_for_updates(self) -> bool:
        """Check if there's a newer version available (sync).

        Uses urllib to avoid requiring aiohttp/httpx at runtime.
        Returns True if an update is available.
        """
        try:
            req = urllib.request.Request(
                RELEASES_URL,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "omni-medical-suite-update-checker",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                latest = data.get("tag_name", "v0.0.0")
                self.latest_version = latest
                self.update_available = latest != self.current_version
                self.last_check = datetime.now(timezone.utc)

                if self.update_available:
                    logger.info(
                        f"Update available: {self.current_version} -> {latest}"
                    )
                else:
                    logger.info(
                        f"Already on latest version: {self.current_version}"
                    )
                return self.update_available

        except urllib.error.HTTPError as e:
            if e.code == 404:
                logger.info("No releases found on GitHub yet.")
            else:
                logger.error(f"GitHub API error (HTTP {e.code}): {e}")
        except Exception as e:
            logger.error(f"Update check failed: {e}")

        return False

    async def check_for_updates_async(self) -> bool:
        """Async wrapper for check_for_updates."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.check_for_updates)

    async def start_periodic_check(self, interval: int = 3600) -> None:
        """Start periodic update checking (default: every hour).

        Args:
            interval: Seconds between checks.
        """
        logger.info(
            f"Starting periodic update check (interval={interval}s, "
            f"current={self.current_version})"
        )
        while True:
            await self.check_for_updates_async()
            await asyncio.sleep(interval)


update_checker = UpdateChecker()


if __name__ == "__main__":
    # One-shot check when run directly
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    available = update_checker.check_for_updates()
    if available:
        print(f"UPDATE AVAILABLE: {update_checker.current_version} -> {update_checker.latest_version}")
    else:
        print(f"No update available (current: {update_checker.current_version})")