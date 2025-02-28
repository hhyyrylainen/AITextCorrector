"use client";

import {useEffect, useState, useRef} from "react";
import {DiffEditor} from '@monaco-editor/react';

import {CorrectionStatus, Paragraph} from "@/app/projectDefinitions";
import {editor} from "monaco-editor";
import IStandaloneDiffEditor = editor.IStandaloneDiffEditor;

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

    const [isProcessing, setIsProcessing] = useState<boolean>(false);

    const diffEditorRef = useRef<IStandaloneDiffEditor>(null);

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

    async function clearData() {
        setIsProcessing(true);
        try {
            const response = await fetch(
                `/api/chapters/${paragraph.partOfChapter}/paragraphs/${paragraph.index}/clear`, {
                    method: "POST",
                });
            if (!response.ok) {
                setError(`Failed to request paragraph data clearing: ${response.statusText}`);
                return;
            }

            setError(null); // Reset any previous errors

            // Succeeded so we should fetch the paragraph data again
            await fetchParagraphData(paragraph.partOfChapter, paragraph.index);

        } catch (err) {
            console.error("Error requesting clearing of paragraph data:", err);
            setError(err instanceof Error ? err.message : "Unknown error");
        } finally {
            setIsProcessing(false);
        }
    }

    async function saveCorrection() {
        setIsProcessing(true);
        try {
            const editedText = handleGetEditedContent();

            if (!editedText) {
                setError("No text to save");
                return;
            }

            const response = await fetch(
                `/api/chapters/${paragraph.partOfChapter}/paragraphs/${paragraph.index}/saveManual`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        correctedText: editedText,
                    }),
                });
            if (!response.ok) {
                setError(`Failed to request save of paragraph: ${response.statusText}`);
                return;
            }

            setError(null); // Reset any previous errors

            // Fetch updated state again
            await fetchParagraphData(paragraph.partOfChapter, paragraph.index);

        } catch (err) {
            console.error("Error requesting save of paragraph data:", err);
            setError(err instanceof Error ? err.message : "Unknown error");
        } finally {
            setIsProcessing(false);
        }
    }

    async function approveAndSave() {
        setIsProcessing(true);
        try {
            let editedText = handleGetEditedContent();

            if (!editedText)
                editedText = null;

            const response = await fetch(
                `/api/chapters/${paragraph.partOfChapter}/paragraphs/${paragraph.index}/approve`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        correctedText: editedText,
                    }),
                });
            if (!response.ok) {
                setError(`Failed to request approval of paragraph: ${response.statusText}`);
                return;
            }

            setError(null); // Reset any previous errors

            // Fetch updated state again
            await fetchParagraphData(paragraph.partOfChapter, paragraph.index);

        } catch (err) {
            console.error("Error requesting approval of paragraph data:", err);
            setError(err instanceof Error ? err.message : "Unknown error");
        } finally {
            setIsProcessing(false);
        }
    }

    async function reject() {
        setIsProcessing(true);
        try {
            const response = await fetch(
                `/api/chapters/${paragraph.partOfChapter}/paragraphs/${paragraph.index}/reject`, {
                    method: "POST",
                });
            if (!response.ok) {
                setError(`Failed to request rejection of paragraph: ${response.statusText}`);
                return;
            }

            setError(null); // Reset any previous errors

            // In case there was any pending edit, just update the state here

            await fetchParagraphData(paragraph.partOfChapter, paragraph.index);

            setParagraphData((prevState) => {
                // Whenever the button is available to press, prevState should be fine to mutate
                if (!prevState)
                    throw new Error("Unexpected state (prevState is null)");

                return {
                    ...prevState,
                    correctionStatus: CorrectionStatus.rejected
                };
            });

        } catch (err) {
            console.error("Error requesting approval of paragraph data:", err);
            setError(err instanceof Error ? err.message : "Unknown error");
        } finally {
            setIsProcessing(false);
        }
    }

    // Callback to capture the Monaco Diff Editor instance
    const handleEditorDidMount = (editor: IStandaloneDiffEditor) => {
        diffEditorRef.current = editor;
    };

    // Function to read the content of the "original" and "modified" models
    const handleGetEditedContent = () => {
        if (diffEditorRef.current) {
            const modifiedText = diffEditorRef.current.getModel()?.modified?.getValue();

            console.log(modifiedText);

            return modifiedText;
        }

        return null;
    };

    function getBackgroundColour(paragraphData: Paragraph) {

        if (paragraphData.correctionStatus == CorrectionStatus.accepted)
            return "bg-green-100";

        if (paragraphData.correctionStatus == CorrectionStatus.reviewed)
            return "bg-yellow-100";

        if (paragraphData.correctionStatus == CorrectionStatus.notRequired)
            return "bg-blue-200";

        if (paragraphData.correctionStatus == CorrectionStatus.rejected)
            return "bg-red-200";

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

    // TODO: this seems to not work when this component transitions to an error state and the monaco editor will print
    // an error
    useEffect(() => {
        // Cleanup logic when the component is unmounted
        return () => {
            if (diffEditorRef.current) {
                // Dispose of the editor and its associated models
                // Note that originally this was before the model disposes
                diffEditorRef.current.dispose(); // Dispose of the editor instance

                /*const models = diffEditorRef.current.getModel();
                if (models) {
                    models.original.dispose(); // Dispose of the "original" model
                    models.modified.dispose(); // Dispose of the "modified" model
                }*/

                diffEditorRef.current = null;  // Clear the reference
            }
        };
    }, []);

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

            {paragraphData.correctedText ? (
                <div style={{height: '300px', width: '100%'}}>
                    <DiffEditor
                        height="100%"
                        theme="vs-light" // Use "vs-light" or "vs-dark"
                        language="plaintext" // Set the appropriate language (e.g., "javascript", "python", etc.)
                        originalLanguage="plaintext"
                        original={paragraphData.originalText}
                        modified={paragraphData.manuallyCorrectedText ? paragraphData.manuallyCorrectedText : paragraphData.correctedText}
                        options={{
                            wordWrap: "on",
                            diffWordWrap: "on",
                            readOnly: false,
                            originalEditable: false,
                            renderSideBySide: true, // Show side-by-side diff (set false for inline diff)
                            automaticLayout: true, // Automatically adjust layout on resize
                            minimap: {enabled: false},
                            renderOverviewRuler: false,
                            useInlineViewWhenSpaceIsLimited: false, // Makes wordwrap work
                            // renderWhitespace: "all",
                            renderWhitespace: "boundary",
                        }}
                        onMount={handleEditorDidMount} // Capture editor instance
                    />
                </div>
            ) : (
                <>
                    <textarea
                        disabled={isProcessing}
                        className="w-full p-2 border border-gray-300 rounded-md"
                        rows={4}
                        defaultValue={paragraphData.originalText}
                    />
                    <p>{"AI found nothing to correct (TODO: allow manual editing here)"}</p>
                </>
            )}

            <button
                disabled={isProcessing || generating}
                onClick={approveAndSave}
                className="mt-2 px-4 py-2 mx-1 bg-green-600 text-white hover:bg-green-800 rounded-md  focus:ring-offset-2">
                Approve
            </button>

            <button
                disabled={isProcessing || generating}
                onClick={reject}
                className="mt-2 px-4 py-2 mx-1 bg-red-500 text-white hover:bg-red-700 rounded-md  focus:ring-offset-2">
                Reject
            </button>

            <button
                disabled={isProcessing || generating}
                onClick={saveCorrection}
                className="mt-2 px-4 py-2 mx-1 bg-blue-500 text-white rounded-md hover:bg-blue-600">
                Save Correction
            </button>

            <button
                disabled={isProcessing || generating}
                onClick={generateCorrection}
                className="mt-2 px-4 py-2 mx-1 bg-gray-300 text-gray-700 hover:bg-gray-200 rounded-md  focus:ring-offset-2">
                {generating ? "Regenerating..." : "Regenerate Correction"}
            </button>

            <button
                disabled={isProcessing || generating}
                onClick={clearData}
                className="mt-2 px-4 py-2 mx-1 bg-gray-300 text-red-700 hover:bg-gray-200 rounded-md  focus:ring-offset-2">
                Clear Correction Data
            </button>
        </div>
    );
}
