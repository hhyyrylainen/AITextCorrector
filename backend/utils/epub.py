import zipfile
from typing import IO, List, Dict

from bs4 import BeautifulSoup
from pydantic import BaseModel


class Paragraph(BaseModel):
    text: str
    index: int
    leadingSpace: int = 0


class Chapter(BaseModel):
    title: str
    paragraphs: List[Paragraph]


def extract_epub_chapters(file_content: IO[bytes]) -> List[Chapter]:
    """
    Extracts chapters as plain text from an EPUB file.

    Args:
        file_content (IO): File-like object containing the EPUB content.

    Returns:
        List: List of chapters containing their titles and content.
    """
    result = []

    # Use a zipfile to read the EPUB content
    with zipfile.ZipFile(file_content) as epub_zip:
        # Locate the container file
        with epub_zip.open('META-INF/container.xml') as container_file:
            container_soup = BeautifulSoup(container_file, 'xml')
            rootfile_path = container_soup.find('rootfile')['full-path']

        # Extract TOC to know what chapters we should look at (spine has stuff we don't necessarily want)
        valid_chapters = extract_epub_toc(epub_zip)

        # Open the rootfile (OPF file) to find the spine and chapters
        with epub_zip.open(rootfile_path) as opf_file:
            opf_soup = BeautifulSoup(opf_file, 'xml')

            # Iterate through the valid chapters
            for chapter in valid_chapters:
                chapter_title = chapter['title']

                # Skip unwanted chapters
                title_lower = chapter_title.lower()
                if title_lower == "preface" or title_lower == "afterword":
                    continue

                if chapter_title.lower().startswith(('note:', 'remark:', 'skip:', 'footer:')):
                    continue

                chapter_path = chapter['href']

                # Extract the chapter content
                with epub_zip.open(chapter_path) as chapter_file:
                    chapter_soup = BeautifulSoup(chapter_file, 'html.parser')

                    # Skip irrelevant remarks or metadata (headers, footers)
                    body = chapter_soup.find('body')
                    if not body:
                        continue  # If no <body> tag is found, move to the next chapter

                    paragraph_result = []
                    paragraph_counter = 1

                    # Body text extraction
                    paragraphs = body.find_all('p')  # Get paragraphs (<p> tags)

                    leading_space = 0

                    for paragraph in paragraphs:
                        paragraph_text = paragraph.get_text(strip=True)  # Extract clean text from the paragraph

                        # Ignore empty paragraphs or remarks
                        skip = (not paragraph_text or paragraph_text.lower().startswith(
                            ('note:', 'remark:', 'skip:', 'footer:', "chapter notes")))

                        # Ignore notes in ao3 epubs
                        if not skip and paragraph.parent.name == "blockquote" and "userstuff" in paragraph.parent.get(
                                "class") :
                            skip = True

                        if skip:
                            # Empty paragraphs add extra spacing between other paragraphs to make chapters look nicer
                            if len(paragraph_result) > 0:
                                leading_space = 1
                            continue

                        paragraph_result.append(
                            Paragraph(text=paragraph_text, index=paragraph_counter, leadingSpace=leading_space))
                        paragraph_counter += 1
                        leading_space = 0

                    chapter = Chapter(title=chapter_title, paragraphs=paragraph_result)
                    result.append(chapter)

    return result


def chapters_to_plain_text(chapters: List[Chapter], char_limit: int):
    extracted_text = ""

    current_char_count = 0
    chapter_counter = 0

    for chapter in chapters:
        chapter_title = chapter.title
        title_lower = chapter_title.lower()

        if "chapter" not in title_lower:
            chapter_counter += 1
            title_with_separator = f"## Chapter {chapter_counter}: {chapter_title}\n\n"
        else:
            title_with_separator = f"## {chapter_title}\n\n"

        # Spacing before chapter title
        if len(extracted_text) > 0:
            extracted_text += "\n"

        extracted_text += title_with_separator
        current_char_count += len(title_with_separator)

        for paragraph in chapter.paragraphs:

            # Add the text to the output, while respecting the character limit
            # TODO: maybe a mode where only full paragraphs are allowed to be cut?
            if current_char_count + len(paragraph.text) > char_limit:
                remaining_chars = char_limit - current_char_count
                extracted_text += paragraph.text[:remaining_chars]
                return extracted_text  # Stop future processing at the limit

            extracted_text += paragraph + "\n\n"  # Add double newline for paragraph break
            current_char_count += len(paragraph.text)

    return extracted_text


