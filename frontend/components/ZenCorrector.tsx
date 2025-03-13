"use client";

import {useEffect, useRef, useState} from "react";

import {DiffEditor} from '@monaco-editor/react';
import {editor} from "monaco-editor";

import {CorrectionStatus, Paragraph} from "@/app/projectDefinitions";
import IStandaloneDiffEditor = editor.IStandaloneDiffEditor;

type ZenCorrectorCorrectorProps = {
    paragraph: Paragraph;
    onMoveToNextAction: () => Promise<void>;
    onMoveToPreviousAction: () => Promise<void>;
};

// A simple component for paragraph correction
export default function ZenCorrector({
                                         paragraph,
                                         onMoveToNextAction,
                                         onMoveToPreviousAction
                                     }: ZenCorrectorCorrectorProps) {

    const [error, setError] = useState<string | null>(null);

    const [textValue, setTextValue] = useState("");

    const [isProcessing, setIsProcessing] = useState<boolean>(false);

    const diffEditorRef = useRef<IStandaloneDiffEditor>(null);

    useEffect(() => {
        if (paragraph) {
            setTextValue(paragraph.originalText); // Update state when data changes
        }
    }, [paragraph]);

    const hasCorrectedText = paragraph && (paragraph.correctedText || paragraph.manuallyCorrectedText);

    async function saveCorrection() {
        setIsProcessing(true);
        try {

            const editedText = hasCorrectedText ? handleGetEditedContent() : textValue;

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

            // We just saved the data, but for user understandability we stay on the current paragraph
            window.location.reload();

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
            let editedText = hasCorrectedText ? handleGetEditedContent() : textValue;

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

            // Done so move to next
            // This doesn't await to make things more responsive feeling
            onMoveToNextAction().then(_ => {
            });

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

            // Discard data and move to next
            onMoveToNextAction().then(_ => {
            });

        } catch (err) {
            console.error("Error requesting rejection of paragraph data:", err);
            setError(err instanceof Error ? err.message : "Unknown error");
        } finally {
            setIsProcessing(false);
        }
    }

    // Callback to capture the Monaco Diff Editor instance
    const handleEditorDidMount = (editor: IStandaloneDiffEditor) => {
        diffEditorRef.current = editor;

        const modifiedEditor = editor.getModifiedEditor(); // This grabs the "new text" editor
        modifiedEditor.focus(); // Focus the new text field
    };

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

    // Function to read the content of the "original" and "modified" models
    const handleGetEditedContent = () => {
        if (diffEditorRef.current) {
            return diffEditorRef.current.getModel()?.modified?.getValue();
        }

        return null;
    };

    // Handle the change in textarea
    const handleChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
        setTextValue(event.target.value); // Update the state as the user types
    };

    // Keybindings for the buttons
    useEffect(() => {
        const handleKeyDown = async (event: KeyboardEvent) => {
            if (event.altKey && event.key === "ArrowLeft") {
                await onMoveToPreviousAction();
            }
            if (event.altKey && event.key === "ArrowRight") {
                await onMoveToNextAction();
            }
            if (event.altKey && event.key === "a") {
                await approveAndSave();
            }
            if (event.altKey && (event.key === "r" || event.key === "c" || event.key === "x")) {
                await reject();
            }
        };

        // Attach event listener when the component mounts
        window.addEventListener("keydown", handleKeyDown);

        // Clean up the event listener when the component unmounts
        return () => {
            window.removeEventListener("keydown", handleKeyDown);
        };
    }, []); // Empty dependency array ensures this runs only on mount and unmount


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

    if (error) {
        return (
            <div className={"flex flex-col items-center bg-red-100 p-4 border rounded-md mt-1 w-full"}>
                <div>Error: {error}</div>
                <button className="mt-2 px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600"
                        onClick={() => window.location.reload()}>
                    Refresh
                </button>
            </div>
        );
    }

    if (paragraph.correctionStatus == CorrectionStatus.notGenerated) {
        return (
            <div className="bg-red-300 p-4 border rounded-md mt-1 w-full flex flex-col items-center">
                <p>Zen editor doesn't support not generated status. The parent component should have handled this...</p>
            </div>
        );
    }

    return (
        <div className={`${getBackgroundColour(paragraph)} p-4 border rounded-md mt-1 w-full`}>

            {hasCorrectedText ? (
                <div style={{height: '300px', width: '100%'}}>
                    <DiffEditor
                        height="100%"
                        theme="vs-light" // Use "vs-light" or "vs-dark"
                        language="plaintext" // Set the appropriate language (e.g., "javascript", "python", etc.)
                        originalLanguage="plaintext"
                        original={paragraph.originalText}
                        modified={paragraph.manuallyCorrectedText ? paragraph.manuallyCorrectedText : paragraph.correctedText}
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
                        value={textValue}
                        onChange={handleChange}
                    />
                    <p>{"AI found nothing to correct (edit above for a manual correction)"}</p>
                </>
            )}

            <div className={"flex flex-row justify-center"}>

                <button
                    disabled={isProcessing}
                    onClick={onMoveToPreviousAction}
                    className="mt-2 px-4 py-2 mx-1 bg-gray-400 text-white rounded-md hover:bg-gray-600">
                    Previous (doesn't save)
                </button>

                <button
                    disabled={isProcessing}
                    onClick={approveAndSave}
                    className="mt-2 px-4 py-2 mx-1 bg-green-600 text-white hover:bg-green-800 rounded-md  focus:ring-offset-2">
                    Approve
                </button>

                {hasCorrectedText &&
                    <button
                        disabled={isProcessing}
                        onClick={reject}
                        className="mt-2 px-4 py-2 mx-1 bg-red-500 text-white hover:bg-red-700 rounded-md  focus:ring-offset-2">
                        Reject
                    </button>
                }

                <button
                    disabled={isProcessing}
                    onClick={saveCorrection}
                    className="mt-2 px-4 py-2 mx-1 bg-blue-500 text-white rounded-md hover:bg-blue-600">
                    Save Correction
                </button>

                <button
                    disabled={isProcessing}
                    onClick={onMoveToNextAction}
                    className="mt-2 px-4 py-2 mx-1 bg-gray-400 text-white rounded-md hover:bg-gray-600">
                    Next (skip)
                </button>
            </div>
        </div>
    );
}
