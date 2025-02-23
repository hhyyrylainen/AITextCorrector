// Project type specifications that should match db/project.py file

export type Paragraph = {
    partOfChapter: number;
    index: number;
    originalText: string;
    correctedText?: string; // Optional property
    manuallyCorrectedText?: string; // Optional property
    leadingSpace: number; // Defaults to 0 in Python, so should always be a number
};

export type Chapter = {
    id: number;
    projectId: number;
    chapterIndex: number;
    belongsToProject: number;
    name: string;
    summary?: string; // Optional property for AI-generated summary
    paragraphs: Paragraph[]; // List of Paragraph objects
};

export type Project = {
    id: number;
    name: string;
    stylePrompt: string;
    correctionStrengthLevel: number;
    chapters: Chapter[]; // List of Chapter objects
};
