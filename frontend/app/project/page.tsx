"use client";

import {useState, useEffect, Suspense} from "react";
import {useSearchParams} from "next/navigation"; // Hook to access query parameters
import Link from "next/link";

import {Project} from "@/app/projectDefinitions";

function Page() {
    // Access the search parameters object
    const searchParams = useSearchParams();

    // Extract the `id` query parameter
    const projectId = searchParams.get("id");

    // State for project data, error messages, and summary button states
    const [project, setProject] = useState<Project | null>(null);
    const [loading, setLoading] = useState(true);
    const [summaryRequested, setSummaryRequested] = useState(false);
    const [summaryGenerated, setSummaryGenerated] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [summaryMessage, setSummaryMessage] = useState<string | null>(null);
    const [regeneratingSummary, setRegeneratingSummary] = useState(false);

    // State for toggling chapter summaries
    const [showSummaries, setShowSummaries] = useState(false);


    // Fetch the Project data from the backend when `projectId` is available
    useEffect(() => {
        if (!projectId) return; // Do nothing if `projectId` is not yet available

        const fetchProjectData = async () => {
            try {
                const res = await fetch(`/api/projects/${projectId}`);
                if (!res.ok) {
                    setErrorMessage("Failed to fetch project details.");
                    return;
                }
                const data: Project = await res.json();
                setProject(data);
            } catch (error) {
                setErrorMessage((error as Error).message || "An error occurred while fetching project data.");
            } finally {
                setLoading(false);
            }
        };
        fetchProjectData();
    }, [projectId]); // Trigger re-fetch when projectId changes


    // Function to handle summary generation
    const requestSummaryGeneration = async () => {
        // Reset error message and set the button state
        setSummaryMessage(null);
        setSummaryRequested(true);

        try {
            // Send a POST request to the backend
            const response = await fetch(`/api/projects/${projectId}/generateSummaries`, {
                method: "POST",
            });

            // Check if the request succeeded
            if (response.ok) {
                setSummaryGenerated(true); // Update state on success
            } else {
                // Handle non-2xx responses
                setSummaryMessage(
                    "Failed to generate summaries. Please try again later."
                );
            }
        } catch {
            // Handle network or unexpected errors
            setSummaryMessage("An unexpected error occurred. Please try again.");
        } finally {
            setSummaryRequested(false); // Re-enable the button
        }
    };

    // Function to regenerate a chapter summary
    const regenerateSummary = async (chapterId: number) => {
        setRegeneratingSummary(true);
        try {
            // Send a POST request to the backend
            const response = await fetch(`/api/chapters/${chapterId}/regenerateSummary`, {
                method: "POST",
            });

            if (response.ok) {
                // If the request is successful, refetch the project data to update the summary
                const updatedProject = await fetch(`/api/projects/${projectId}`).then((res) => res.json());
                setProject(updatedProject);
            } else {
                setErrorMessage("Failed to regenerate the summary. Please try again.");
            }
        } catch {
            setErrorMessage("An error occurred while regenerating the summary. Please try again.");
        } finally {
            setRegeneratingSummary(false);
        }
    };

    if (projectId == null) {
        return <p>No project found. Please go back to the project list.</p>
    }

    return (
        <div className="p-8 pb-20 gap-16 font-[family-name:var(--font-geist-sans)]">
            <main className="flex flex-col gap-8 items-start max-w-2xl">
                <h1>Project {project?.name || projectId}</h1>

                {/* Error message for fetching project or generating summary */}
                {errorMessage && (
                    <div className="text-red-600 bg-red-100 p-2 rounded-md">
                        {errorMessage}
                    </div>
                )}

                {/* Loading state */}
                {loading ? (
                    <p>Loading project details...</p>
                ) : project ? (
                    <>
                        {/* List of Project Chapters */}
                        <section>
                            <h2>Chapters</h2>

                            <ul className="space-y-2">
                                {project.chapters.map(chapter => (
                                    <li key={chapter.id} className="flex flex-col gap-2">
                                        <div className="flex items-center gap-4">
                                            <span className="font-semibold">{chapter.chapterIndex}.</span>
                                            <Link
                                                href={`/chapter?id=${chapter.id}`}
                                                className="text-blue-500 hover:underline"
                                            >
                                                {chapter.name}
                                            </Link>
                                        </div>
                                        {showSummaries && (
                                            <div className="text-gray-600 mb-3">
                                                {/* Replace "\n" with actual <br /> elements */}
                                                {chapter.summary
                                                    ? (
                                                        <div>
                                                            {chapter.summary.split("\n").map((line, index) => (
                                                                <span key={index}>
                                                            {line}
                                                                    <br/>
                                                        </span>
                                                            ))}

                                                            {/* Button to regenerate chapter summary */}
                                                            {regeneratingSummary ? "Regenerating..." :
                                                                (<button
                                                                    className="text-blue-500 hover:underline text-sm"
                                                                    onClick={() => regenerateSummary(chapter.id)}
                                                                >
                                                                    Regenerate Summary
                                                                </button>)
                                                            }
                                                        </div>
                                                    )
                                                    : "No summary exists"}
                                            </div>
                                        )}
                                    </li>
                                ))}
                            </ul>

                            {/* Checkbox to toggle summaries */}
                            <div className="mt-4">
                                <label className="flex items-center space-x-2">
                                    <input
                                        type="checkbox"
                                        checked={showSummaries}
                                        onChange={() => setShowSummaries((prev) => !prev)}
                                    />
                                    <span>Show Summaries</span>
                                </label>
                            </div>
                        </section>

                        {/* Summary Generation Section */}
                        <p>
                            Press the following button if chapter summaries are missing.
                            Once started it will take some minutes for summaries to be generated.
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
                            onClick={requestSummaryGeneration}
                            className={`px-4 py-2 rounded-md shadow-sm focus:outline-none ${
                                summaryRequested || summaryGenerated
                                    ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                                    : "bg-gray-300 text-gray-700 hover:bg-gray-200 focus:ring-gray-500 focus:ring-offset-2"
                            }`}
                            disabled={summaryRequested || summaryGenerated} // Disable button when processing
                        >
                            {summaryGenerated ? "Summaries Generated" : "Generate Chapter Summaries"}
                        </button>
                    </>
                ) : (
                    <p>No project found. Please go back to the project list.</p>
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
