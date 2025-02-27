import re
from collections import Counter
from functools import partial
import time
from typing import List

from backend.db.config import DEFAULT_MODEL
from backend.db.database import Database
from backend.db.project import Project, Chapter, Paragraph, CorrectionStatus
from backend.utils.job import Job
from backend.utils.job_queue import JobQueue
from backend.utils.correction_validation import validate_corrections
from .ollama_client import OllamaClient

# TODO: investigate JSON formatted responses

ANALYZE_PROMPT = (
    "Analyze the writing style of the provided text, focusing on key elements such as sentence structure, word choice, "
    "tone, readability, and overall style. Provide a concise, one-paragraph summary of the writing style in the form "
    "of instructions, as if advising someone on how to emulate this style. Avoid commenting on the content itself, "
    "such as the author's expertise or the subject matter—it's only about the writing style.\n"
    "\n"
    "Example output: \"Write using [characteristic 1], [characteristic 2], and [characteristic 3]. "
    "Employ [writing technique 1] and [writing technique 2] to [desired effect]. Maintain a [tone] tone throughout, "
    "and aim for a readability score of [score].\"\n"
    "\n"
    "#TEXT\n"
    "\n")

SUMMARY_PROMPT = (
    "\n---\n"
    "Write a summary of the plot in the above text. Write at most four to five paragraphs of summary of the text with the focus"
    "being on the most important plot points in this chapter. Write about what happened in the chapter without "
    "speculating about the future direction of the story. Also do not comment on the writing style or sophistication of "
    "the text. Assume the target audience of the summary is already familiar with the overall story the chapter is from.")

# If this is too low starts of chapters won't be summarized
# If this cannot be turned high enough then a multipart analysis will need to be done
SUMMARY_CONTEXT_WINDOW_SIZE = 8196

TEXT_CORRECTION_PROMPT_LOW = (
    "Check the given text for typos and misspellings. Do not rephrase sentences or try to correct the grammar. "
    "Do not suggest synonyms to improve the text. Answer by replying with the full text with the corrections applied "
    "to it. Separate the paragraphs in your corrections with \"---\" like the paragraphs are given. "
    "Do not add new paragraph breaks or merge existing ones. If there are no corrections to make, "
    "reply with the original text. Do not include anything extra in your response, just the corrected text.\n"
    "\n"
    "Here are the text paragraphs to correct:\n"
    "---\n")

TEXT_CORRECTION_PROMPT_MEDIUM = (
    "Check the given text for typos and grammar errors. Do not rewrite sentences that are technically grammatically "
    "correct even if they are hard to read. Do not suggest synonyms to improve the text. Answer by replying with the "
    "full text with the corrections applied to it. Separate the paragraphs in your corrections with \"---\" like the "
    "paragraphs are given. Do not add new paragraph breaks or merge existing ones. If there are no corrections to make, "
    "reply with the original text. Do not include anything extra in your response, just the corrected text.\n"
    "\n"
    "Here are the text paragraphs to correct:\n"
    "---\n")

TEXT_CORRECTION_PROMPT_MAX = (
    "Check the given text for typos, grammar and awkward sentence structures. Try to keep as close to the original "
    "writer's style when rewriting sentences as possible. Answer by replying with the "
    "full text with the corrections applied to it. Separate the paragraphs in your corrections with \"---\" like the "
    "paragraphs are given. Do not add new paragraph breaks or merge existing ones. "
    "Do not include anything extra in your response, just the corrected text.\n"
    "\n"
    "Here are the text paragraphs to correct:\n"
    "---\n")

# Lower temperature makes less creative answers, and hopefully makes the text correction more reliable
# Though, it kind of seems like low heat more often doesn't follow the prompt fully?
# CORRECTION_MODEL_TEMPERATURE = 0.7
# CORRECTION_MODEL_TEMPERATURE = 0.75
CORRECTION_MODEL_TEMPERATURE = 0.79

# How many times to retry a prompt if the AI is not making correctly formatted suggestions (or Levenshtein distance
# check fails)
MAX_TECHNICAL_RETRIES = 2

EXTRA_RECOMMENDED_MODELS = ["deepseek-r1:14b"]


