"use client";

import { useState } from "react";
import { ScanText, UploadCloud } from "lucide-react";
import Card from "@/components/Card";
import Dropzone from "@/components/Dropzone";
import ResultsPanel from "@/components/ResultsPanel";
import TranslatePanel from "@/components/TranslatePanel";
import TtsButton from "@/components/TtsButton";
import ChatPanel from "@/components/ChatPanel";
import ExportButtons from "@/components/ExportButtons";
import ThemeToggle from "@/components/ThemeToggle";
import { DocumentResult } from "@/lib/types";

export default function Home() {
  const [result, setResult] = useState<DocumentResult | null>(null);

  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900">
      <header className="sticky top-0 z-10 backdrop-blur bg-white/80 dark:bg-slate-950/80 border-b border-slate-200 dark:border-slate-800">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-gradient-to-br from-blue-600 to-indigo-600 text-white rounded-xl p-2">
              <ScanText className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-base font-bold text-slate-800 dark:text-slate-100 leading-tight">
                AI OCR Document Understanding
              </h1>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Extract, correct, translate, and understand your documents
              </p>
            </div>
          </div>
          <ThemeToggle />
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-4 py-8 grid lg:grid-cols-[1fr_360px] gap-6 items-start">
        <div className="space-y-6 min-w-0">
          <Card icon={UploadCloud} title="Upload Document">
            <Dropzone onResult={setResult} />
          </Card>

          {result ? (
            <ResultsPanel result={result} />
          ) : (
            <div className="text-center py-16 text-slate-400 dark:text-slate-600">
              <ScanText className="w-10 h-10 mx-auto mb-3 opacity-40" />
              <p className="text-sm">Upload a document to see extracted results here.</p>
            </div>
          )}
        </div>

        <div className="space-y-6 lg:sticky lg:top-20">
          {result ? (
            <>
              <TranslatePanel text={result.corrected_text} />
              <TtsButton text={result.corrected_text} />
              <ChatPanel documentId={result.document_id} />
              <ExportButtons result={result} />
            </>
          ) : (
            <Card className="opacity-60">
              <p className="text-sm text-slate-400 dark:text-slate-600 text-center py-6">
                Translation, text-to-speech, chat, and export tools will appear here once you upload a document.
              </p>
            </Card>
          )}
        </div>
      </div>
    </main>
  );
}
