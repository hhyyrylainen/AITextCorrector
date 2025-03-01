"use client";

import {Suspense, useEffect, useState} from "react";
import {useSearchParams} from "next/navigation"; // Hook to access query parameters
import Link from "next/link";

import ParagraphCorrector from "@components/ParagraphCorrector";

import {Chapter, CorrectionStatus, Paragraph} from "@/app/projectDefinitions";

function Page() {
    // Access the search parameters object
    const searchParams = useSearchParams();

    // Extract the `id` query parameter
    const chapterId = searchParams.get("id");

    // State for chapter data, error messages, and summary button states
    const [chapter, setChapter] = useState<Chapter | null>(null);
    const [loading, setLoading] = useState(true);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [summaryMessage, setSummaryMessage] = useState<string | null>(null);
    const [regeneratingSummary, setRegeneratingSummary] = useState(false);
    const [generatingCorrections, setGeneratingCorrections] = useState(false);
    const [generationRequested, setGenerationRequested] = useState(false);

    const [showExportMode, setShowExportMode] = useState(false);

    // Track which paragraphs are in correction mode
    const [correctionStates, setCorrectionStates] = useState<Record<number, boolean>>({});


    // Fetch the Chapter data from the backend when `chapterId` is available
    useEffect(() => {
        if (!chapterId) return; // Do nothing if `chapterId` is not yet available

        const fetchChapterData = async () => {
            try {
                const res = await fetch(`/api/chapters/${chapterId}`);
                if (!res.ok) {
                    setErrorMessage("Failed to fetch chapter details.");
                    return;
                }
                const data: Chapter = await res.json();
                setChapter(data);
            } catch (error) {
                setErrorMessage((error as Error).message || "An error occurred while fetching chapter data.");
            } finally {
                setLoading(false);
            }
        };
        fetchChapterData();
    }, [chapterId]); // Trigger re-fetch when chapterId changes

    // Function to regenerate a chapter summary
    const regenerateSummary = async () => {
        setRegeneratingSummary(true);
        try {
            // Send a POST request to the backend
            const response = await fetch(`/api/chapters/${chapterId}/regenerateSummary`, {
                method: "POST",
            });

            if (response.ok) {
                // If the request is successful, refetch the chapter data to update the summary
                const updatedChapter = await fetch(`/api/chapters/${chapterId}`).then((res) => res.json());
                setChapter(updatedChapter);
            } else {
                setSummaryMessage("Failed to regenerate the summary. Please try again.");
            }
        } catch {
            setSummaryMessage("An error occurred while regenerating the summary. Please try again.");
        } finally {
            setRegeneratingSummary(false);
        }
    };

    const generateCorrections = async () => {
        setGeneratingCorrections(true);
        try {
            const response = await fetch(`/api/chapters/${chapterId}/generateCorrections`, {
                method: "POST",
            });

            if (response.ok) {
                const data = await response.json();
                if (data.error) {
                    setErrorMessage(data.error);
                } else {
                    setErrorMessage("Correction generation for all paragraphs has started. It will take many minutes.");
                    setGenerationRequested(true);
                }
            } else {
                setErrorMessage("Failed to generate corrections. Please try again.");
            }
        } catch {
            setErrorMessage("An error occurred while generating corrections. Please try again.");
        } finally {
            setGeneratingCorrections(false);
        }
    }

    const openParagraphsNeedingCorrection = async () => {
        try {
            const response = await fetch(`/api/chapters/${chapterId}/paragraphsWithCorrections`,);

            if (response.ok) {
                const data = await response.json();
                if (data.error) {
                    setErrorMessage(data.error);
                } else if (!Array.isArray(data)) {
                    setErrorMessage("Failed to get list of paragraphs needing corrections. Please try again.");
                } else {
                    setCorrectionStates((prev) => {

                        const result = {...prev};

                        for (const id of data) {
                            result[id] = true;
                        }

                        return result;
                    });
                }
            } else {
                setErrorMessage("Failed to get list of paragraphs needing corrections. Please try again.");
            }
        } catch {
            setErrorMessage("An error occurred while fetching paragraphs list. Please try again.");
        }
    }

    const toggleParagraphCorrection = (id: number) => {
        // Toggle the correction state for the given paragraph ID
        setCorrectionStates((prev) => ({
            ...prev,
            [id]: !prev[id],
        }));
    };

    const setParagraphCorrection = (state: boolean) => {
        setCorrectionStates((prev) => ({
            ...prev,
            ...Object.fromEntries(chapter!.paragraphs.map(p => [p.index, state]))
        }))
    }

    const bgColourFromState = (paragraph: Paragraph) => {
        if (paragraph.correctionStatus == CorrectionStatus.accepted) {
            return "bg-green-100";
        } else if (paragraph.correctionStatus == CorrectionStatus.rejected) {
            return "bg-red-100";
        } else if (paragraph.correctionStatus == CorrectionStatus.notRequired) {
            return "bg-blue-200";
        } else if (paragraph.correctionStatus == CorrectionStatus.reviewed) {
            return "bg-yellow-100";
        } else if (paragraph.correctionStatus == CorrectionStatus.generated) {
            return "bg-gray-100";
        } else {
            return "";
        }
    }

    const paragraphTextToShow = (paragraph: Paragraph) => {
        if (paragraph.correctionStatus == CorrectionStatus.accepted) {
            return paragraph.manuallyCorrectedText || paragraph.correctedText || "CORRECTION MISSING!";
        }

        return paragraph.originalText;
    }

    function commonParagraphControls() {
        return (
            <>
                <button
                    className="ml-4 px-4 py-2 bg-gray-200 text-gray-600 rounded-md hover:bg-gray-300"
                    onClick={openParagraphsNeedingCorrection}
                >
                    {"Correct All"}
                </button>

                <button
                    className="ml-4 px-4 py-2 bg-gray-200 text-gray-600 rounded-md hover:bg-gray-300"
                    onClick={() => setParagraphCorrection(true)}
                >
                    {"Expand All"}
                </button>

                <button
                    className="ml-4 px-4 py-2 bg-gray-200 text-gray-600 rounded-md hover:bg-gray-300"
                    onClick={() => setParagraphCorrection(false)}
                >
                    {"Collapse All"}
                </button>

                <button
                    className={`ml-4 px-4 py-2 bg-gray-200 text-gray-600 rounded-md ${
                        generatingCorrections ? "bg-gray-100 text-gray-500 cursor-not-allowed"
                            : "bg-gray-200 text-gray-600 hover:bg-gray-300 "
                    }`}
                    onClick={generateCorrections}
                    disabled={generatingCorrections || generationRequested} // Disable button when processing
                >
                    {generationRequested ? "Generating..." : "Generate Corrections"}
                </button>
            </>
        )
    }

    if (chapterId == null) {
        return <p>No chapter found. Please go back to the project.</p>
    }

    return (
        <div className="pb-8 gap-16 w-full font-[family-name:var(--font-geist-sans)]">
            <main className="flex flex-col gap-8 items-center">
                <h1>Chapter {chapter?.chapterIndex}: {chapter?.name || chapterId}</h1>

                {chapter && (
                    <Link href={`/project?id=${chapter.projectId}`} className={"text-blue-600 hover:underline text-sm"}>
                        In Project {chapter.projectId}
                    </Link>
                )}

                {/* Error message for fetching chapter or generating summary */}
                {errorMessage && (
                    <div className="text-red-600 bg-red-100 p-2 rounded-md">
                        {errorMessage}
                    </div>
                )}

                <div className={"max-w-3xl"}>
                    {commonParagraphControls()}
                </div>

                {/* Loading state */}
                {loading ? (
                    <p>Loading chapter details...</p>
                ) : chapter ? (
                    <>
                        {/* List of Chapter paragraphs */}
                        <section className={"w-full flex flex-col items-center"}>
                            <h1>Paragraphs</h1>

                            <ul className="space-y-2 w-full">
                                {chapter.paragraphs.map(paragraph => (
                                    <li key={paragraph.index} className="w-full flex flex-col items-center gap-2">
                                        {paragraph.leadingSpace > 0 && (<div className="h-10"/>)}
                                        <div className="flex items-center gap-2">
                                            <span
                                                className={`font-semibold min-w-8 rounded p-1 ${bgColourFromState(paragraph)} text-center`}>
                                                {paragraph.index}.</span>
                                            <span className="text-gray-700 ms-2"
                                                  style={{maxWidth: "32rem", width: "32rem"}}>
                                                {paragraphTextToShow(paragraph).split("\n").map((line, index) => (
                                                    <span key={index}>
                                                        {line}
                                                        <br/>
                                                    </span>
                                                ))}
                                            </span>
                                            <button
                                                className="ml-4 px-4 py-2 bg-gray-200 text-gray-600 rounded-md hover:bg-gray-300 min-w-24"
                                                onClick={() => toggleParagraphCorrection(paragraph.index)}
                                            >
                                                {correctionStates[paragraph.index] ? "Cancel" : "Correct"}
                                            </button>
                                        </div>
                                        {/* Render ParagraphCorrector when correction mode is on */}
                                        {correctionStates[paragraph.index] && (
                                            <ParagraphCorrector paragraph={paragraph}/>
                                        )}
                                    </li>
                                ))}
                            </ul>
                        </section>

                        {/* second error display to see it near these buttons as well */}
                        {errorMessage && (
                            <div className="text-red-600 bg-red-100 p-2 rounded-md">
                                {errorMessage}
                            </div>
                        )}

                        <div className={"max-w-3xl"}>
                            {commonParagraphControls()}

                            <button
                                className="ml-4 px-4 py-2 bg-gray-200 text-gray-600 rounded-md hover:bg-gray-300"
                                onClick={() => setShowExportMode(!showExportMode)}
                            >
                                {"Export..."}
                            </button>
                        </div>

                        {showExportMode && (
                            <p>Export corrections from this chapter in bulk. TODO: implement this!</p>
                        )}

                        <div className={"max-w-2xl"}>
                            <h2>Summary of Chapter</h2>
                            {/* Summary Section */}

                            {chapter.summary ? (
                                <div className={"mx-2"}>
                                    {chapter.summary.split("\n").map((line, index) => (
                                        <span key={index}>
                                        {line}
                                            <br/>
                                    </span>
                                    ))}
                                </div>
                            ) : (
                                <p>No summary exists</p>
                            )}

                            <p>
                                Press the button below to generate a summary for this chapter. Note that it may take a
                                few minutes to generate.
                            </p>

                            {/* Show error message if there's an error */}
                            {summaryMessage && (
                                <div className="text-red-600 bg-red-100 p-2 rounded-md">
                                    {summaryMessage}
                                </div>
                            )}

                            {/* Button to trigger summary generation */}
                            <button
                                type="button"
                                onClick={regenerateSummary}
                                className={`px-4 py-2 rounded-md shadow-sm focus:outline-none ${
                                    regeneratingSummary
                                        ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                                        : "bg-gray-300 text-gray-700 hover:bg-gray-200 focus:ring-gray-500 focus:ring-offset-2"
                                }`}
                                disabled={regeneratingSummary} // Disable button when processing
                            >
                                {"Generate Summary"}
                            </button>
                        </div>
                    </>
                ) : (
                    <p>No chapter found. Please go back to the project.</p>
                )}
            </main>
        </div>
    );
}

export default function PageWrapper() {
    return (
        <Suspense>
            <Page/>
        </Suspense>
    )
}
