"use client";

import React, {useState} from "react";
import {useRouter} from "next/navigation";
import Link from "next/link";

export default function CreateNew() {
    const router = useRouter(); // Next.js router for redirection
    const [error, setError] = useState<string | null>(null); // State to manage error messages
    const [writingStyle, setWritingStyle] = useState<string>(""); // State to manage the "Writing Style" field content
    const [levelOfCorrection, setLevelOfCorrection] = useState<string>("2");
    const [analysisError, setAnalysisError] = useState<string | null>(null); // State to manage errors for the embedded form
    const [loading, setLoading] = useState(false);
    const [submitting, setSubmitting] = useState(false);

    // Handles submission of the main form
    const handleMainSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        setError(null);
        setSubmitting(true);

        const formData = new FormData(event.currentTarget);

        try {
            const response = await fetch("/api/projects", {
                method: "POST",
                body: formData,
            });

            if (response.ok) {
                const data = await response.json();
                // Assume the server responds with an ID like { id: "123" }
                if (data?.id) {
                    router.push(`/project?id=${data.id}`); // Redirect to the new project page
                } else {
                    setError("An unexpected error occurred. Missing project ID.");
                }
            } else {
                // Handle server errors
                const errorData = await response.json();
                setError(errorData?.message || "Failed to create project. Please try again."); // Display server error message
            }
        } catch (error) {
            console.error("Error submitting the form:", error);
            setError("An unexpected error occurred. Please try again.");
        } finally {
            setSubmitting(false);
        }
    };

    // Handles submission of the embedded form
    const handleAnalyzeSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        setAnalysisError(null); // Reset error state for the embedded form
        setLoading(true);

        const formData = new FormData(event.currentTarget);

        try {
            const response = await fetch("/api/textAnalysis", {
                method: "POST",
                body: formData,
            });

            if (response.ok) {
                const data = await response.json();
                // Assume the server responds with an "instructions" field
                if (data?.instructions) {
                    setWritingStyle(data.instructions); // Update the "Writing Style" field content
                } else {
                    setAnalysisError("Analysis did not return any instructions.");
                }
            } else {
                const errorData = await response.json();
                setAnalysisError(errorData?.message || "Failed to analyze text style. Please try again.");
            }
        } catch (error) {
            console.error("Error submitting the analyze form:", error);
            setAnalysisError("An unexpected error occurred. Please try again.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="p-8 pb-20 gap-16 font-[family-name:var(--font-geist-sans)]">
            <main className="flex flex-col gap-8 items-start max-w-2xl">
                <h1>Setup New Project</h1>

                {/* Main Form */}
                <form
                    onSubmit={handleMainSubmit}
                    className="flex flex-col gap-4 w-full"
                    encType="multipart/form-data"
                >
                    {/* Name Input Section */}
                    <div>
                        <label htmlFor="name" className="block text-sm font-medium text-gray-700">
                            Project Name
                        </label>
                        <input
                            type="text"
                            id="name"
                            name="name"
                            required
                            placeholder="Enter your project name"
                            className="mt-1 p-2 block w-full border rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                        />
                    </div>

                    {/* "Level of Correction" Field */}
                    <div>
                        <label
                            htmlFor="levelOfCorrection"
                            className="block text-sm font-medium text-gray-700"
                        >
                            Level of Correction
                        </label>
                        <select
                            id="levelOfCorrection"
                            name="levelOfCorrection"
                            value={levelOfCorrection}
                            onChange={(e) => setLevelOfCorrection(e.target.value)}
                            required
                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                        >
                            <option value="1">Typo fixing only</option>
                            <option value="2">Slight grammar fixing</option>
                            <option value="3">Full grammar improvement</option>
                        </select>
                    </div>

                    {/* Writing Style Field */}
                    <div>
                        <label htmlFor="writingStyle" className="block text-sm font-medium text-gray-700">
                            Writing Style
                        </label>
                        <textarea
                            id="writingStyle"
                            name="writingStyle"
                            rows={8}
                            value={writingStyle} // Controlled by state
                            onChange={(e) => setWritingStyle(e.target.value)} // Update when edited manually
                            placeholder="Instructions for the corrections AI to follow styling (see below for automatic detection)"
                            className="mt-1 p-2 block w-full border rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm min-w-1"
                        ></textarea>
                    </div>

                    {/* File Upload Section */}
                    <div>
                        <label htmlFor="file" className="block text-sm font-medium text-gray-700">
                            Import Project Text File
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
                    {error && (
                        <div className="text-red-600 text-sm mt-2">
                            {error}
                        </div>
                    )}

                    {/* Submit Button */}
                    <button
                        type="submit"
                        disabled={loading || submitting}
                        className="w-48 inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                    >
                        {submitting ? (
                            <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-white"></div>
                        ) : (
                            "Create Project"
                        )}
                    </button>
                </form>

                {/* Embedded Form */}
                <form
                    onSubmit={handleAnalyzeSubmit}
                    className="flex flex-col gap-4 w-full mt-8"
                    encType="multipart/form-data"
                >
                    <h2 className="text-lg font-medium text-gray-900">Analyze Text Style</h2>
                    <p>This will allow automatically creating the text styling instructions for the above field.</p>
                    <div>
                        <label htmlFor="analysisFile" className="block text-sm font-medium text-gray-700">
                            Upload a File
                        </label>
                        <input
                            type="file"
                            id="analysisFile"
                            name="file"
                            required
                            className="mt-1 block w-full text-sm text-gray-500 file:border file:border-gray-300 file:rounded-md file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                        />
                    </div>

                    {/* Error Message for Embedded Form */}
                    {analysisError && (
                        <div className="text-red-600 text-sm mt-2">
                            {analysisError}
                        </div>
                    )}

                    {/* Submit Button for Analysis */}
                    <button
                        type="submit"
                        disabled={loading || submitting}
                        className="w-48 inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
                    >
                        {loading ? (
                            <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-white"></div>
                        ) : (
                            "Analyze Text Style"
                        )}
                    </button>
                </form>

                <p>
                    Test text extraction <Link href="/testExtraction" style={{color: "blue", textDecoration: "underline"}}>
                    here</Link> to see if there&apos;s a problem.
                </p>
            </main>
        </div>
    );
}
