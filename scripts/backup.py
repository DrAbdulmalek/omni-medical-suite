"""
Automated backup system for databases and critical files.

Supports PostgreSQL dumps, Redis RDB snapshots, and file-level backups
with automatic cleanup of old backups beyond the retention period.
"""
import asyncio
import logging
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "/app/backups"))
DATABASE_BACKUP_DIR = BACKUP_DIR / "database"
REDIS_BACKUP_DIR = BACKUP_DIR / "redis"
FILES_BACKUP_DIR = BACKUP_DIR / "files"

# Directories considered critical for file-level backup
CRITICAL_DIRS = ["app", "packages", "src", "config"]


async def backup_database() -> bool:
    """Backup PostgreSQL database using pg_dump.

    Requires pg_dump on PATH and DB_* environment variables.
    """
    try:
        DATABASE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = DATABASE_BACKUP_DIR / f"omni_medical_{timestamp}.sql"

        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")
        user = os.getenv("DB_USER", "postgres")
        dbname = os.getenv("DB_NAME", "omni_medical")

        cmd = [
            "pg_dump",
            "-h", host,
            "-p", port,
            "-U", user,
            "-d", dbname,
            "-f", str(backup_file),
        ]

        env = os.environ.copy()
        env["PGPASSWORD"] = os.getenv("DB_PASSWORD", "")

        result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=300)

        if result.returncode == 0:
            logger.info(f"Database backup created: {backup_file}")
            return True
        else:
            logger.error(f"pg_dump failed (rc={result.returncode}): {result.stderr}")
            return False

    except FileNotFoundError:
        logger.warning("pg_dump not found — skipping database backup")
        return False
    except subprocess.TimeoutExpired:
        logger.error("Database backup timed out (300s)")
        return False
    except Exception as e:
        logger.error(f"Database backup failed: {e}")
        return False


async def backup_redis() -> bool:
    """Trigger Redis BGSAVE and copy the RDB dump file.

    Requires redis-cli on PATH and REDIS_URL or individual REDIS_* vars.
    """
    try:
        REDIS_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        # Trigger BGSAVE via redis-cli
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = os.getenv("REDIS_PORT", "6379")

        # Try to trigger BGSAVE
        try:
            subprocess.run(
                ["redis-cli", "-h", redis_host, "-p", redis_port, "BGSAVE"],
                capture_output=True, text=True, timeout=10,
            )
            # Wait for BGSAVE to complete
            await asyncio.sleep(2)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("redis-cli not available or timed out — attempting direct copy")

        # Find and copy the dump file
        redis_data_dir = os.getenv("REDIS_DATA_DIR", "/data")
        dump_src = Path(redis_data_dir) / "dump.rdb"

        if dump_src.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = REDIS_BACKUP_DIR / f"redis_{timestamp}.rdb"
            shutil.copy2(str(dump_src), str(backup_file))
            logger.info(f"Redis backup created: {backup_file}")
            return True
        else:
            logger.warning(f"Redis dump file not found at {dump_src}")
            return False

    except Exception as e:
        logger.error(f"Redis backup failed: {e}")
        return False


async def backup_files() -> bool:
    """Backup critical source directories."""
    try:
        FILES_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = FILES_BACKUP_DIR / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)

        project_root = Path(__file__).resolve().parent.parent
        backed_up = 0

        for dir_name in CRITICAL_DIRS:
            src = project_root / dir_name
            if src.exists() and src.is_dir():
                dst = backup_dir / dir_name
                shutil.copytree(str(src), str(dst))
                backed_up += 1

        logger.info(f"Files backup created: {backup_dir} ({backed_up} directories)")
        return backed_up > 0

    except Exception as e:
        logger.error(f"Files backup failed: {e}")
        return False


async def cleanup_old_backups(days: int = 30) -> int:
    """Delete backup files older than N days.

    Args:
        days: Retention period in days (default 30).

    Returns:
        Number of files deleted.
    """
    deleted = 0
    try:
        cutoff = datetime.now() - timedelta(days=days)

        for backup_path in BACKUP_DIR.rglob("*"):
            if backup_path.is_file():
                mtime = datetime.fromtimestamp(backup_path.stat().st_mtime, tz=timezone.utc)
                if mtime < cutoff:
                    backup_path.unlink()
                    deleted += 1
                    logger.info(f"Deleted old backup: {backup_path}")

    except Exception as e:
        logger.error(f"Backup cleanup failed: {e}")

    return deleted


async def full_backup() -> Dict[str, bool]:
    """Perform full backup of all components and cleanup old files."""
    results = {
        "database": await backup_database(),
        "redis": await backup_redis(),
        "files": await backup_files(),
    }

    deleted = await cleanup_old_backups()
    results["cleanup"] = True
    logger.info(f"Full backup complete. Cleaned {deleted} old files.")
    return results


async def start_periodic_backup(interval: int = 86400) -> None:
    """Start periodic backup (default: daily).

    Args:
        interval: Seconds between backups (default 86400 = 24 hours).
    """
    logger.info(f"Starting periodic backup (interval={interval}s)")
    while True:
        await full_backup()
        await asyncio.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    results = asyncio.run(full_backup())
    print(f"Backup results: {results}")