"use client";

import { useState } from "react";
import { Copy, Check, FileText, SpellCheck, ListTree, ScrollText, ShieldCheck, Gauge } from "lucide-react";
import { DocumentResult } from "@/lib/types";
import Card from "./Card";
import PrivacyPanel from "./PrivacyPanel";
import AccuracyPanel from "./AccuracyPanel";

const TABS = [
  { label: "Extracted Text", icon: FileText },
  { label: "Corrected Text", icon: SpellCheck },
  { label: "Structured Info", icon: ListTree },
  { label: "Summary", icon: ScrollText },
  { label: "Accuracy", icon: Gauge },
  { label: "Privacy Shield", icon: ShieldCheck },
] as const;
type Tab = (typeof TABS)[number]["label"];

const BADGE_COLORS: Record<string, string> = {
  Invoice: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  Resume: "bg-violet-100 text-violet-800 dark:bg-violet-500/15 dark:text-violet-300",
  Prescription: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
  Receipt: "bg-sky-100 text-sky-800 dark:bg-sky-500/15 dark:text-sky-300",
  "ID Card": "bg-rose-100 text-rose-800 dark:bg-rose-500/15 dark:text-rose-300",
  Notes: "bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200",
  Presentation: "bg-orange-100 text-orange-800 dark:bg-orange-500/15 dark:text-orange-300",
};

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <button
      onClick={copy}
      className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-100"
    >
      {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

function TextBlock({ text }: { text: string }) {
  return (
    <div className="space-y-2">
      <div className="flex justify-end">
        <CopyButton text={text} />
      </div>
      <pre className="whitespace-pre-wrap font-sans text-sm text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-800/60 rounded-xl p-4 max-h-80 overflow-y-auto">
        {text || "—"}
      </pre>
    </div>
  );
}

function StructuredInfoGrid({ result }: { result: DocumentResult }) {
  const fields: [string, string[]][] = [
    ["Names", result.structured_info.names],
    ["Dates", result.structured_info.dates],
    ["Emails", result.structured_info.emails],
    ["Phones", result.structured_info.phones],
    ["Amounts", result.structured_info.amounts],
  ];

  return (
    <div className="grid sm:grid-cols-2 gap-4">
      {fields.map(([label, values]) => (
        <div key={label} className="bg-slate-50 dark:bg-slate-800/60 rounded-xl p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-2">
            {label}
          </p>
          {values.length > 0 ? (
            <ul className="space-y-1 text-sm text-slate-700 dark:text-slate-300">
              {values.map((value, i) => (
                <li key={i}>{value}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-400 dark:text-slate-600">None detected</p>
          )}
        </div>
      ))}
    </div>
  );
}

export default function ResultsPanel({ result }: { result: DocumentResult }) {
  const [activeTab, setActiveTab] = useState<Tab>("Corrected Text");
  const badgeColor = BADGE_COLORS[result.document_type] || BADGE_COLORS.Notes;

  return (
    <Card className="animate-fade-in">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <p className="text-sm text-slate-400 dark:text-slate-500">{result.filename}</p>
          <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100">Document Results</h2>
        </div>
        <span className={`px-3 py-1 rounded-full text-sm font-medium ${badgeColor}`}>
          {result.document_type}
        </span>
      </div>

      <div className="flex gap-1 border-b border-slate-200 dark:border-slate-800 overflow-x-auto">
        {TABS.map(({ label, icon: Icon }) => (
          <button
            key={label}
            onClick={() => setActiveTab(label)}
            className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium border-b-2 -mb-px whitespace-nowrap transition-colors ${
              activeTab === label
                ? "border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                : "border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200"
            }`}
          >
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      <div key={activeTab} className="animate-fade-in">
        {activeTab === "Extracted Text" && <TextBlock text={result.extracted_text} />}
        {activeTab === "Corrected Text" && <TextBlock text={result.corrected_text} />}
        {activeTab === "Structured Info" && <StructuredInfoGrid result={result} />}
        {activeTab === "Summary" && <TextBlock text={result.summary} />}
        {activeTab === "Accuracy" && <AccuracyPanel result={result} />}
        {activeTab === "Privacy Shield" && <PrivacyPanel report={result.privacy} filename={result.filename} />}
      </div>
    </Card>
  );
}
