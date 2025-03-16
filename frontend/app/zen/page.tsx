"use client";

import {Suspense, useEffect, useState, useRef} from "react";
import {useSearchParams, useRouter} from "next/navigation"; // Hook to access query parameters
import Link from "next/link";

import {CorrectionStatus, Paragraph} from "@/app/projectDefinitions";
import ZenCorrector from "@components/ZenCorrector";

type StringKeyedDictionary = {
    [key: string]: number | string;
};


function Page() {
    // Access the search parameters object
    const searchParams = useSearchParams();
    const chapterId = searchParams.get("chapterId");
    const paragraphIndex = searchParams.get("paragraphIndex");

    const router = useRouter(); // Next.js router for redirection

    // State for the data we are working with
    const [paragraph, setParagraph] = useState<Paragraph | null>(null);
    const [earlierParagraphs, setEarlierParagraphs] = useState<Paragraph[] | null>(null);
    const [laterParagraphs, setLaterParagraphs] = useState<Paragraph[] | null>(null);

    const [loading, setLoading] = useState(true);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [processing, setProcessing] = useState(false);

    const [generatingCorrections, setGeneratingCorrections] = useState(false);
    const [correctionsGenerated, setCorrectionsGenerated] = useState(false);

    const correctorCenterRef = useRef<HTMLDivElement>(null);

    // Fetch the paragraph data from the backend when `chapterId` is available
    useEffect(() => {
        if (!chapterId) return; // Do nothing if `chapterId` is not yet available

        const fetchParagraphs = async () => {
            setLoading(true);
            try {
                const res = await fetch(`/api/zen/load/${chapterId}?current=${paragraphIndex}`);
                if (!res.ok) {
                    setErrorMessage("Failed to fetch paragraphs.");
                    return;
                }
                const data: Paragraph[] = await res.json();

                // Parse the actual paragraphs we want from the response
                let targetFound = false;
                const early: Paragraph[] = [];
                const later: Paragraph[] = [];

                for (const paragraph of data) {
                    if (!targetFound && paragraph.index.toString() == paragraphIndex) {
                        setParagraph(paragraph);
                        targetFound = true;
                    } else if (!targetFound) {
                        // Early paragraph
                        early.push(paragraph);
                    } else {
                        later.push(paragraph);
                    }
                }

                setEarlierParagraphs(early);
                setLaterParagraphs(later);

                if (!targetFound) {
                    setErrorMessage("Failed to find the target paragraph.");
                    setParagraph(null);
                }

            } catch (error) {
                setErrorMessage((error as Error).message || "An error occurred while fetching paragraph data.");
            } finally {
                setLoading(false);
            }
        };
        fetchParagraphs();
    }, [chapterId, paragraphIndex]); // Trigger re-fetch when chapterId changes

    // Function to generate missing corrections
    const generateCorrections = async () => {
        setGeneratingCorrections(true);
        try {
            const response = await fetch(`/api/chapters/${chapterId}/generateCorrections`, {
                method: "POST",
            });

            if (response.ok) {
                setCorrectionsGenerated(true);
            } else {
                setErrorMessage("Failed to regenerate the summary. Please try again.");
            }
        } catch {
            setErrorMessage("An error occurred while regenerating the summary. Please try again.");
        } finally {
            setGeneratingCorrections(false);
        }
    };

    const handleMove = async (backwards: boolean) => {
        setProcessing(true);
        try {
            const response = await fetch(
                `/api/zen/nextParagraph/${chapterId}?current=${paragraphIndex}&reverse=${backwards}`);

            const data: StringKeyedDictionary = await response.json();

            if (!data["next"]) {
                setErrorMessage(data["error"]?.toString() ?? "Unknown error in server next index response");
                return;
            }

            // Do nothing if we are already at the right place
            if (data["next"] == paragraphIndex)
                return;

            router.push(`/zen?chapterId=${chapterId}&paragraphIndex=${data["next"]}`);
        } catch {
            setErrorMessage("An error occurred while fetching the paragraph to switch to. Please try again.");
        } finally {
            setProcessing(false);
        }
    }

    const handleMoveNext = async () => {
        await handleMove(false);
    }

    const handleMovePrevious = async () => {
        await handleMove(true);
    }

    // Center view on the corrector when it opens
    useEffect(() => {
        if (correctorCenterRef.current) {
            // correctorCenterRef.current.scrollIntoView({behavior: "smooth", block: "center"});
            correctorCenterRef.current.scrollIntoView({behavior: "instant", block: "center"});
        }
    }, [paragraph, loading]);

    const bgColourFromState = (paragraph: Paragraph) => {
        if (paragraph.correctionStatus == CorrectionStatus.accepted) {
            return "bg-green-100";
        } else if (paragraph.correctionStatus == CorrectionStatus.rejected) {
            return "bg-red-100";
        } else if (paragraph.correctionStatus == CorrectionStatus.notRequired) {
            return "bg-blue-200";
        } else if (paragraph.correctionStatus == CorrectionStatus.reviewed) {
            return "bg-yellow-100";
        } else if (paragraph.correctionStatus == CorrectionStatus.generated) {
            return "bg-gray-100";
        } else {
            return "";
        }
    }

    const paragraphTextToShow = (paragraph: Paragraph) => {
        if (paragraph.correctionStatus == CorrectionStatus.accepted) {
            return paragraph.manuallyCorrectedText || paragraph.correctedText || "CORRECTION MISSING!";
        }

        return paragraph.originalText;
    }

    const displayParagraph = (paragraph: Paragraph) => {
        return <li key={paragraph.index} className="w-full flex flex-col items-center gap-2">
            {paragraph.leadingSpace > 0 && (<div className="h-10"/>)}
            <div className="flex items-center gap-2">
                <span
                    className={`font-semibold min-w-8 rounded p-1 ${bgColourFromState(paragraph)} text-center`}>
                    {paragraph.index}.
                </span>
                <span className="text-gray-700 ms-2"
                      style={{maxWidth: "32rem", width: "32rem"}}>
                    {paragraphTextToShow(paragraph).split("\n").map((line, index) => (
                        <span key={index}>
                            {line}
                            <br/>
                        </span>
                    ))}
                </span>

                <Link href={`/zen?chapterId=${chapterId}&paragraphIndex=${paragraph.index}`}
                      className={"text-blue-600 hover:underline"}>
                    Jump Here
                </Link>
            </div>
        </li>
    }

    if (chapterId == null) {
        return <p>No chapter and paragraph found. Please go back to the chapter page.</p>
    }

    return (
        <div className="pb-8 gap-16 w-full font-[family-name:var(--font-geist-sans)]">
            <main className="flex flex-col gap-8 items-center">

                {/* Spacing to allow scrolling to work */}
                <div style={{height: "400px"}}/>

                {/* Error message */}
                {errorMessage && (
                    <div className="text-red-600 bg-red-100 p-2 rounded-md">
                        {errorMessage}
                    </div>
                )}

                <div className={"max-w-3xl"}>
                    <ul>
                        {earlierParagraphs && earlierParagraphs.map(displayParagraph)}
                    </ul>
                </div>

                <Link href={`/chapter?id=${chapterId}`}
                      className="text-blue-600 hover:underline absolute left-1 top-14">
                    Return to Chapter
                </Link>

                {/* Main paragraph */}
                {/* Min height is used to keep scroll offsets more reasonable*/}
                <div className={"flex items-center gap-4 w-full"} style={{minHeight: "400px"}} ref={correctorCenterRef}>
                    {loading ? (
                        <p className={"text-center w-full"}>
                            Loading paragraph data...
                        </p>
                    ) : paragraph ? (
                            <>
                                <div className={"flex items-center w-full"}>
                                    {paragraph.correctionStatus == CorrectionStatus.notGenerated ? (
                                        <>
                                            <p>
                                                This paragraph is missing corrections. Press the button below to trigger
                                                generation for all missing paragraphs in this chapter. The generation
                                                will take many minutes. So refresh after some time.
                                            </p>

                                            <button
                                                type="button"
                                                onClick={generateCorrections}
                                                className={`px-4 py-2 rounded-md shadow-sm focus:outline-none ${
                                                    generatingCorrections
                                                        ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                                                        : "bg-gray-300 text-gray-700 hover:bg-gray-200 " +
                                                        "focus:ring-gray-500 focus:ring-offset-2"
                                                }`}
                                                disabled={generatingCorrections || correctionsGenerated}
                                            >
                                                {correctionsGenerated ? "Corrections Generating..." :
                                                    "Generate Missing Corrections"}
                                            </button>
                                        </>
                                    ) : (
                                        <ZenCorrector paragraph={paragraph} onMoveToNextAction={handleMoveNext}
                                                      onMoveToPreviousAction={handleMovePrevious}
                                                      disableButtons={processing}/>
                                    )}
                                </div>
                            </>
                        ) :
                        (
                            <p>No chapter paragraphs found. Please go back to the chapter page.</p>
                        )
                    }
                </div>

                <div className={"max-w-3xl"}>
                    <ul>
                        {laterParagraphs && laterParagraphs.map(displayParagraph)}
                    </ul>
                </div>

                {/* Spacing to allow scrolling to work */}
                <div style={{height: "772px"}}/>
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
