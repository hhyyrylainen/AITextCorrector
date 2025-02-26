// Project type specifications that should match db/project.py file

// Enum for correction status
export enum CorrectionStatus {
    notGenerated = 0, // Default state
    generated = 1,
    reviewed = 2,
    accepted = 3,
    notRequired = 4,
    rejected = 5,
}

export type Paragraph = {
    partOfChapter: number;
    index: number;
    originalText: string;
    correctedText?: string;
    manuallyCorrectedText?: string;

    // Defaults to 0 in Python, so should always be a number
    leadingSpace: number;

    // Correction status with default as notGenerated
    correctionStatus: CorrectionStatus;
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
