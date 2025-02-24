import { Chapter, Paragraph } from "@/app/projectDefinitions";

type ParagraphCorrectorProps = {
  paragraph: Paragraph;
};

// A simple component for paragraph correction
export default function ParagraphCorrector({ paragraph }: ParagraphCorrectorProps) {
  return (
    <div className="bg-gray-100 p-4 border rounded-md mt-1">
      <textarea
        className="w-full p-2 border border-gray-300 rounded-md"
        rows={4}
        defaultValue={paragraph.originalText}
      />
      <button className="mt-2 px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600">
        Save Correction
      </button>
    </div>
  );
}
