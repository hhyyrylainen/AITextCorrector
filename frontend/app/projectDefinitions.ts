// Project type specifications that should match db/project.py file

export type Paragraph = {
    partOfChapter: number;
    index: number;
    originalText: string;
    correctedText?: string;
    manuallyCorrectedText?: string;

    // Defaults to 0 in Python, so should always be a number
    leadingSpace: number;
};

export type Chapter = {
    id: number;
    projectId: number;
    chapterIndex: number;
    belongsToProject: number;
    name: string;

    // Optional property for AI-generated summary
    summary?: string;

    // List of Paragraph objects
    paragraphs: Paragraph[];
};

export type Project = {
    id: number;
    name: string;
    stylePrompt: string;
    correctionStrengthLevel: number;

    // List of Chapter objects
    chapters: Chapter[];
};
