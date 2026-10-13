"use client";

import { useState } from "react";
import { Volume2 } from "lucide-react";
import { synthesizeSpeech } from "@/lib/api";
import Card from "./Card";
import Spinner from "./Spinner";

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "hi", label: "Hindi" },
  { code: "te", label: "Telugu" },
];

export default function TtsButton({ text }: { text: string }) {
  const [lang, setLang] = useState(LANGUAGES[0].code);
  const [loading, setLoading] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleListen() {
    setLoading(true);
    setError(null);

    try {
      const blob = await synthesizeSpeech(text, lang);
      setAudioUrl(URL.createObjectURL(blob));
    } catch (err) {
      console.error(err);
      setError("Text-to-speech failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card icon={Volume2} title="Listen">
      <div className="flex flex-wrap gap-2">
        <select
          value={lang}
          onChange={(e) => setLang(e.target.value)}
          className="border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-lg px-3 py-2 text-sm text-slate-700 dark:text-slate-200"
        >
          {LANGUAGES.map((l) => (
            <option key={l.code} value={l.code}>
              {l.label}
            </option>
          ))}
        </select>

        <button
          onClick={handleListen}
          disabled={!text || loading}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg disabled:bg-slate-300 dark:disabled:bg-slate-700 hover:bg-blue-700 transition-colors"
        >
          {loading && <Spinner />}
          {loading ? "Generating audio..." : "Play as speech"}
        </button>
      </div>

      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

      {audioUrl && <audio controls src={audioUrl} className="w-full animate-fade-in" />}
    </Card>
  );
}
