"use client";

import {useEffect, useState} from "react";
import {CorrectionStatus, Paragraph} from "@/app/projectDefinitions";

type ParagraphCorrectorProps = {
    paragraph: Paragraph;
};

// A simple component for paragraph correction
export default function ParagraphCorrector({paragraph}: ParagraphCorrectorProps) {
    const [paragraphData, setParagraphData] = useState<Paragraph | null>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [generating, setGenerating] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const [isPolling, setIsPolling] = useState<boolean>(false); // Track polling state

    // Function to fetch paragraph data from the backend
    async function fetchParagraphData(partOfChapter: number, index: number) {
        try {
            const response = await fetch(`/api/chapters/${partOfChapter}/paragraphs/${index}`);
            if (!response.ok) {
                setError(`Failed to fetch paragraph: ${response.statusText}`);
                return;
            }
            const data: Paragraph = await response.json();
            setParagraphData(data);
            setError(null); // Reset any previous errors
        } catch (err) {
            console.error("Error fetching paragraph data:", err);
            setError(err instanceof Error ? err.message : "Unknown error");
        } finally {
            setLoading(false);
        }
    }

    async function generateCorrection() {
        setGenerating(true);
        try {
            const response = await fetch(
                `/api/chapters/${paragraph.partOfChapter}/paragraphs/${paragraph.index}/generateCorrection`, {
                    method: "POST",
                });
            if (!response.ok) {
                setError(`Failed to request correction generation: ${response.statusText}`);
                return;
            }

            setError(null); // Reset any previous errors

            // Succeeded so we should fetch the paragraph data again
            await fetchParagraphData(paragraph.partOfChapter, paragraph.index);

        } catch (err) {
            console.error("Error requesting corrections to paragraph data:", err);
            setError(err instanceof Error ? err.message : "Unknown error");
        } finally {
            setGenerating(false);
        }
    }

    function getBackgroundColour(paragraphData: Paragraph) {

        if (paragraphData.correctionStatus == CorrectionStatus.accepted)
            return "bg-green-100";

        if (paragraphData.correctionStatus == CorrectionStatus.reviewed)
            return "bg-blue-100";

        return "bg-gray-100";
    }

    // Polling logic for "notGenerated"
    useEffect(() => {
        let interval: NodeJS.Timeout | undefined;

        if (paragraphData?.correctionStatus === CorrectionStatus.notGenerated) {
            setIsPolling(true);
            interval = setInterval(async () => {
                try {
                    const response = await fetch(
                        `/api/chapters/${paragraph.partOfChapter}/paragraphs/${paragraph.index}`
                    );
                    if (!response.ok) {
                        // noinspection ExceptionCaughtLocallyJS
                        throw new Error("Failed to fetch paragraph updates while polling");
                    }
                    const updatedData: Paragraph = await response.json();

                    // Update paragraph data if correctionStatus has changed
                    if (updatedData.correctionStatus !== CorrectionStatus.notGenerated) {
                        setParagraphData(updatedData); // Apply the new state
                        clearInterval(interval); // Stop polling
                        setIsPolling(false);
                    }
                } catch (err) {
                    console.error("Error polling backend for updates:", err);
                    setError(err instanceof Error ? err.message : "Unknown error during polling");
                    clearInterval(interval); // Stop polling on error
                    setIsPolling(false);
                }
            }, 10000); // Poll every 10 seconds
        }

        return () => {
            if (interval) clearInterval(interval); // Cleanup interval on component unmount or correctionStatus change
        };
    }, [paragraphData?.correctionStatus, paragraph.partOfChapter, paragraph.index]);


    useEffect(() => {
        // Fetch paragraph data when the component mounts
        fetchParagraphData(paragraph.partOfChapter, paragraph.index);
    }, [paragraph.partOfChapter, paragraph.index]);

    if (loading) {
        return <div>Loading latest paragraph data...</div>;
    }

    if (error) {
        return (
            <div className={"flex flex-col items-center bg-red-100 p-4 border rounded-md mt-1 w-full"}>
                <div>Error: {error}</div>
                {/* Show a button to retry fetching the data */}
                <button className="mt-2 px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600"
                        onClick={() => fetchParagraphData(paragraph.partOfChapter, paragraph.index)}>
                    Retry
                </button>
            </div>
        );
    }

    if (!paragraphData) {
        return <div>No paragraph data found.</div>;
    }

    if (paragraphData.correctionStatus == CorrectionStatus.notGenerated) {
        return (
            <div className="bg-gray-100 p-4 border rounded-md mt-1 w-full flex flex-col items-center">
                <button className="mt-2 px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600"
                        onClick={generateCorrection} disabled={generating}>
                    {generating ? "Generating..." : "Generate Correction"}
                </button>
            </div>
        );
    }


    return (
        <div className={`${getBackgroundColour(paragraphData)} p-4 border rounded-md mt-1 w-full`}>
            <textarea
                className="w-full p-2 border border-gray-300 rounded-md"
                rows={4}
                defaultValue={paragraphData.originalText}
            />
            <button className="mt-2 px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600">
                Save Correction
            </button>
        </div>
    );
}
