"use client";

import { useState, useEffect } from "react";
import { Paragraph } from "@/app/projectDefinitions";

type ParagraphCorrectorProps = {
  paragraph: Paragraph;
};

// A simple component for paragraph correction
export default function ParagraphCorrector({ paragraph }: ParagraphCorrectorProps) {
  const [paragraphData, setParagraphData] = useState<Paragraph | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

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

  useEffect(() => {
    // Fetch paragraph data when the component mounts
    fetchParagraphData(paragraph.partOfChapter, paragraph.index);
  }, [paragraph.partOfChapter, paragraph.index]);

  if (loading) {
    return <div>Loading latest paragraph data...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  if (!paragraphData) {
    return <div>No paragraph data found.</div>;
  }

  return (
    <div className="bg-gray-100 p-4 border rounded-md mt-1 w-full">
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
