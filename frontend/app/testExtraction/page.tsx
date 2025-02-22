"use client";

import React, {useState} from "react";

type Paragraph = {
    index: number;
    text: string;
    leadingSpace: number;
};

type Chapter = {
    title: string;
    paragraphs: Paragraph[];
};


export default function CreateNew() {
    const [error, setError] = useState<string | null>(null); // State to manage error messages
    const [chapters, setChapters] = useState<Chapter[]>([]);
    const [submitting, setSubmitting] = useState(false);

    const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        setError(null);
        setSubmitting(true);

        const formData = new FormData(event.currentTarget);

        try {
            const response = await fetch("/api/extractText", {
                method: "POST",
                body: formData,
            });

            if (response.ok) {
                const data = await response.json();
                setChapters(data)
            } else {
                // Handle server errors
                const errorData = await response.json();
                setError(errorData?.error || "Failed to extract text. Please try again."); // Display server error message
            }
        } catch (error) {
            console.error("Error submitting the form:", error);
            setError("An unexpected error occurred. Please try again.");
        } finally {
            setSubmitting(false);
        }
    };

    const handleCancel = async (event: React.MouseEvent<HTMLButtonElement>) => {
        event.preventDefault();
        setChapters([]);
    }

    return (
        <div className="p-8 pb-20 gap-16 font-[family-name:var(--font-geist-sans)]">
            <main className="flex flex-col gap-8 items-start max-w-2xl">
                <h1>Test Text Extraction</h1>

                {/* Main Form */}
                <form
                    onSubmit={handleSubmit}
                    className="flex flex-col gap-4 w-full"
                    encType="multipart/form-data"
                >
                    {/* File Upload Section */}
                    <div>
                        <label htmlFor="file" className="block text-sm font-medium text-gray-700">
                            Text File to Test
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
                        disabled={submitting}
                        className="px-4 py-2 bg-blue-600 text-white rounded-md shadow-sm hover:bg-blue-500 focus:ring-blue-500 focus:ring-offset-2 focus:outline-none"
                    >
                        {submitting ? (
                            <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-white"></div>
                        ) : (
                            "Submit"
                        )}
                    </button>

                    <button
                        type="button"
                        onClick={handleCancel}
                        className="px-4 py-2 bg-gray-300 text-gray-700 rounded-md shadow-sm hover:bg-gray-200 focus:ring-gray-500 focus:ring-offset-2 focus:outline-none"
                        disabled={submitting}
                    >
                        Clear
                    </button>

                    {/* Result display */}
                    <div className="max-w-2xl space-y-8">
                        {chapters.map((chapter, index) => (
                            <div key={index} className="space-y-4">
                                {/* Chapter Title */}
                                <h2 className="text-2xl font-bold text-gray-800">{chapter.title}</h2>

                                {/* Chapter Paragraphs */}
                                {chapter.paragraphs.map((paragraph) => (
                                    <p key={paragraph.index} className="text-gray-600 leading-relaxed">
                                        {paragraph.leadingSpace > 0 && (<br/>)}
                                        <span className="text-gray-400 text-sm pe-1">{paragraph.index}.</span>
                                        {paragraph.text}
                                    </p>
                                ))}
                            </div>
                        ))}
                    </div>
                </form>
            </main>
        </div>
    );
}
