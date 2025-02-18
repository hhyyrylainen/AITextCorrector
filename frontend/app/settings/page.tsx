"use client";

import React, {useState, useEffect} from "react";

const API_MODELS_URL = "/api/ai/models";
const API_CONFIG_URL = "/api/config";

type Config = {
    selectedModel: string;
    correctionReRuns: number;
    autoSummaries: boolean;
};

// Utility function to fetch and handle responses
async function fetchJSONData<T>(url: string, errorMessage: string): Promise<T> {
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(errorMessage);
    }
    return response.json();
}

export default function AppSettings() {
    const [aiModels, setAiModels] = useState<{ name: string }[]>([]); // List of AI models from the backend; defaults to an empty array
    const [config, setConfig] = useState<Config>({
        selectedModel: "",
        correctionReRuns: 0,
        autoSummaries: false,
    }); // Current form settings
    const [initialConfig, setInitialConfig] = useState<Config>(config); // Store fetched config to reset
    const [loading, setLoading] = useState(true); // Track data loading state
    const [saving, setSaving] = useState(false); // Track save button state
    const [error, setError] = useState<string | null>(null); // Error message state

    // Fetch available models and existing configuration
    useEffect(() => {
        const fetchData = async () => {
            try {
                // Fetch AI models
                const models = await fetchJSONData<{ name: string }[]>(
                    API_MODELS_URL,
                    "Failed to fetch AI models."
                );
                setAiModels(Array.isArray(models) ? models : []);

                // Fetch configuration
                const initialConfigData = await fetchJSONData<Config>(
                    API_CONFIG_URL,
                    "Failed to fetch configuration."
                );
                setConfig(initialConfigData);
                setInitialConfig(initialConfigData);


                setError(null);
            } catch (err) {
                console.error(err);
                setError((err as Error).message || "Failed to load data.");
                setAiModels([]); // Ensure aiModels is an empty array on error
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    // Handle input changes for form fields
    const handleChange = (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const {name, value, type} = event.target;
        const checked = type === "checkbox" ? (event.target as HTMLInputElement).checked : undefined;

        setConfig((prevConfig) => ({
            ...prevConfig,
            [name]: type === "checkbox" ? checked : value,
        }));
    };

    // Save updated settings
    const handleSave = async () => {
        setSaving(true);
        try {
            const response = await fetch("/api/config", {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(config),
            });

            if (!response.ok) {
                const errorData = await response.json();
                setError(errorData.message || "Failed to save settings.");
                return;
            }

            setInitialConfig(config); // Update initial values after saving
            setError(null);
        } catch (err) {
            console.error(err);
            setError("An error occurred while saving. Please try again.");
        } finally {
            setSaving(false);
        }
    };

    // Reset form to initial values
    const handleCancel = () => {
        setConfig(initialConfig);
        setError(null);
    };

    return (
        <div className="p-8 pb-20 gap-16 font-[family-name:var(--font-geist-sans)]">
            <main className="flex flex-col gap-8 items-start max-w-2xl">
                <h1>App Settings</h1>

                {loading ? (
                    <p>Loading...</p>
                ) : error ? (
                    <div className="p-3 text-red-600 border border-red-600 bg-red-100 rounded-md">
                        {error}
                    </div>
                ) : (
                    <form className="flex flex-col gap-6 w-full">
                        {/* AI Model Dropdown */}
                        <div>
                            <label
                                htmlFor="selectedModel"
                                className="block text-sm font-medium text-gray-700"
                            >
                                Select AI Model
                            </label>
                            <select
                                id="selectedModel"
                                name="selectedModel"
                                value={config.selectedModel}
                                onChange={handleChange}
                                className="mt-1 p-2 block w-full border rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                            >
                                <option value="" disabled>
                                    Select a model
                                </option>
                                {Array.isArray(aiModels) && aiModels.map((model, index) => (
                                    <option key={index} value={model.name}>
                                        {model.name}
                                    </option>
                                ))}
                            </select>
                        </div>

                        {/* Correction Re-runs Spinbox */}
                        <div>
                            <label
                                htmlFor="correctionReRuns"
                                className="block text-sm font-medium text-gray-700"
                            >
                                Number of Correction Re-runs
                            </label>
                            <input
                                type="number"
                                id="correctionReRuns"
                                name="correctionReRuns"
                                value={config.correctionReRuns}
                                onChange={handleChange}
                                className="mt-1 p-2 block w-full border rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                                min={0}
                            />
                        </div>

                        {/* Auto Summaries Checkbox */}
                        <div className="flex items-center">
                            <input
                                type="checkbox"
                                id="autoSummaries"
                                name="autoSummaries"
                                checked={config.autoSummaries}
                                onChange={handleChange}
                                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                            />
                            <label
                                htmlFor="autoSummaries"
                                className="ml-2 block text-sm font-medium text-gray-700"
                            >
                                Automatically Create Chapter Summaries
                            </label>
                        </div>

                        {/* Action Buttons */}
                        <div className="flex gap-4">
                            <button
                                type="button"
                                onClick={handleSave}
                                className="px-4 py-2 bg-blue-600 text-white rounded-md shadow-sm hover:bg-blue-500 focus:ring-blue-500 focus:ring-offset-2 focus:outline-none"
                                disabled={saving}
                            >
                                {saving ? "Saving..." : "Save"}
                            </button>
                            <button
                                type="button"
                                onClick={handleCancel}
                                className="px-4 py-2 bg-gray-300 text-gray-700 rounded-md shadow-sm hover:bg-gray-200 focus:ring-gray-500 focus:ring-offset-2 focus:outline-none"
                                disabled={saving}
                            >
                                Cancel
                            </button>
                        </div>
                    </form>
                )}
            </main>
        </div>
    );
}