class AIManager:
    """
    Main manager of the AI side of things, handles running AI jobs and finding the right model
    """

    def __init__(self):
        self.unload_delay = 300
        self.currently_running = False
        self.model = "deepseek-r1:32b"
        self.job_queue = JobQueue()

    def configure_model(self, model: str):
        self.model = model
        print("Changed active model to: ", model)

    def prompt_chat(self, message, remove_think=False) -> Job:
        task = Job(partial(self._prompt_chat, message, self.model, None, remove_think))

        self.job_queue.submit(task)

        return task

    def analyze_writing_style(self, text) -> Job:
        # TODO: maybe increase context window also here?
        task = Job(partial(self._prompt_chat, ANALYZE_PROMPT + text, self.model, None, True))

        self.job_queue.submit(task)

        return task

    async def generate_summaries(self, project: Project, database: Database):
        for chapter in project.chapters:
            if chapter.summary:
                continue

            print("Generating missing summary for chapter:", chapter.name)

            paragraphs = await database.get_chapter_paragraph_text(chapter.id)

            await self._generate_summary(chapter, paragraphs)

            await database.update_chapter(chapter)

    async def generate_single_summary(self, chapter: Chapter):
        """
        Synchronously generate a summary for a single chapter

        :param chapter: chapter to generate summary for
        """
        if len(chapter.paragraphs) < 1:
            raise Exception(
                "Cannot generate summary for chapter with no paragraphs (was the right database fetch method used?")

        await self._generate_summary(chapter, chapter.paragraphs)

    async def generate_corrections_for_project(self, project: Project, database: Database):
        if not project.chapters:
            raise Exception("Cannot generate corrections for project with no chapters")

        print("Generating corrections for project:", project.name)

        for chapter in project.chapters:
            try:
                # This doesn't require a recursively fetched project, so we need to fetch the chapters here again
                fully_loaded_chapter = await database.get_chapter(chapter.id, True)

                await self.generate_corrections(fully_loaded_chapter, database, project.correctionStrengthLevel)
            except Exception as e:
                print("Error generating corrections for chapter:", chapter.name, "with error:", e)
                continue

    async def generate_corrections(self, chapter: Chapter, database: Database, correction_strength: int):
        if not chapter.paragraphs:
            raise Exception("Cannot generate corrections for chapter with no paragraphs")

        start = time.time()

        config = await database.get_config()

        paragraphs_to_correct = [paragraph for paragraph in chapter.paragraphs if
                                 paragraph.correctionStatus == CorrectionStatus.notGenerated]

        if len(paragraphs_to_correct) < 1:
            print("No paragraphs to correct, skipping chapter:", chapter.name)
            return

        print(f"Generating corrections for chapter {chapter.chapterIndex}:", chapter.name)

        for group in chunked_paragraphs(paragraphs_to_correct, config.simultaneousCorrectionSize):

            print("Correcting paragraph group with size:", len(group), "and total character count:", sum(
                [len(paragraph.originalText) for paragraph in group]))

            try:
                await self._generate_correction(group, correction_strength, config.correctionReRuns)
            except Exception as e:
                print("Error generating correction for group with error:", e)
                print("Ignoring this group and continuing with the rest of the chapter...")
                continue

            for paragraph in group:
                await database.update_paragraph(paragraph)

        duration = time.time() - start
        if duration > 10:
            print("Generated corrections for chapter:", chapter.name, "in:", round(duration / 60, 1), "minutes")

    async def generate_single_correction(self, paragraph: Paragraph, correction_strength: int, re_runs: int):
        print("Generating correction for paragraph:", paragraph.index, "in chapter:", paragraph.partOfChapter)

        await self._generate_correction([paragraph], correction_strength, re_runs)

    def download_recommended(self):
        all_models = [DEFAULT_MODEL] + EXTRA_RECOMMENDED_MODELS

        for model in all_models:
            print("Will download model: ", model)

            task = Job(partial(self._download_model, model))

            self.job_queue.submit(task)

    @property
    def queue_length(self):
        return self.job_queue.task_queue.qsize()

    async def _generate_summary(self, chapter: Chapter, paragraphs: List[Paragraph]):
        text = f"Chapter {chapter.chapterIndex}: {chapter.name}\n\n"

        for paragraph in paragraphs:
            text += "\n\n"

            if paragraph.leadingSpace > 0:
                text += "\n" * paragraph.leadingSpace

            text += paragraph.originalText

        # Increase context length to get full chapter explanations
        extra_options = {"num_ctx": SUMMARY_CONTEXT_WINDOW_SIZE}

        task = Job(
            partial(self._prompt_chat, "Read this text:\n" + text + SUMMARY_PROMPT, self.model, extra_options,
                    True))

        self.job_queue.submit(task)

        response = await task

        if len(response) > 3500:
            response = response[:3500] + "..."

        chapter.summary = response

    async def _generate_correction(self, paragraph_bundle: List[Paragraph], correction_strength: int, re_runs: int):
        start = time.time()

        if correction_strength == 1:
            prompt = TEXT_CORRECTION_PROMPT_LOW
        elif correction_strength == 2:
            prompt = TEXT_CORRECTION_PROMPT_MEDIUM
        elif correction_strength == 3:
            prompt = TEXT_CORRECTION_PROMPT_MAX
        else:
            print("Invalid correction strength, using medium prompt!")
            prompt = TEXT_CORRECTION_PROMPT_MEDIUM

        # Adjust temperature for the model when doing corrections
        # TODO: could try with an increased context size and a vastly higher max corrections at once setting
        extra_options = {"temperature": CORRECTION_MODEL_TEMPERATURE}

        text = "---".join([paragraph.originalText for paragraph in paragraph_bundle]) + "\n---"

        corrections = None
        corrections_history: List[List[str]] = []

        technical_retries = MAX_TECHNICAL_RETRIES

        while True:
            while True:
                task = Job(partial(self._prompt_chat, prompt + text, self.model, extra_options, True))

                self.job_queue.submit(task)
                response = await task

                try:
                    corrections = extract_corrections(paragraph_bundle, response)

                    # Check how different the corrections are to not allow pure garbage through (but only if more than
                    # two paragraphs were corrected as once as the AI shouldn't be able to write short enough garbage
                    # to match the length
                    if len(paragraph_bundle) >= 3:
                        if not validate_corrections([paragraph.originalText for paragraph in paragraph_bundle],
                                                    corrections):
                            print("Corrections are too dissimilar to the original text, considering them invalid")
                            raise Exception("Invalid corrections found in response! (too dissimilar to original text)")

                    # Check that the AI hasn't split quotation marks outside the real paragraphs
                    for index, correction in enumerate(corrections):
                        if len(correction) < 2 and len(paragraph_bundle[index].originalText) > 0:
                            raise Exception("Invalid correction found in response! (too short):", correction)

                except Exception as e:
                    print("Error extracting corrections from response:", e)
                    print("Response:", response)

                    # Retry a few times on technicalities
                    if technical_retries <= 0:
                        if len(corrections_history) > 0:
                            print("Using previous corrections due to running out of technical retries")
                            corrections = corrections_history[-1]
                            # This will already detect that all the same text was added again, so we might as well
                            # explicitly stop the re_runs
                            re_runs = 0
                            break

                        raise e

                    technical_retries -= 1
                    print("Retrying correction due to technical issue, remaining retries:", technical_retries)
                    continue

                # No need for technical retry
                break

            # Restore some technical retries for another re-run (but don't go over a limit)
            technical_retries = min(technical_retries + MAX_TECHNICAL_RETRIES // 2, MAX_TECHNICAL_RETRIES)

            corrections_history.append(corrections)

            if re_runs <= 0:
                break

            re_runs -= 1

            # If no corrections are needed for any text, then we can end
            matches = True
            index = 0
            for paragraph in paragraph_bundle:
                correction = corrections[index]
                index += 1

                if correction != paragraph.originalText:
                    matches = False

            if matches:
                # A full match, no need to do anything
                # Delete history to not accidentally pick some minor correction we don't actually need
                corrections_history = []
                break

            if len(corrections_history) > 1:
                # Break if all entries in the correction histories are the same
                if history_entries_match(corrections_history):
                    break

        if not corrections:
            print("No corrections found in response, skipping correction!")
            return

        corrections = pick_best_history(corrections_history, corrections)
        apply_corrections(paragraph_bundle, corrections, time.time() - start)

    def _prompt_chat(self, message, model, extra_options=None, remove_think=False) -> str:
        self.currently_running = True
        client = OllamaClient(unload_delay=self.unload_delay)

        response = client.submit_chat_message(model, message, extra_options)
        self.currently_running = False

        if "error" in response:
            raise Exception(f"Ollama API error: {response['error']}")

        # Convert nanoseconds to seconds
        print("Ollama API took: ", response["total_duration"] / 1_000_000_000)

        content = response["message"]["content"]

        if remove_think and content.startswith("<think>"):
            # Remove everything between <think></think> tags
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)

        return content.strip()

    def _download_model(self, model):
        self.currently_running = True
        client = OllamaClient()
        if client.download_model(model):
            print("Downloaded model: ", model)

        self.currently_running = False


