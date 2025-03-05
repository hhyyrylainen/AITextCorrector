import asyncio
import os
import platform
import time
from asyncio import Lock
from pathlib import Path
from typing import List

import aiosqlite
from aiosqlite import Connection

from .config import ConfigModel, default_config
from .project import Project, Chapter, Paragraph, CorrectionStatus

DATABASE_VERSION = 4


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

    # TODO: figure out why it seems like this method runs twice from the singleton instance, does the rvunicorn run
    # multiple instances of the app?
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
                    INSERT INTO projects (name, stylePrompt, correctionStrengthLevel)
                    VALUES (?, ?, ?)
                    """,
                    (project.name, project.stylePrompt, project.correctionStrengthLevel)
                )
                project_id = project_cursor.lastrowid

                # Insert each Chapter and its Paragraphs.
                for chapter in project.chapters:
                    await self._insert_chapter(connection, chapter, project_id)

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

    async def update_project_chapters(self, project: Project, new_chapters: List[Chapter]):
        """
        Adds new chapters to an existing project. If a chapter already exists, it is not added again, but paragraphs
        are updated. Note that removed paragraphs from the new text are not deleted from the database.

        :param project: project to update (doesn't need to have chapters loaded)
        :param new_chapters: new chapters to add to the project
        :return:
        """
        if len(new_chapters) == 0:
            return

        connection = self._connection
        async with self._lock:
            try:
                await connection.execute("BEGIN")

                for chapter in new_chapters:
                    chapter_id = await self.get_chapter_id_by_name(chapter.name, project.id)

                    if chapter_id is None:
                        # Inserting an entirely new chapter
                        print(f"Inserting new chapter to project {project.id} with name: {chapter.name}")
                        await self._insert_chapter(connection, chapter, project.id)
                    else:
                        # Updating a chapter. Check if the paragraphs are fine
                        database_chapter = await self.get_chapter(chapter_id, include_paragraphs=True)

                        for i, paragraph in enumerate(chapter.paragraphs):

                            paragraph_index = i + 1

                            if paragraph_index > len(database_chapter.paragraphs):
                                # Adding new paragraphs
                                print(
                                    f"Adding new paragraph {paragraph_index} to chapter {chapter.name} in project {project.id}")
                                await connection.execute(
                                    """
                                    INSERT INTO paragraphs (
                                        chapterId, paragraphIndex, originalText,
                                        correctedText, manuallyCorrectedText, leadingSpace, correctionStatus,
                                    )
                                    VALUES (?, ?, ?, ?, ?, ?)
                                    """,
                                    (
                                        chapter_id,
                                        paragraph_index,
                                        paragraph.originalText,
                                        paragraph.correctedText,
                                        paragraph.manuallyCorrectedText,
                                        paragraph.leadingSpace,
                                        paragraph.correctionStatus,
                                    )
                                )
                            else:
                                # See if text is right and update it if not
                                database_paragraph = database_chapter.paragraphs[i]

                                if database_paragraph.originalText != paragraph.originalText:
                                    print(
                                        f"New text for paragraph {paragraph_index} in chapter {chapter.name} "
                                        f"in project {project.id}, resetting correction status")
                                    result = await connection.execute(
                                        """
                                        UPDATE paragraphs
                                        SET originalText = ?, correctedText = ?, manuallyCorrectedText = ?, 
                                            correctionStatus = ?, leadingSpace = ?
                                        WHERE chapterId = ? AND paragraphIndex = ?
                                        """,
                                        (paragraph.originalText,
                                         paragraph.correctedText, paragraph.manuallyCorrectedText,
                                         paragraph.correctionStatus, paragraph.leadingSpace,
                                         database_paragraph.partOfChapter, database_paragraph.index)
                                    )
                                    if result.rowcount == 0:
                                        raise ValueError(
                                            f"Failed to upgrade paragraph "
                                            f"{database_paragraph.partOfChapter}-{database_paragraph.index}")
                                elif database_paragraph.leadingSpace != paragraph.leadingSpace:
                                    # Update just this property
                                    result = await connection.execute(
                                        """
                                        UPDATE paragraphs
                                        SET leadingSpace = ?
                                        WHERE chapterId = ? AND paragraphIndex = ?
                                        """,
                                        (paragraph.leadingSpace, database_paragraph.partOfChapter,
                                         database_paragraph.index)
                                    )
                                    if result.rowcount == 0:
                                        raise ValueError(
                                            f"Failed to upgrade paragraph "
                                            f"{database_paragraph.partOfChapter}-{database_paragraph.index}")

                # Commit the transaction if all inserts succeed.
                await connection.commit()

            except Exception as e:
                await connection.rollback()
                raise RuntimeError("Failed to write project text updates to the database.") from e

    async def get_project(self, project_id: int, include_chapters=True) -> Project | None:
        """
        Fetches the primary data for a project, along with all associated chapters,
        but excludes the paragraphs to optimize data retrieval. Uses async operations.

        Args:
            project_id (int): The ID of the project to retrieve.

        Returns:
            Project | None: The project data, or None if no project is found.
        """
        connection = self._connection

        try:
            # Fetch the primary project data
            async with connection.execute(
                    """
                SELECT id, name, correctionStrengthLevel, stylePrompt
                FROM projects
                WHERE id = ?
                """,
                    (project_id,),
            ) as project_cursor:
                project_data = await project_cursor.fetchone()

            # If no project data is found, return None
            if not project_data:
                return None

            if include_chapters:
                # Fetch all associated chapters for the project
                async with connection.execute(
                        """
                    SELECT id, name, chapterIndex, summary
                    FROM chapters
                    WHERE projectId = ?
                    ORDER BY chapterIndex ASC
                    """,
                        (project_id,),
                ) as chapters_cursor:
                    chapters = [
                        Chapter(id=row[0], projectId=project_id, name=row[1], chapterIndex=row[2], summary=row[3],
                                paragraphs=[]) async for row in chapters_cursor
                    ]
            else:
                chapters = []

            project = Project(id=project_data[0], name=project_data[1], correctionStrengthLevel=project_data[2],
                              stylePrompt=project_data[3], chapters=chapters)

            return project

        except Exception as e:
            # Handle and log database errors (optional logging)
            print(f"Error fetching project data: {e}")
            return None

    async def get_project_by_chapter(self, chapter_id: int) -> Project | None:
        """
        Fetches the primary data for a project, based on a chapter it contains.

        Args:
            chapter_id (int): The ID of the chapter whose project to retrieve.

        Returns:
            Project | None: The project data, or None if no project is found.
        """
        connection = self._connection

        try:
            async with connection.execute(
                    """
                SELECT id, name, correctionStrengthLevel, stylePrompt
                FROM projects
                WHERE id = (SELECT projectId FROM chapters WHERE id = ?)
                """,
                    (chapter_id,),
            ) as project_cursor:
                project_data = await project_cursor.fetchone()

            # If no project data is found, return None
            if not project_data:
                return None

            project = Project(id=project_data[0], name=project_data[1], correctionStrengthLevel=project_data[2],
                              stylePrompt=project_data[3], chapters=[])

            return project

        except Exception as e:
            # Handle and log database errors (optional logging)
            print(f"Error fetching project by chapter: {e}")
            return None

    async def get_projects(self) -> List[Project]:
        """
        Fetches all the projects from the database. This method retrieves only the project-level data
        and excludes any associated chapters or paragraphs. Does not fetch style information.
    
        Returns:
            List[Project]: A list of Project objects, or an empty list if no projects are found.
        """
        connection = self._connection

        try:
            # Fetch all projects
            async with connection.execute(
                    """
                    SELECT id, name, correctionStrengthLevel
                    FROM projects
                    ORDER BY name ASC
                    """
            ) as projects_cursor:
                projects = [
                    Project(
                        id=row["id"],
                        name=row["name"],
                        correctionStrengthLevel=row["correctionStrengthLevel"],
                        stylePrompt="not fetched",
                        chapters=[]
                    ) async for row in projects_cursor
                ]

            return projects

        except Exception as e:
            # Handle and log database errors (optional logging)
            print(f"Error fetching projects: {e}")
            return []

    async def get_chapter(self, chapter_id: int, include_paragraphs: bool = False) -> Chapter | None:
        """
        Fetches a chapter by ID. Optionally fetches all associated paragraphs.
    
        Args:
            chapter_id (int): The ID of the chapter to retrieve.
            include_paragraphs (bool): If True, retrieves associated paragraphs.
    
        Returns:
            Chapter | None: The chapter data, or None if not found.
        """
        connection = self._connection

        try:
            # Fetch the main chapter data
            async with connection.execute(
                    """
                    SELECT id, name, chapterIndex, summary, projectId
                    FROM chapters
                    WHERE id = ?
                    """,
                    (chapter_id,),
            ) as chapter_cursor:
                chapter_data = await chapter_cursor.fetchone()

            # If no chapter is found, return None
            if not chapter_data:
                return None

            # Create the Chapter object
            chapter = Chapter(
                id=chapter_data["id"],
                name=chapter_data["name"],
                chapterIndex=chapter_data["chapterIndex"],
                summary=chapter_data["summary"],
                projectId=chapter_data["projectId"],
                paragraphs=[],
            )

            # If requested, fetch all associated paragraphs
            if include_paragraphs:
                async with connection.execute(
                        """
                        SELECT paragraphIndex, originalText, correctedText, manuallyCorrectedText, leadingSpace, correctionStatus
                        FROM paragraphs
                        WHERE chapterId = ?
                        ORDER BY paragraphIndex ASC
                        """,
                        (chapter_id,),
                ) as paragraphs_cursor:
                    chapter.paragraphs = [
                        Paragraph(
                            index=row["paragraphIndex"],
                            originalText=row["originalText"],
                            correctedText=row["correctedText"],
                            manuallyCorrectedText=row["manuallyCorrectedText"],
                            leadingSpace=row["leadingSpace"],
                            correctionStatus=row["correctionStatus"],
                            partOfChapter=chapter_id,
                        ) async for row in paragraphs_cursor
                    ]

            return chapter

        except Exception as e:
            # Handle and log errors
            print(f"Error fetching chapter data: {e}")
            return None

    async def get_chapter_id_by_name(self, name: str, project_id: int) -> int | None:
        """
        Fetches a chapter ID by name.

        Args:
            name (str): The name of the chapter to retrieve.
            project_id (int): The ID of the project to search in.

        Returns:
            int | None: The chapter id, or None if not found.
        """
        connection = self._connection

        try:
            # Fetch the main chapter data
            async with connection.execute(
                    """
                    SELECT id
                    FROM chapters
                    WHERE projectId = ? AND name = ?
                    """,
                    (project_id, name),
            ) as chapter_cursor:
                chapter_data = await chapter_cursor.fetchone()

            # If no chapter is found, return None
            if not chapter_data:
                return None

            return int(chapter_data["id"])

        except Exception as e:
            # Handle and log errors
            print(f"Error looking for chapter by name: {e}")
            return None

    async def get_chapter_paragraph_text(self, chapter_id: int) -> List[Paragraph]:
        """
        Fetches all paragraphs associated with a given chapter ID. Only returns the primary text.
        Uses async operations for retrieving data from the database.
    
        Args:
            chapter_id (int): The ID of the chapter to retrieve paragraphs for.
    
        Returns:
            List[Paragraph]: A list of Paragraph objects, or an empty list if no paragraphs are found.
        """
        connection = self._connection

        try:
            # Fetch paragraphs for the specified chapter
            async with connection.execute(
                    """
                    SELECT paragraphIndex, originalText, leadingSpace
                    FROM paragraphs
                    WHERE chapterId = ?
                    ORDER BY paragraphIndex ASC
                    """,
                    (chapter_id,),
            ) as paragraphs_cursor:
                paragraphs = [
                    Paragraph(
                        index=row["paragraphIndex"],
                        originalText=row["originalText"],
                        leadingSpace=row["leadingSpace"],
                        partOfChapter=chapter_id,
                        correctedText=None,
                        manuallyCorrectedText=None,
                    ) async for row in paragraphs_cursor
                ]

            return paragraphs

        except Exception as e:
            # Handle and log database errors (optional logging)
            print(f"Error fetching paragraph data: {e}")
            return []

    async def get_paragraphs_ids_needing_actions(self, chapter_id) -> List[int]:
        connection = self._connection

        try:
            # Fetch paragraphs for the specified chapter
            async with connection.execute(
                    f"""
                    SELECT paragraphIndex
                    FROM paragraphs
                    WHERE chapterId = ? AND correctionStatus != {CorrectionStatus.notRequired.value}
                    AND correctionStatus != {CorrectionStatus.accepted.value} 
                    AND correctionStatus != {CorrectionStatus.rejected.value}
                    """,
                    (chapter_id,),
            ) as paragraphs_cursor:
                return [
                    int(row["paragraphIndex"])
                    async for row in paragraphs_cursor
                ]

        except Exception as e:
            # Handle and log database errors (optional logging)
            print(f"Error fetching paragraph data: {e}")
            return []

    async def update_chapter(self, chapter: Chapter):
        """
        Updates an existing chapter's name and summary but does not modify the projectId or paragraphs.
    
        Args:
            chapter (Chapter): Chapter object containing the updated details.
    
        Raises:
            ValueError: If no chapter with the specified ID exists.
        """
        async with self._lock:  # Ensure thread safety
            connection = self._connection

            result = await connection.execute(
                """
                UPDATE chapters
                SET name = ?, summary = ?
                WHERE id = ?
                """,
                (chapter.name, chapter.summary, chapter.id)
            )
            if result.rowcount == 0:
                raise ValueError(f"No chapter found with ID {chapter.id}")

            await connection.commit()

    async def get_paragraph(self, chapter_id: int, paragraph_index: int) -> Paragraph | None:
        connection = self._connection

        try:
            async with connection.execute(
                    """
                    SELECT originalText, leadingSpace, correctionStatus, correctedText, manuallyCorrectedText
                    FROM paragraphs
                    WHERE chapterId = ? AND paragraphIndex = ?
                    """,
                    (chapter_id, paragraph_index),
            ) as paragraph_cursor:
                paragraph_data = await paragraph_cursor.fetchone()

            if not paragraph_data:
                return None

            return Paragraph(
                partOfChapter=chapter_id,
                index=paragraph_index,
                originalText=paragraph_data["originalText"],
                leadingSpace=paragraph_data["leadingSpace"],
                correctedText=paragraph_data["correctedText"],
                manuallyCorrectedText=paragraph_data["manuallyCorrectedText"],
                correctionStatus=paragraph_data["correctionStatus"],
            )

        except Exception as e:
            print(f"Error fetching paragraph data: {e}")
            return None

    async def update_paragraph(self, paragraph: Paragraph):
        """
        Updates paragraph, but doesn't update the original text nor the ID fields.

        :param paragraph: paragraph object with updated details.
        """
        async with self._lock:  # Ensure thread safety
            connection = self._connection

            result = await connection.execute(
                """
                UPDATE paragraphs
                SET correctedText = ?, manuallyCorrectedText = ?, correctionStatus = ?, leadingSpace = ?
                WHERE chapterId = ? AND paragraphIndex = ?
                """,
                (paragraph.correctedText, paragraph.manuallyCorrectedText, paragraph.correctionStatus,
                 paragraph.leadingSpace, paragraph.partOfChapter, paragraph.index)
            )
            if result.rowcount == 0:
                raise ValueError(f"No paragraph found with ID {paragraph.partOfChapter}-{paragraph.index}")

            await connection.commit()

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

    async def _insert_chapter(self, connection: Connection, chapter: Chapter, project_id: int):
        chapter_cursor = await connection.execute(
            """
            INSERT INTO chapters (projectId, chapterIndex, name, summary)
            VALUES (?, ?, ?, ?)
            """,
            (project_id, chapter.chapterIndex, chapter.name, chapter.summary)
        )
        chapter_id = chapter_cursor.lastrowid

        for paragraph in chapter.paragraphs:
            await connection.execute(
                """
                INSERT INTO paragraphs (
                    chapterId, paragraphIndex, originalText,
                    correctedText, manuallyCorrectedText, leadingSpace, correctionStatus,
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    chapter_id,
                    paragraph.index,
                    paragraph.originalText,
                    paragraph.correctedText,
                    paragraph.manuallyCorrectedText,
                    paragraph.leadingSpace,
                    paragraph.correctionStatus,
                )
            )

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
                CREATE UNIQUE INDEX idx_unique_project_name ON projects (name);
            """)

            await self._on_version_migrated(db, existing_config, 3)
        if existing_config["version"] == 3:
            await db.execute("ALTER TABLE paragraphs ADD COLUMN correctionStatus INTEGER NOT NULL DEFAULT 0")

            await self._on_version_migrated(db, existing_config, 4)
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
                    correctionStatus INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (chapterId) REFERENCES Chapters (id) ON DELETE CASCADE,
                    PRIMARY KEY (chapterId, paragraphIndex)
                );
        """)

        await db.commit()


# Singleton instance of the database
database = Database()
