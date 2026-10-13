"use client";

import { useState } from "react";
import { Languages } from "lucide-react";
import { translateText } from "@/lib/api";
import Card from "./Card";
import Spinner from "./Spinner";

const LANGUAGES = [
  { code: "es", label: "Spanish" },
  { code: "fr", label: "French" },
  { code: "de", label: "German" },
  { code: "hi", label: "Hindi" },
  { code: "te", label: "Telugu" },
  { code: "zh-CN", label: "Chinese" },
  { code: "ar", label: "Arabic" },
  { code: "ja", label: "Japanese" },
];

export default function TranslatePanel({ text }: { text: string }) {
  const [targetLang, setTargetLang] = useState(LANGUAGES[0].code);
  const [translated, setTranslated] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleTranslate() {
    setLoading(true);
    setError(null);

    try {
      const result = await translateText(text, targetLang);
      setTranslated(result);
    } catch (err) {
      console.error(err);
      setError("Translation failed. Check your internet connection.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card icon={Languages} title="Translate">
      <div className="flex flex-wrap gap-2">
        <select
          value={targetLang}
          onChange={(e) => setTargetLang(e.target.value)}
          className="border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-lg px-3 py-2 text-sm text-slate-700 dark:text-slate-200"
        >
          {LANGUAGES.map((lang) => (
            <option key={lang.code} value={lang.code}>
              {lang.label}
            </option>
          ))}
        </select>

        <button
          onClick={handleTranslate}
          disabled={!text || loading}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg disabled:bg-slate-300 dark:disabled:bg-slate-700 hover:bg-blue-700 transition-colors"
        >
          {loading && <Spinner />}
          Translate
        </button>
      </div>

      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

      {translated && (
        <pre className="whitespace-pre-wrap font-sans text-sm text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-800/60 rounded-xl p-4 max-h-60 overflow-y-auto animate-fade-in">
          {translated}
        </pre>
      )}
    </Card>
  );
}
