"use client";

import {useState, useEffect, Suspense} from "react";
import {useSearchParams} from "next/navigation"; // Hook to access query parameters
import Link from "next/link";

import {Chapter} from "@/app/projectDefinitions";

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

    if (chapterId == null) {
        return <p>No chapter found. Please go back to the project.</p>
    }

    return (
        <div className="p-8 pb-20 gap-16 font-[family-name:var(--font-geist-sans)]">
            <main className="flex flex-col gap-8 items-start max-w-2xl">
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

                {/* Loading state */}
                {loading ? (
                    <p>Loading chapter details...</p>
                ) : chapter ? (
                    <>
                        {/* List of Chapter paragraphs */}
                        <section>
                            <h2>Paragraphs</h2>

                            <ul className="space-y-2">
                                {chapter.paragraphs.map(paragraph => (
                                    <li key={paragraph.index} className="flex flex-col gap-2">
                                        {paragraph.leadingSpace > 0 && (<div className="h-2"/>)}
                                        <div className="flex items-center gap-4">
                                            <span className="font-semibold min-w-8">{paragraph.index}.</span>
                                            <span className="text-gray-700 ms-2 flex-grow">{paragraph.originalText}</span>
                                            <Link
                                                href={`#`}
                                                className="text-blue-500 hover:underline ms-2"
                                            >
                                                {"Correct"}
                                            </Link>
                                        </div>
                                    </li>
                                ))}
                            </ul>
                        </section>

                        <h2>Summary of Chapter</h2>
                        {/* Summary Section */}

                        {chapter.summary ? (
                            <div>
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
