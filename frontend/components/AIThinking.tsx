"use client";

import React, { useEffect, useState } from "react";

export default function AIThinking() {
  const [isThinking, setIsThinking] = useState(false);

  const fetchAIStatus = async () => {
    try {
      const response = await fetch("/api/ai/status");
      if (response.ok) {
        const data = await response.json();
        setIsThinking(data.thinking); // Update the "thinking" state
      } else {
        console.error("Failed to fetch AI status");
      }
    } catch (err) {
      console.error("Error querying AI status:", err);
    }
  };

  useEffect(() => {
    // Fetch the initial status and set up a polling interval
    fetchAIStatus();
    const intervalId = setInterval(fetchAIStatus, 1000); // Poll every 1 second

    return () => clearInterval(intervalId); // Cleanup interval on unmount
  }, []);

  if (!isThinking) {
    return null; // Do not render anything when AI is not thinking
  }

  return (
    <div className="flex items-center justify-center space-x-2 text-white">
      <p className="text-sm font-medium">AI is processing</p>
      {/* Tailwind spinner */}
      <div className="inline-block w-4 h-4 border-2 border-t-2 border-gray-300 rounded-full animate-spin border-t-blue-500"></div>
    </div>
  );
}
