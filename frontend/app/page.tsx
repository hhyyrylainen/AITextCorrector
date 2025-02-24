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
                ) : (
                    <p>No projects available.</p>
                )}
            </main>
        </div>
    );
}