def extract_corrections(paragraph_bundle: List[Paragraph], response: str) -> List[str]:
    parts = [part.strip() for part in response.split("---")]

    # Remove blank parts
    parts = [part for part in parts if len(part) > 0]

    # If we end up with different number of parts than paragraphs, then we are in trouble
    if len(parts) != len(paragraph_bundle):
        # Remove any preface the AI may have added
        if len(parts) - 1 == len(paragraph_bundle) and is_ai_preamble(parts[0]):
            parts = parts[1:]
            return parts

        # Remove pre-amble as it is going to be hard for the further processing
        if len(parts) > 1 and is_ai_preamble(parts[0]):
            parts = parts[1:]

        # Delete exactly duplicated parts
        parts = list(dict.fromkeys(parts))  # Preserves order

        if len(parts) == len(paragraph_bundle):
            return parts

        # Handle the case where the AI might just be splitting things on empty lines
        line_parts = [section.strip() for part in parts for section in part.split("\n\n")]

        # Remove any pre-amble that is visible now, and hope there were two spaces separating it so that it doesn't
        # accidentally remove the first real part here
        if len(line_parts) > 1 and is_ai_preamble(line_parts[0]):
            line_parts = line_parts[1:]

        if len(line_parts) == len(paragraph_bundle):
            return line_parts
        else:
            # Try splitting even harder on the parts
            line_parts = [section.strip() for part in line_parts for section in part.split("\n")]

            # Hopefully preamble cannot appear here anymore...

            # Check against accidentally accepting an AI correction summary paragraphs as part of the corrections
            if len(line_parts) == len(paragraph_bundle) and not is_ai_corrections_summary(line_parts):
                return line_parts

        # Try a different separator
        parts = [part.strip() for part in response.split("—")]
        parts = [part for part in parts if len(part) > 0]
        if len(parts) > 1 and is_ai_preamble(parts[0]):
            first = parts[0]
            parts = parts[1:]

            # In case there's something else in the first part, restore that
            split_first = first.split("\n\n")

            # Try single lines if it looks like no double line change was used
            if len(split_first) < 2:
                split_first = first.split("\n")

            if len(split_first) > 1:
                parts = split_first[1:] + parts

        if len(parts) == len(paragraph_bundle):
            return parts

        print("Incorrect number of parts in response! Expected:", len(paragraph_bundle), "Got:", len(parts))
        raise Exception("Incorrect number of parts in response!")

    return parts