## Internal helper functions

def extract_epub_toc(epub_zip: zipfile) -> List[Dict[str, str]]:
    """
    Extracts the Table of Contents (ToC) from an EPUB file that is already open as a zip

    Returns:
        List[Dict[str, str]]: A list of dictionaries, each representing a ToC entry with `title` and `href`.
    """
    # Step 1: Locate the container.xml file
    with epub_zip.open('META-INF/container.xml') as container_file:
        container_soup = BeautifulSoup(container_file, 'xml')
        rootfile_path = container_soup.find('rootfile')['full-path']

    # Step 2: Parse the OPF file to find the ToC file reference
    with epub_zip.open(rootfile_path) as opf_file:
        opf_soup = BeautifulSoup(opf_file, 'xml')

        # Get the manifest to find the ToC file (NCX or Nav)
        manifest_items = {item['id']: item for item in opf_soup.find_all('item')}
        spine = opf_soup.find('spine')

        # Try to locate the NCX file first (For EPUB 2)
        ncx_reference = [item['href'] for item in manifest_items.values() if
                         item.get('media-type') == 'application/x-dtbncx+xml']

        if ncx_reference:
            ncx_path = ncx_reference[0]
            with epub_zip.open(ncx_path) as ncx_file:
                ncx_soup = BeautifulSoup(ncx_file, 'xml')
                return extract_ncx_toc(ncx_soup)

        # If there is no NCX file, fall back to EPUB 3 HTML navigation document
        nav_item = [item for item in manifest_items.values() if
                    item['media-type'] == 'application/xhtml+xml' and 'nav' in item['properties']]
        if nav_item:
            nav_href = nav_item[0]['href']
            with epub_zip.open(nav_href) as nav_file:
                nav_soup = BeautifulSoup(nav_file, 'html.parser')
                return extract_nav_toc(nav_soup)

    return []


def extract_ncx_toc(ncx_soup: BeautifulSoup) -> List[Dict[str, str]]:
    """
    Extracts the ToC from an NCX file (EPUB 2).
    Args:
        ncx_soup (BeautifulSoup): Parsed NCX contents.

    Returns:
        List[Dict[str, str]]: A list of ToC entries with `title` and `href`.
    """
    toc = []
    nav_points = ncx_soup.find_all('navPoint')
    for nav_point in nav_points:
        # Extract ToC entry: text and corresponding reference (href)
        title = nav_point.find('text').get_text(strip=True)
        content = nav_point.find('content')['src']
        toc.append({'title': title, 'href': content})
    return toc


def extract_nav_toc(nav_soup: BeautifulSoup) -> List[Dict[str, str]]:
    """
    Extracts the ToC from an HTML navigation file (EPUB 3).
    Args:
        nav_soup (BeautifulSoup): Parsed HTML navigation file.

    Returns:
        List[Dict[str, str]]: A list of ToC entries with `title` and `href`.
    """
    toc = []
    # Find the <nav> element with role="doc-toc" for ToC
    nav_toc = nav_soup.find('nav', {"epub:type": "toc"}) or nav_soup.find('nav', {"role": "doc-toc"})
    if not nav_toc:
        return toc

    # Traverse <nav> and extract entries
    for li in nav_toc.find_all('li'):
        a_tag = li.find('a')
        if a_tag:
            title = a_tag.get_text(strip=True)
            href = a_tag['href']
            toc.append({'title': title, 'href': href})
    return toc
