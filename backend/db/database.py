import asyncio
import os
import platform
import time
from asyncio import Lock
from pathlib import Path

import aiosqlite

from .config import ConfigModel, default_config
from .project import Project

DATABASE_VERSION = 3


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

    _config_cache = None  # Cached configuration data
    _config_cache_timestamp = None  # Timestamp of when the cache was last updated
    _CACHE_TTL = 5  # Time to live for cache (in seconds)

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

            await Database._create_default_tables_if_missing(db)

            # Create config and apply migrations if needed
            async with db.execute("SELECT * FROM config WHERE id = 1") as cursor:
                existing_config = await cursor.fetchone()

            if existing_config is None:
                await db.execute("""
                    INSERT INTO config (id, version, selectedModel, correctionReRuns, autoSummaries)
                    VALUES (1, ?, ?, ?, ?)
                """, (
                    DATABASE_VERSION,
                    default_config.selectedModel,
                    default_config.correctionReRuns,
                    default_config.autoSummaries
                ))

                print("Initializing new database...")
            else:
                config = dict(existing_config)
                if existing_config["version"] > DATABASE_VERSION:
                    raise Exception(
                        f"Database version is newer than expected (current version: {config['version']}, "
                        f"expected version: {DATABASE_VERSION}). Please update the application to the latest version!")

                await db.execute("BEGIN TRANSACTION;")

                config["version"] = int(config["version"])

                # Ensure database is migrated to the latest version
                while config["version"] < DATABASE_VERSION:
                    # TODO: implement migrations
                    print(
                        f"Database migration required (current version: {config['version']}, expected version: {DATABASE_VERSION})")

                    await self._migrate_database(db, config)

            await db.commit()
            print("Database loaded")

    async def create_project(self, project: Project) -> int:
        """
        Writes a new project (along with its chapters and paragraphs) into the database.
        The provided project data does not include valid IDs. This method inserts the
        project into the Projects table, the chapters into the Chapters table, and the paragraphs
        into the Paragraphs table. It returns the newly created project's ID.
        """
        connection = self._connection
        async with self._lock:
            try:
                # Begin a transaction
                await connection.execute("BEGIN")

                # Insert the Project data and retrieve the new project ID.
                project_cursor = await connection.execute(
                    """
                    INSERT INTO Projects (name, stylePrompt, correctionStrengthLevel)
                    VALUES (?, ?, ?)
                    """,
                    (project.name, project.stylePrompt, project.correctionStrengthLevel)
                )
                project_id = project_cursor.lastrowid

                # Insert each Chapter and its Paragraphs.
                for chapter in project.chapters:
                    chapter_cursor = await connection.execute(
                        """
                        INSERT INTO Chapters (projectId, chapterIndex, name, summary)
                        VALUES (?, ?, ?, ?)
                        """,
                        (project_id, chapter.chapterIndex, chapter.name, chapter.summary)
                    )
                    chapter_id = chapter_cursor.lastrowid

                    for paragraph in chapter.paragraphs:
                        await connection.execute(
                            """
                            INSERT INTO Paragraphs (
                                partOfChapter, paragraphIndex, originalText,
                                correctedText, manuallyCorrectedText, leadingSpace
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                chapter_id,
                                paragraph.index,
                                paragraph.originalText,
                                paragraph.correctedText,
                                paragraph.manuallyCorrectedText,
                                paragraph.leadingSpace,
                            )
                        )

                # Commit the transaction if all inserts succeed.
                await connection.commit()

            except aiosqlite.IntegrityError as e:
                # Rollback in case a unique constraint is violated (e.g., duplicate project name)
                await connection.rollback()
                raise ValueError("A project with the same name already exists.") from e
            except Exception as e:
                await connection.rollback()
                raise RuntimeError("Failed to write project to the database.") from e

        return project_id

    async def get_config(self) -> ConfigModel:
        """
        Fetch configuration asynchronously, using a cached copy if valid.

        Returns:
            ConfigModel: Configuration details.
        """
        async with self._lock:  # Ensure thread safety
            current_time = time.time()

            # Check if cache is valid
            if (
                    self._config_cache is not None and
                    self._config_cache_timestamp is not None and
                    (current_time - self._config_cache_timestamp) < self._CACHE_TTL
            ):
                # Return the cached copy if it's still valid
                return self._config_cache

            db = self._connection
            async with db.execute("SELECT * FROM config WHERE id = 1") as cursor:
                row = await cursor.fetchone()

            if row:
                config = ConfigModel(selectedModel=row["selectedModel"],
                                     correctionReRuns=row["correctionReRuns"],
                                     autoSummaries=bool(row["autoSummaries"]),
                                     styleExcerptLength=row["styleExcerptLength"],
                                     simultaneousCorrectionSize=row["simultaneousCorrectionSize"],
                                     unusedAIUnloadDelay=row["unusedAIUnloadDelay"])
            else:
                # Return default values if no configuration exists
                print("WARNING: no configuration found, using default values")
                config = default_config

            # Update the cache with new data and current timestamp
            self._config_cache = config
            self._config_cache_timestamp = current_time

            return config

    async def update_config(self, new_config: ConfigModel):
        """
        Update configuration for the given user asynchronously.

        Args:
            new_config (ConfigModel): New configuration to save.
        """
        async with self._lock:  # Ensure thread safety
            db = self._connection

            # Update existing configuration
            await db.execute("""
                UPDATE config
                SET selectedModel = ?, correctionReRuns = ?, autoSummaries = ?, styleExcerptLength = ?, 
                simultaneousCorrectionSize = ?, unusedAIUnloadDelay = ?
                WHERE id = ?
            """, (
                new_config.selectedModel,
                new_config.correctionReRuns,
                new_config.autoSummaries,
                new_config.styleExcerptLength,
                new_config.simultaneousCorrectionSize,
                new_config.unusedAIUnloadDelay,
                1
            ))

            await db.commit()  # Save the changes

            # Immediately make new config available through the cache
            self._config_cache = new_config

    async def _migrate_database(self, db, existing_config):
        if existing_config["version"] == 1:
            await db.execute(
                f"ALTER TABLE config ADD COLUMN styleExcerptLength INTEGER NOT NULL DEFAULT {default_config.styleExcerptLength}")
            await db.execute(
                f"ALTER TABLE config ADD COLUMN simultaneousCorrectionSize INTEGER NOT NULL DEFAULT {default_config.simultaneousCorrectionSize}")
            await db.execute(
                f"ALTER TABLE config ADD COLUMN unusedAIUnloadDelay INTEGER NOT NULL DEFAULT {default_config.unusedAIUnloadDelay}")

            await self._on_version_migrated(db, existing_config, 2)

        if existing_config["version"] == 2:
            await db.execute("""
                CREATE UNIQUE INDEX idx_unique_project_name ON Projects (name);
            """)

            await self._on_version_migrated(db, existing_config, 3)
        else:
            raise Exception(f"Unknown database version: {existing_config['version']}")

    async def _on_version_migrated(self, db, existing_config, new_version):
        existing_config["version"] = new_version
        print(f"Database migrated to version {new_version}")
        await db.execute("UPDATE config SET version = ? WHERE id = 1", (new_version,))

    @staticmethod
    async def _create_default_tables_if_missing(db):
        await db.execute("BEGIN TRANSACTION;")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS config (
                id INTEGER PRIMARY KEY,
                version INTEGER NOT NULL,
                selectedModel TEXT NOT NULL,
                correctionReRuns INTEGER NOT NULL DEFAULT 0,
                autoSummaries BOOLEAN NOT NULL DEFAULT 0,
                styleExcerptLength INTEGER NOT NULL DEFAULT 1000,
                simultaneousCorrectionSize INTEGER NOT NULL DEFAULT 200,
                unusedAIUnloadDelay INTEGER NOT NULL DEFAULT 120
            );
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    stylePrompt TEXT NOT NULL,
                    correctionStrengthLevel INTEGER NOT NULL
                );
        """)

        await db.execute("""
                CREATE TABLE IF NOT EXISTS chapters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    projectId INTEGER NOT NULL,
                    chapterIndex INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    summary TEXT,
                    FOREIGN KEY (projectId) REFERENCES Projects (id) ON DELETE CASCADE
                );
        """)

        await db.execute("""
                CREATE TABLE IF NOT EXISTS paragraphs (
                    chapterId INTEGER NOT NULL,
                    paragraphIndex INTEGER NOT NULL,
                    originalText TEXT NOT NULL,
                    correctedText TEXT,
                    manuallyCorrectedText TEXT,
                    leadingSpace INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (chapterId) REFERENCES Chapters (id) ON DELETE CASCADE,
                    PRIMARY KEY (chapterId, paragraphIndex)
                );
        """)

        await db.commit()

# Singleton instance of the database
database = Database()