# TODO: put these in a separate correction helpers file:

def apply_corrections(paragraph_bundle: List[Paragraph], corrections: List[str], duration: float = 0.0):
    needed_corrections = 0
    perfect_already = 0

    # Apply the corrections
    index = 0
    for paragraph in paragraph_bundle:

        correction = corrections[index]
        index += 1

        # Update correction status for paragraphs that were missing the status
        if paragraph.correctionStatus == CorrectionStatus.notGenerated:
            paragraph.correctionStatus = CorrectionStatus.generated

        # Reset rejected status if there's new text
        if paragraph.correctionStatus == CorrectionStatus.rejected and paragraph.correctedText != correction:
            paragraph.correctionStatus = CorrectionStatus.generated

        if correction == paragraph.originalText:
            paragraph.correctedText = None
            perfect_already += 1

            # Set no correction required status if it makes sense
            if paragraph.correctionStatus != CorrectionStatus.accepted and paragraph.correctionStatus != CorrectionStatus.reviewed:
                paragraph.correctionStatus = CorrectionStatus.notRequired

            # print("No correction needed for paragraph:", paragraph.index, "in chapter:", paragraph.partOfChapter)
        else:
            paragraph.correctedText = correction
            needed_corrections += 1

            if paragraph.correctionStatus == CorrectionStatus.notRequired:
                paragraph.correctionStatus = CorrectionStatus.generated

    if needed_corrections == 0:
        print("No corrections needed for paragraph bundle in chapter:", paragraph_bundle[0].partOfChapter,
              "processed in:", round(duration, 3), "seconds")
    else:
        print("Needed corrections in", needed_corrections, "paragraph(s),", perfect_already,
              "were perfect already, in chapter:", paragraph_bundle[0].partOfChapter, "processed in:",
              round(duration, 3), "seconds")


