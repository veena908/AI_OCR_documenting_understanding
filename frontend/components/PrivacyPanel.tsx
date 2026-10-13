"use client";

import { useState } from "react";
import { Check, Copy, Download, Eye, EyeOff, FileLock2, ShieldAlert, ShieldCheck } from "lucide-react";
import { downloadRedactedFile } from "@/lib/api";
import { PrivacyReport, RiskLevel } from "@/lib/types";
import Spinner from "./Spinner";

const RISK_STYLES: Record<RiskLevel, { box: string; bar: string; label: string }> = {
  High: {
    box: "bg-rose-50 border-rose-200 text-rose-800 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-300",
    bar: "bg-rose-500",
    label: "High risk - do not share this document as-is",
  },
  Medium: {
    box: "bg-amber-50 border-amber-200 text-amber-800 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-300",
    bar: "bg-amber-500",
    label: "Medium risk - review before sharing",
  },
  Low: {
    box: "bg-sky-50 border-sky-200 text-sky-800 dark:bg-sky-500/10 dark:border-sky-500/30 dark:text-sky-300",
    bar: "bg-sky-500",
    label: "Low risk - contains basic contact details",
  },
  None: {
    box: "bg-emerald-50 border-emerald-200 text-emerald-800 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-300",
    bar: "bg-emerald-500",
    label: "No sensitive data detected - safe to share",
  },
};

const SEVERITY_BADGE: Record<string, string> = {
  High: "bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300",
  Medium: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  Low: "bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
};

export default function PrivacyPanel({ report, filename }: { report: PrivacyReport; filename: string }) {
  const [showRedacted, setShowRedacted] = useState(false);
  const [copied, setCopied] = useState(false);
  const [redacting, setRedacting] = useState(false);
  const [fileStatus, setFileStatus] = useState<{ ok: boolean; message: string } | null>(null);
  const extension = (filename.match(/\.([^.]+)$/)?.[1] || "file").toUpperCase();
  const style = RISK_STYLES[report.risk_level];
  const RiskIcon = report.risk_level === "None" ? ShieldCheck : ShieldAlert;

  async function copyRedacted() {
    await navigator.clipboard.writeText(report.redacted_text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  function downloadRedacted() {
    const blob = new Blob([report.redacted_text], { type: "text/plain;charset=utf-8" });
    saveBlob(blob, `${filename.replace(/\.[^.]+$/, "")}_redacted.txt`);
  }

  function saveBlob(blob: Blob, name: string) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function downloadOriginalFormat() {
    setRedacting(true);
    setFileStatus(null);

    try {
      const values = report.findings.map((finding) => finding.value);
      const { blob, missed } = await downloadRedactedFile(filename, values);
      saveBlob(blob, filename.replace(/(\.[^.]+)?$/, "_redacted$1"));
      setFileStatus(
        missed > 0
          ? { ok: false, message: `${missed} item${missed === 1 ? "" : "s"} could not be located in the file - please review it before sharing.` }
          : { ok: true, message: "All detected items were blacked out in the file." }
      );
    } catch (err) {
      console.error(err);
      setFileStatus({ ok: false, message: "Could not create the redacted file." });
    } finally {
      setRedacting(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className={`border rounded-xl p-4 space-y-3 ${style.box}`}>
        <div className="flex items-center gap-3">
          <RiskIcon className="w-6 h-6 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="font-semibold">{style.label}</p>
            <p className="text-xs opacity-80">
              {report.findings.length} sensitive item{report.findings.length === 1 ? "" : "s"} found · scanned
              locally, nothing left your machine
            </p>
          </div>
          <span className="text-2xl font-bold tabular-nums">{report.risk_score}</span>
        </div>
        <div className="h-2 rounded-full bg-black/10 dark:bg-white/10 overflow-hidden">
          <div className={`h-full ${style.bar} transition-all`} style={{ width: `${report.risk_score}%` }} />
        </div>
      </div>

      {report.findings.length > 0 && (
        <>
          <div className="bg-slate-50 dark:bg-slate-800/60 rounded-xl p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-2">
              Detected Data
            </p>
            <ul className="divide-y divide-slate-200 dark:divide-slate-700">
              {report.findings.map((finding, i) => (
                <li key={i} className="flex items-center justify-between gap-3 py-2 text-sm">
                  <span className="text-slate-700 dark:text-slate-300">{finding.type}</span>
                  <span className="flex items-center gap-2 min-w-0">
                    <code className="font-mono text-xs text-slate-500 dark:text-slate-400 truncate">
                      {finding.masked_value}
                    </code>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${SEVERITY_BADGE[finding.severity]}`}>
                      {finding.severity}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div className="bg-slate-50 dark:bg-slate-800/60 rounded-xl p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-2">
              Recommendations
            </p>
            <ul className="list-disc pl-5 space-y-1 text-sm text-slate-700 dark:text-slate-300">
              {report.recommendations.map((tip, i) => (
                <li key={i}>{tip}</li>
              ))}
            </ul>
          </div>

          <div className="space-y-2">
            <button
              onClick={downloadOriginalFormat}
              disabled={redacting}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg disabled:opacity-60 hover:bg-blue-700 transition-colors"
            >
              {redacting ? <Spinner /> : <FileLock2 className="w-4 h-4" />}
              {redacting ? "Redacting..." : `Download redacted ${extension} (same layout)`}
            </button>
            {fileStatus && (
              <p
                className={`text-xs ${
                  fileStatus.ok ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"
                }`}
              >
                {fileStatus.message}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <button
                onClick={() => setShowRedacted((v) => !v)}
                className="flex items-center gap-1.5 text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline"
              >
                {showRedacted ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                {showRedacted ? "Hide redacted copy" : "Show safe-to-share redacted copy"}
              </button>
              <div className="flex items-center gap-3">
                <button
                  onClick={copyRedacted}
                  className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-100"
                >
                  {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                  {copied ? "Copied" : "Copy"}
                </button>
                <button
                  onClick={downloadRedacted}
                  className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-100"
                >
                  <Download className="w-3.5 h-3.5" />
                  Download .txt
                </button>
              </div>
            </div>
            {showRedacted && (
              <pre className="whitespace-pre-wrap font-sans text-sm text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-800/60 rounded-xl p-4 max-h-80 overflow-y-auto animate-fade-in">
                {report.redacted_text || "—"}
              </pre>
            )}
          </div>
        </>
      )}
    </div>
  );
}
