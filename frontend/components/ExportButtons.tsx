"use client";

import { useState } from "react";
import { FileDown } from "lucide-react";
import { exportDocument } from "@/lib/api";
import { DocumentResult, ExportFormat } from "@/lib/types";
import Card from "./Card";
import Spinner from "./Spinner";

const FORMATS: { format: ExportFormat; label: string }[] = [
  { format: "pdf", label: "PDF" },
  { format: "docx", label: "Word" },
  { format: "xlsx", label: "Excel" },
];

export default function ExportButtons({ result }: { result: DocumentResult }) {
  const [pending, setPending] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleExport(format: ExportFormat) {
    setPending(format);
    setError(null);

    try {
      const blob = await exportDocument(
        format,
        result.corrected_text,
        result.structured_info,
        result.document_type
      );

      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `document.${format}`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
      setError("Export failed.");
    } finally {
      setPending(null);
    }
  }

  return (
    <Card icon={FileDown} title="Export">
      <div className="flex flex-wrap gap-2">
        {FORMATS.map(({ format, label }) => (
          <button
            key={format}
            onClick={() => handleExport(format)}
            disabled={pending !== null}
            className="flex items-center gap-2 px-4 py-2 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 text-sm font-medium rounded-lg disabled:opacity-50 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
          >
            {pending === format && <Spinner />}
            {label}
          </button>
        ))}
      </div>

      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
    </Card>
  );
}
