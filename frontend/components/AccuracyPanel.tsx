"use client";

import { useState } from "react";
import { ArrowRight, FlaskConical, ShieldCheck } from "lucide-react";
import { evaluateAccuracy } from "@/lib/api";
import { DiffSegment, DocumentResult, ReferenceEvaluation } from "@/lib/types";
import Spinner from "./Spinner";

type ChangeSegment = Exclude<DiffSegment, { type: "equal" }>;
type View = "Inline" | "Side by side";

const CATEGORY_COLORS: Record<string, string> = {
  Spelling: "bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300",
  Typo: "bg-orange-100 text-orange-700 dark:bg-orange-500/15 dark:text-orange-300",
  Grammar: "bg-violet-100 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300",
  Punctuation: "bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
  Style: "bg-teal-100 text-teal-700 dark:bg-teal-500/15 dark:text-teal-300",
  Cleanup: "bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200",
};

const DEL_CLASS = "bg-rose-100 text-rose-700 line-through decoration-rose-500 dark:bg-rose-500/20 dark:text-rose-300 rounded px-0.5";
const INS_CLASS = "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-300 rounded px-0.5";

function categoryClass(category: string) {
  return CATEGORY_COLORS[category] || CATEGORY_COLORS.Cleanup;
}

function tooltip(segment: ChangeSegment) {
  return `${segment.category}: ${segment.reasons.join(" / ")}`;
}

function StatTile({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="bg-slate-50 dark:bg-slate-800/60 rounded-xl p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-2">{label}</p>
      {children}
    </div>
  );
}

function Chips({ counts, empty }: { counts: Record<string, number>; empty: string }) {
  const entries = Object.entries(counts);
  if (entries.length === 0) return <p className="text-sm text-slate-400 dark:text-slate-600">{empty}</p>;

  return (
    <div className="flex flex-wrap gap-1.5">
      {entries.map(([name, count]) => (
        <span key={name} className={`px-2 py-0.5 rounded-full text-xs font-medium ${categoryClass(name)}`}>
          {count} {name}
        </span>
      ))}
    </div>
  );
}

function InlineDiff({ segments }: { segments: DiffSegment[] }) {
  return (
    <>
      {segments.map((segment, i) =>
        segment.type === "equal" ? (
          <span key={i}>{segment.text}</span>
        ) : (
          <span key={i} title={tooltip(segment)} className="cursor-help">
            {segment.before && <del className={DEL_CLASS}>{segment.before.trimEnd()}</del>}
            {segment.before && segment.after && " "}
            {segment.after && <ins className={`${INS_CLASS} no-underline`}>{segment.after.trimEnd()}</ins>}
            {/* keep the original spacing/line break after the change */}
            {(segment.after || segment.before).match(/\s*$/)?.[0]}
          </span>
        )
      )}
    </>
  );
}

function SideDiff({ segments, side }: { segments: DiffSegment[]; side: "before" | "after" }) {
  return (
    <>
      {segments.map((segment, i) => {
        if (segment.type === "equal") return <span key={i}>{segment.text}</span>;
        const text = segment[side];
        if (!text) return null;
        return (
          <span key={i} title={tooltip(segment)} className={`cursor-help ${side === "before" ? DEL_CLASS : INS_CLASS}`}>
            {text}
          </span>
        );
      })}
    </>
  );
}

