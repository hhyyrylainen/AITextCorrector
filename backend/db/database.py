import asyncio
import os
from asyncio import Lock
from collections.abc import Awaitable
from pathlib import Path
from typing import Dict, Any
import platform

import aiosqlite

from .config import ConfigModel, default_config

DATABASE_VERSION = 1


def get_db_path() -> Path:
    """
    Determine the database path based on the platform (Linux, macOS, Windows).
    Returns:
        Path: The folder where the database should be stored.
    """
    system = platform.system()

    if system == "Linux":
        # Use XDG Base Directory Standard on Linux
        xdg_data_home = os.getenv("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
        db_folder = Path(xdg_data_home) / "AITextCorrector"
    elif system == "Darwin":  # macOS
        # Use ~/Library/Application Support/ on macOS
        db_folder = Path.home() / "Library" / "Application Support" / "AITextCorrector"
    elif system == "Windows":
        # Use %APPDATA% on Windows (default AppData\Roaming location)
        appdata = os.getenv("APPDATA", Path.home() / "AppData" / "Roaming")
        db_folder = Path(appdata) / "AITextCorrector"
    else:
        # Fallback for unknown platforms: use a local directory
        db_folder = Path.home() / ".AITextCorrector"

    # Ensure the folder exists
    db_folder.mkdir(parents=True, exist_ok=True)
    return db_folder


# -----------------
# Database Singleton Class
# -----------------
class Database:
    _instance = None  # Singleton instance
    _lock: Lock = Lock()  # Thread-safe lock for async operations

    def __new__(cls, *args, **kwargs):
        """Ensure only one instance of the Database class exists."""
        if not cls._instance:
            cls._instance = super(Database, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        self.db_folder = get_db_path()
        self.db_file = self.db_folder / "database.sqlite"

        # Ensure the folder exists
        self.db_folder.mkdir(parents=True, exist_ok=True)

        # Connection pool (aiosqlite)
        self._connection = None

        # Run the async initialization function
        # We are already in an async context so we do it like this and hopefully this is initialized before any API
        # calls are allowed through
        asyncio.create_task(self.initialize())

    async def initialize(self):
        """Initialize the database and ensure tables exist."""
        async with self._lock:
            # TODO: more entries in the pool than just one...
            self._connection = await aiosqlite.connect(self.db_file)
            db = self._connection
            await db.execute("PRAGMA journal_mode=WAL;")  # Enable Write-Ahead Logging (WAL)
            db.row_factory = aiosqlite.Row  # Return dictionary-like rows

            await db.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    id INTEGER PRIMARY KEY,
                    version INTEGER NOT NULL,
                    selectedModel TEXT NOT NULL,
                    correctionReRuns INTEGER NOT NULL DEFAULT 0,
                    autoSummaries BOOLEAN NOT NULL DEFAULT 0
                );
            """)
            await db.commit()

            # Create config and apply migrations if needed
            async with db.execute("SELECT * FROM config WHERE id = 1") as cursor:
                existing_config = await cursor.fetchone()

            if existing_config is None:
                await db.execute("""
                    INSERT INTO config (id, version, selectedModel, correctionReRuns, autoSummaries)
                    VALUES (1, ?, ?, ?, ?)
                """, (
                    DATABASE_VERSION,
                    default_config.selected_model,
                    default_config.correction_re_runs,
                    default_config.auto_summaries
                ))

                print("Initializing new database...")
            else:
                # Ensure database is migrated to the latest version
                if existing_config["version"] < DATABASE_VERSION:
                    # TODO: implement migrations
                    raise Exception(
                        f"Database migration required (current version: {existing_config['version']}, expected version: {DATABASE_VERSION})")

                    await db.execute("""
                        UPDATE config
                        SET version = ?
                    """, (DATABASE_VERSION,))

            await db.commit()
            print("Database loaded")

    async def get_config(self, user: str = "default") -> ConfigModel:
        """
        Fetch configuration for the given user asynchronously.

        Args:
            user (str): User identifier, defaults to "default".

        Returns:
            ConfigModel: Configuration details.
        """
        async with self._lock:  # Ensure thread safety
            db = self._connection
            async with db.execute("SELECT * FROM config WHERE id = 1") as cursor:
                row = await cursor.fetchone()

            if row:
                # If configuration exists, return it
                return ConfigModel(selected_model=row["selectedModel"],
                                   correction_re_runs=row["correctionReRuns"],
                                   auto_summaries=bool(row["autoSummaries"]))
            else:
                # Return default values if no configuration exists
                print("WARNING: no configuration found, using default values")
                return default_config

    async def update_config(self, new_config: ConfigModel, user: str = "default"):
        """
        Update configuration for the given user asynchronously.

        Args:
            new_config (ConfigModel): New configuration to save.
            user (str): User identifier, defaults to "default".
        """
        async with self._lock:  # Ensure thread safety
            db = self._connection

            # Update existing configuration
            await db.execute("""
                UPDATE config
                SET selectedModel = ?, correctionReRuns = ?, autoSummaries = ?
                WHERE id = ?
            """, (
                new_config.selectedModel,
                new_config.correctionReRuns,
                new_config.autoSummaries,
                1
            ))

            await db.commit()  # Save the changes


# Singleton instance of the database
database = Database()
