from enum import Enum

from difflib import SequenceMatcher

from backend.db.database import Database
from backend.db.project import Chapter, CorrectionStatus


class ExportMode(int, Enum):
    correctionsWithOriginal = 0


async def format_chapter_corrections_as_text(chapter: Chapter, mode: ExportMode, database: Database) -> str:
    unhandled = await database.get_paragraphs_ids_needing_actions(chapter.id)

    chapter_data = await database.get_chapter(chapter.id, include_paragraphs=True)
    paragraphs = chapter_data.paragraphs

    text = ""

    if len(unhandled) > 0:
        text += f"This chapter has {len(unhandled)} paragraphs that need manual checking!\n\n"

    corrections = 0

    for paragraph in paragraphs:
        if paragraph.correctionStatus == CorrectionStatus.accepted:
            corrections += 1

    text += f"Listing {corrections} paragraph(s) that have corrections.\n"

    for paragraph in paragraphs:
        if paragraph.correctionStatus != CorrectionStatus.accepted:
            continue

        text += "\n"

        if paragraph.leadingSpace > 0:
            text += "\n" * paragraph.leadingSpace

        text += f"Paragraph {paragraph.index}:\n"

        if mode == ExportMode.correctionsWithOriginal:
            text += f"Original: {paragraph.originalText}\n"
            text += f"Correction: {paragraph.correctedText}\n"

            text += f"\nCorrection highlighted:\n"

            try:
                text += highlight_diff(paragraph.originalText, paragraph.correctedText)
            except Exception as e:
                text += f"## Error highlighting diff: {e}"
                print(f"Error highlighting diff: {e}")

            text += "\n---\n"
        else:
            raise Exception("Invalid export mode")

    return text


def highlight_diff(original: str, updated: str) -> str:
    """
    Highlights the differences between two strings by adding '*' around the differing segments.

    :param original: The original string
    :param updated: The updated string
    :return: The updated string with '*' indicating the differences
    """
    # Use SequenceMatcher to find the differences
    matcher = SequenceMatcher(None, original, updated)
    highlighted = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':  # If the segments are equal, just add them
            highlighted.append(updated[j1:j2])
        elif tag in {'replace', 'insert', 'delete'}:  # Highlight differences
            highlighted.append(f"*{updated[j1:j2]}*")

    # Combine all the highlighted segments into a single string
    return ''.join(highlighted)


def parse_mode(mode: str) -> ExportMode:
    if mode == "correctionsWithOriginal":
        return ExportMode.correctionsWithOriginal
    else:
        raise Exception("Invalid export mode")
