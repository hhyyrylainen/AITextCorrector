"use client";

type ProjectPageProps = {
    params: {
        id: string; // The dynamic route parameter id as a string
    };
};


import {useState, useEffect} from "react";
import Link from "next/link";

import {Project, Chapter} from "@/app/projectDefinitions";

export default function Page({params}: ProjectPageProps) {
    // State to store unwrapped params
    const [projectId, setProjectId] = useState<string | null>(null);

    // State for project data, error messages, and summary button states
    const [project, setProject] = useState<Project | null>(null);
    const [loading, setLoading] = useState(true);
    const [summaryRequested, setSummaryRequested] = useState(false);
    const [summaryGenerated, setSummaryGenerated] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [summaryMessage, setSummaryMessage] = useState<string | null>(null);

    // Unwrap params using `React.use()`
    useEffect(() => {
        const unwrapParams = async () => {
            const {id} = await params; // Await params Promise
            setProjectId(id); // Set the project ID
        };
        unwrapParams();
    }, [params]);


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
            } catch (error: any) {
                setErrorMessage(error.message || "An error occurred while fetching project data.");
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
        } catch (error) {
            // Handle network or unexpected errors
            setSummaryMessage("An unexpected error occurred. Please try again.");
        } finally {
            setSummaryRequested(false); // Re-enable the button
        }
    };


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
                                {project.chapters.map((chapter, index) => (
                                    <li key={chapter.id} className="flex gap-4 items-center">
                                        <span className="font-semibold">#{index}</span>
                                        <Link
                                            href={`/chapter/${chapter.id}`}
                                            className="text-blue-500 hover:underline"
                                        >
                                            {chapter.name}
                                        </Link>
                                    </li>
                                ))}
                            </ul>
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
                    <p>No project found. Please try again later.</p>
                )}
            </main>
        </div>
    );
}