function ReferenceCheck({ result }: { result: DocumentResult }) {
  const [reference, setReference] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [evaluation, setEvaluation] = useState<ReferenceEvaluation | null>(null);

  async function handleEvaluate() {
    setLoading(true);
    setError(null);
    try {
      setEvaluation(await evaluateAccuracy(reference, result.extracted_text, result.corrected_text));
    } catch (err: unknown) {
      console.error(err);
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      setError(detail || "Evaluation failed.");
    } finally {
      setLoading(false);
    }
  }

  const rows: { label: string; key: keyof ReferenceEvaluation["before"]; lowerIsBetter: boolean }[] = [
    { label: "Character Error Rate (CER)", key: "cer", lowerIsBetter: true },
    { label: "Word Error Rate (WER)", key: "wer", lowerIsBetter: true },
    { label: "Character Accuracy", key: "character_accuracy", lowerIsBetter: false },
    { label: "Word Accuracy", key: "word_accuracy", lowerIsBetter: false },
  ];

  return (
    <div className="bg-slate-50 dark:bg-slate-800/60 rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-2">
        <FlaskConical className="w-4 h-4 text-blue-600 dark:text-blue-400" />
        <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">Measure real accuracy</p>
      </div>
      <p className="text-xs text-slate-500 dark:text-slate-400">
        Paste the exact true text of this document (typed by hand) to compute standard OCR metrics for the raw OCR output
        and the corrected version.
      </p>
      <textarea
        value={reference}
        onChange={(e) => setReference(e.target.value)}
        rows={4}
        placeholder="Paste the ground-truth text here..."
        className="w-full border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 rounded-lg px-3 py-2 text-sm"
      />
      <button
        onClick={handleEvaluate}
        disabled={!reference.trim() || loading}
        className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg disabled:bg-slate-300 dark:disabled:bg-slate-700 hover:bg-blue-700 transition-colors"
      >
        {loading && <Spinner />}
        Evaluate
      </button>
      {error && <p className="text-xs text-rose-600 dark:text-rose-400">{error}</p>}

      {evaluation && (
        <div className="space-y-2 animate-fade-in">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">
                  <th className="py-2 pr-3 font-semibold">Metric</th>
                  <th className="py-2 px-3 font-semibold text-right">Raw OCR</th>
                  <th className="py-2 pl-3 font-semibold text-right">Corrected</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-700 text-slate-700 dark:text-slate-300">
                {rows.map(({ label, key, lowerIsBetter }) => {
                  const before = evaluation.before[key];
                  const after = evaluation.after[key];
                  const better = lowerIsBetter ? after < before : after > before;
                  const worse = lowerIsBetter ? after > before : after < before;
                  return (
                    <tr key={key}>
                      <td className="py-2 pr-3">{label}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{before}%</td>
                      <td
                        className={`py-2 pl-3 text-right tabular-nums font-semibold ${
                          better ? "text-emerald-600 dark:text-emerald-400" : worse ? "text-rose-600 dark:text-rose-400" : ""
                        }`}
                      >
                        {after}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="text-sm text-slate-700 dark:text-slate-200">
            Correction reduced word errors by{" "}
            <span className="font-semibold">{evaluation.wer_improvement}%</span> and character errors by{" "}
            <span className="font-semibold">{evaluation.cer_improvement}%</span>.
          </p>
        </div>
      )}
    </div>
  );
}

export default function AccuracyPanel({ result }: { result: DocumentResult }) {
  const [view, setView] = useState<View>("Inline");
  const { segments, stats } = result.accuracy;
  const changes = segments.filter((s): s is ChangeSegment => s.type !== "equal");
  const protectedTotal = Object.values(stats.protected).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-4">
      <div className="grid sm:grid-cols-2 gap-4">
        <StatTile label="Estimated accuracy">
          <div className="flex items-center gap-2 text-2xl font-bold tabular-nums">
            <span className="text-slate-500 dark:text-slate-400">{stats.estimated_accuracy_before}%</span>
            <ArrowRight className="w-5 h-5 text-slate-400" />
            <span className="text-emerald-600 dark:text-emerald-400">{stats.estimated_accuracy_after}%</span>
          </div>
          <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
            Raw OCR → corrected · {stats.unresolved_issues} issue{stats.unresolved_issues === 1 ? "" : "s"} still flagged
          </p>
        </StatTile>
        <StatTile label="Words corrected">
          <p className="text-2xl font-bold tabular-nums text-slate-800 dark:text-slate-100">
            {stats.changed_words}
            <span className="text-base font-medium text-slate-400"> / {stats.total_words}</span>
          </p>
          <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">{stats.change_rate}% of the OCR text was fixed</p>
        </StatTile>
        <StatTile label="Fixes by type">
          <Chips counts={stats.fixes_by_category} empty="No fixes were needed" />
        </StatTile>
        <StatTile label="Protected from auto-correct">
          <div className="flex items-start gap-2">
            <ShieldCheck className="w-4 h-4 mt-0.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
            <Chips counts={stats.protected} empty="Nothing needed protecting" />
          </div>
          {protectedTotal > 0 && (
            <p className="text-xs text-slate-400 dark:text-slate-500 mt-2">
              Names, IDs and emails are kept exactly as scanned instead of being "fixed" into dictionary words.
            </p>
          )}
        </StatTile>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
            Before vs after correction
          </p>
          <div className="flex rounded-lg bg-slate-100 dark:bg-slate-800 p-0.5 text-xs font-medium">
            {(["Inline", "Side by side"] as View[]).map((option) => (
              <button
                key={option}
                onClick={() => setView(option)}
                className={`px-3 py-1 rounded-md transition-colors ${
                  view === option
                    ? "bg-white dark:bg-slate-700 text-slate-800 dark:text-slate-100 shadow-sm"
                    : "text-slate-500 dark:text-slate-400"
                }`}
              >
                {option}
              </button>
            ))}
          </div>
        </div>

        {changes.length === 0 && (
          <p className="text-sm text-emerald-600 dark:text-emerald-400">
            The OCR text needed no corrections.
          </p>
        )}

        {view === "Inline" ? (
          <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-800/60 rounded-xl p-4 max-h-80 overflow-y-auto">
            <InlineDiff segments={segments} />
          </pre>
        ) : (
          <div className="grid sm:grid-cols-2 gap-3">
            {(["before", "after"] as const).map((side) => (
              <div key={side} className="min-w-0">
                <p className="text-xs text-slate-500 dark:text-slate-400 mb-1">
                  {side === "before" ? "Raw OCR" : "Corrected"}
                </p>
                <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-800/60 rounded-xl p-4 max-h-80 overflow-y-auto">
                  <SideDiff segments={segments} side={side} />
                </pre>
              </div>
            ))}
          </div>
        )}
      </div>

      {changes.length > 0 && (
        <div className="bg-slate-50 dark:bg-slate-800/60 rounded-xl p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-2">
            Change log ({changes.length})
          </p>
          <ul className="divide-y divide-slate-200 dark:divide-slate-700 max-h-64 overflow-y-auto">
            {changes.map((change, i) => (
              <li key={i} className="py-2 text-sm space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={DEL_CLASS}>{change.before.trim() || "∅"}</span>
                  <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                  <span className={INS_CLASS}>{change.after.trim() || "∅"}</span>
                  <span className={`ml-auto px-2 py-0.5 rounded-full text-xs font-medium ${categoryClass(change.category)}`}>
                    {change.category}
                  </span>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400">{change.reasons.join(" · ")}</p>
              </li>
            ))}
          </ul>
        </div>
      )}

      <ReferenceCheck result={result} />
    </div>
  );
}