def chunked_paragraphs(paragraphs: List[Paragraph], chunk_size: int = 100) -> List[List[Paragraph]]:
    """
    Groups up paragraphs into chunks of a given total character length
    :param paragraphs: paragraphs to group
    :param chunk_size: size of each chunk
    :return: list of lists of paragraphs
    """
    chunks = []
    current_chunk = []
    current_size = 0

    for paragraph in paragraphs:
        paragraph_length = len(paragraph.originalText)

        # Chunks may not be empty if all paragraphs are too long by themselves
        # Also if there is a gap in the paragraph indices, then do not allow combining
        if ((current_size + paragraph_length > chunk_size) and len(current_chunk) > 0) or (
                len(current_chunk) > 0 and current_chunk[-1].index + 1 != paragraph.index):
            chunks.append(current_chunk)
            current_chunk = []
            current_size = 0

        current_chunk.append(paragraph)
        current_size += paragraph_length

    if current_chunk:
        chunks.append(current_chunk)

    print(f"Consolidated {len(paragraphs)} paragraphs into {len(chunks)} chunks of size {chunk_size}")
    return chunks


def history_entries_match(corrections_history: List[List[str]]) -> bool:
    """
    Looks in each history entry and compares it to the other ones, if all histories have the same item in slot 0,
    slot 1, etc. then they are considered to be the same.
    :param corrections_history: history to check
    :return: True if histories match
    """
    # If there are no history entries or just one, they can be considered matching.
    if not corrections_history or len(corrections_history) == 1:
        return True

    # Use zip to iterate over each "slot" from all history entries.
    for items in zip(*corrections_history):
        # If there are different items in this slot, the histories do not match.
        if len(set(items)) > 1:
            return False

    return True


def pick_best_history(corrections_history: List[List[str]], corrections: List[str]) -> List[str]:
    """
    Finds the most common item in each history at each slot and returns the corrections with those items. If no
    history exists returns the "corrections" parameter.
    :param corrections_history: history to inspect
    :param corrections: fallback corrections if no history exists

    :return: best corrections from the history
    """
    if len(corrections_history) == 0:
        return corrections

    best_corrections = []

    # Using zip will collect each corresponding slot in the history entries
    for slot_items in zip(*corrections_history):
        # Count how many times each correction appears in this slot.
        counter = Counter(slot_items)
        # Select the most common item. most_common(1) returns a list with one tuple (item, count)
        best_item = counter.most_common(1)[0][0]
        best_corrections.append(best_item)

    return best_corrections


def is_ai_preamble(text: str) -> bool:
    """
    Checks if text is just a dumb AI preamble that should be removed
    :param text: text to check
    :return: True if it is a preamble, False otherwise
    """
    as_lower = text.lower()

    return (as_lower.startswith("here are the corrected text") or
            as_lower.startswith("here are the corrected paragraphs") or
            as_lower.startswith("here are the corrected chapters") or
            as_lower.startswith("here are the corrections applied") or
            as_lower.startswith("here are the text paragraphs") or
            as_lower.startswith("here is the corrected"))


def is_ai_corrections_summary(parts: List[str]) -> bool:
    if len(parts) < 2:
        return False

    first_lower = parts[0].lower()

    if "issues" in first_lower and "provided" in first_lower and "corrections" in first_lower:
        return True

    if "here is the corrected" in first_lower:
        return True

    return False
