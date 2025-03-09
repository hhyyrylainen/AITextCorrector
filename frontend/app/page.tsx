"use client";

import {useState, useEffect} from "react";
import Link from "next/link";

type Project = {
    id: string;
    name: string;
};

export default function Home() {
    // State for storing project data and loading/error flags
    const [projects, setProjects] = useState<Project[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [correctionsGenerated, setCorrectionsGenerated] = useState(false);
    const [generatingCorrections, setGeneratingCorrections] = useState(false);
    const [generalMessage, setGeneralMessage] = useState<string | null>(null);

    // Fetch project data from the backend
    useEffect(() => {
        const fetchProjects = async () => {
            try {
                const res = await fetch("/api/projects");
                if (!res.ok) {
                    setError("Failed to fetch projects.");
                    return;
                }
                const data: Project[] = await res.json();
                setProjects(data);
            } catch (err) {
                setError((err as Error).message || "An error occurred.");
            } finally {
                setLoading(false);
            }
        };

        fetchProjects();
    }, []);

    const requestCorrectionGeneration = async () => {
        // Reset error message and set the button state
        setGeneralMessage(null);
        setGeneratingCorrections(true);

        try {
            // Send a POST request to the backend
            const response = await fetch(`/api/projects/generateCorrections`, {
                method: "POST",
            });

            // Check if the request succeeded
            if (response.ok) {
                setCorrectionsGenerated(true); // Update state on success
                setGeneralMessage("Corrections generation has started. It will take a really long time, up to hours.");
            } else {
                // Handle non-2xx responses
                setGeneralMessage(
                    "Failed to request correction generation. Please try again later."
                );
            }
        } catch {
            // Handle network or unexpected errors
            setGeneralMessage("An unexpected error occurred. Please try again.");
        } finally {
            setGeneratingCorrections(false);
        }
    };

    if (loading) {
        // Show a loading indicator while fetching
        return <p className="p-8">Loading projects...</p>;
    }

    if (error) {
        // Display error message if the API call fails
        return (
            <p className="p-8 text-red-600 bg-red-100 p-2 rounded-md">
                {error}
            </p>
        );
    }

    return (
        <div className="p-8 pb-20 gap-16 font-[family-name:var(--font-geist-sans)]">
            <main className="flex flex-col gap-8 items-start max-w-2xl">
                <h1 className="text-2xl font-bold mb-4">Projects</h1>
                {projects.length > 0 ? (
                    <div>
                        <ul className="list-inside list-disc text-sm text-left">
                            {projects.map((project) => (
                                <li key={project.id} className="max-w-full break-words">
                                    <Link
                                        href={`/project?id=${project.id}`}
                                        className="text-blue-600 hover:underline"
                                    >
                                        {project.name}
                                    </Link>
                                </li>
                            ))}
                        </ul>

                        <br/>

                        {generalMessage && (
                            <div className="bg-gray-200 p-2 rounded-md w-full">
                                {generalMessage}
                            </div>
                        )}

                        <br/>

                        <button
                            type="button"
                            onClick={requestCorrectionGeneration}
                            className={`px-4 py-2 rounded-md shadow-sm focus:outline-none ${
                                generatingCorrections || correctionsGenerated
                                    ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                                    : "bg-gray-300 text-gray-700 hover:bg-gray-200 focus:ring-gray-500 focus:ring-offset-2"
                            }`}
                            disabled={generatingCorrections || correctionsGenerated} // Disable button when processing
                        >
                            {correctionsGenerated ? "Corrections Generating..." : "Generate All Missing Corrections"}
                        </button>
                    </div>
                ) : (
                    <p>No projects available.</p>
                )}
            </main>
        </div>
    );
}
