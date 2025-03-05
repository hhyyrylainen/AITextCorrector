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
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [submitting, setSubmitting] = useState(false);

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


    // Handles submission of the form
    const handleMainSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        setErrorMessage(null);
        setSubmitting(true);

        const formData = new FormData(event.currentTarget);

        try {
            const response = await fetch(`/api/projects/${projectId}/updateText`, {
                method: "POST",
                body: formData,
            });

            if (!response.ok) {
                // Handle server errors
                const errorData = await response.json();
                setErrorMessage(errorData?.message || "Failed to update the project. Please try again."); // Display server error message
            }
        } catch (error) {
            console.error("Error submitting the form:", error);
            setErrorMessage("An unexpected error occurred. Please try again.");
        } finally {
            setSubmitting(false);
        }
    };

    if (projectId == null) {
        return <p>No project found. Please go back to the project list.</p>
    }

    return (
        <div className="p-8 pb-20 gap-16 font-[family-name:var(--font-geist-sans)]">
            <main className="flex flex-col gap-8 items-start max-w-2xl">
                <h1>Edit Project {project?.name || projectId}</h1>

                <Link href={`/project?id=${projectId}`} style={{color: "blue", textDecoration: "underline"}}>
                    Back to Project
                </Link>

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
                        {/* Main Form */}
                        <form
                            onSubmit={handleMainSubmit}
                            className="flex flex-col gap-4 w-full"
                            encType="multipart/form-data"
                        >
                            {/* TODO: implement modifying the following */}
                            {/* Name Input Section */}
                            {/* "Level of Correction" Field */}
                            {/* Writing Style Field */}


                            {/* File Upload Section */}
                            <div>
                                <label htmlFor="file" className="block text-sm font-medium text-gray-700">
                                    Update Project Text With File
                                </label>
                                <input
                                    type="file"
                                    id="file"
                                    name="file"
                                    required
                                    className="mt-1 block w-full text-sm text-gray-500 file:border file:border-gray-300 file:rounded-md file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                                />
                            </div>

                            {/* Error Message Display */}
                            {errorMessage && (
                                <div className="text-red-600 text-sm mt-2">
                                    {errorMessage}
                                </div>
                            )}

                            {/* Submit Button */}
                            <button
                                type="submit"
                                disabled={loading || submitting}
                                className="w-48 inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                            >
                                {submitting ? (
                                    <div
                                        className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-white"></div>
                                ) : (
                                    "Update Project Text"
                                )}
                            </button>
                        </form>

                        <br/>
                        <Link href={`/project?id=${projectId}`}>
                            <button className="px-4 py-2 rounded-md shadow-sm focus:outline-none bg-blue-600 text-white">
                                Back
                            </button>
                        </Link>
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



