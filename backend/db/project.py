from typing import Optional, List

from pydantic import BaseModel

from backend.utils.epub import Chapter as EpubChapter


# Matching data is in app/projectDefinitions.ts

class Paragraph(BaseModel):
    partOfChapter: int
    index: int
    originalText: str
    correctedText: Optional[str]

    # Text corrected by the user as opposed to the AI
    manuallyCorrectedText: Optional[str]

    # If there is some leading space (as detected from extraction) then this is above 0
    leadingSpace: int = 0


class Chapter(BaseModel):
    id: int
    projectId: int
    chapterIndex: int
    name: str

    # AI generated summary (if one exists)
    summary: Optional[str]

    paragraphs: list[Paragraph]


class Project(BaseModel):
    """
    The primary project model around which all the other data is built.
    This has a list of chapters and those contain paragraphs, which are the unit AI correction is used on.
    """
    id: int
    name: str
    stylePrompt: str
    correctionStrengthLevel: int
    chapters: list[Chapter]


def create_project(name: str, style_prompt: str, correction_strength_level: int,
                   chapters: List[EpubChapter]) -> Project:
    """
    Creates a project from frontend data and parsed list of epub chapters

    :param name:
    :param style_prompt:
    :param correction_strength_level:
    :param chapters:
    :return:
    """

    if correction_strength_level < 1 or correction_strength_level > 3:
        raise ValueError(
            "Correction strength level must be between 1 and 3"
        )

    parsed_chapters = []
    index_counter = 1

    for chapter in chapters:

        # We rebuild the paragraph index here even if not totally required
        paragraph_index = 1

        parsed_paragraphs = []

        for paragraph in chapter.paragraphs:
            parsed_paragraphs.append(
                Paragraph(
                    partOfChapter=0,
                    index=paragraph_index,
                    originalText=paragraph.text,
                    correctedText=None,
                    manuallyCorrectedText=None,
                    leadingSpace=paragraph.leadingSpace
                )
            )

            paragraph_index += 1

        parsed_chapters.append(
            Chapter(
                id=0,
                projectId=0,
                chapterIndex=index_counter,
                name=chapter.title,
                paragraphs=parsed_paragraphs,
                summary=None,
            )
        )

        index_counter += 1

    if len(parsed_chapters) < 1:
        raise ValueError(
            "No chapters found in data"
        )

    return Project(
        id=0,
        name=name,
        stylePrompt=style_prompt,
        correctionStrengthLevel=correction_strength_level,
        chapters=parsed_chapters
    )
