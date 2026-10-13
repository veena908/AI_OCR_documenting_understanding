"use client";

import { useEffect, useRef, useState } from "react";
import { UploadCloud, File as FileIcon, X, ScanEye, SpellCheck, Tags, ListTree } from "lucide-react";
import { uploadDocument } from "@/lib/api";
import { DocumentResult } from "@/lib/types";
import Spinner from "./Spinner";

interface DropzoneProps {
  onResult: (result: DocumentResult) => void;
}

const ACCEPTED_EXTENSIONS = [
  ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp", ".gif",
  ".pdf", ".docx", ".txt",
];

const ACCEPT_ATTR = [
  "image/png", "image/jpeg", "image/bmp", "image/tiff", "image/webp", "image/gif",
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
  ...ACCEPTED_EXTENSIONS,
].join(",");

const STAGES = [
  { label: "Reading document", icon: ScanEye },
  { label: "Correcting spelling & grammar", icon: SpellCheck },
  { label: "Classifying document", icon: Tags },
  { label: "Extracting structured info & summary", icon: ListTree },
];

export default function Dropzone({ onResult }: DropzoneProps) {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [stageIndex, setStageIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!loading) return;

    setStageIndex(0);
    const interval = setInterval(() => {
      setStageIndex((prev) => Math.min(prev + 1, STAGES.length - 1));
    }, 1800);

    return () => clearInterval(interval);
  }, [loading]);

  function selectFile(selected: File | null) {
    setError(null);

    if (selected) {
      const ext = "." + selected.name.split(".").pop()?.toLowerCase();

      if (!ACCEPTED_EXTENSIONS.includes(ext)) {
        setError(`Unsupported file type "${ext}". Try an image, PDF, DOCX, or TXT file.`);
        setFile(null);
        setPreviewUrl(null);
        return;
      }
    }

    setFile(selected);
    setPreviewUrl(selected && selected.type.startsWith("image/") ? URL.createObjectURL(selected) : null);
  }

  function handleDrop(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragActive(false);
    const dropped = event.dataTransfer.files?.[0];
    if (dropped) selectFile(dropped);
  }

  async function handleUpload() {
    if (!file) return;

    setLoading(true);
    setError(null);

    try {
      const result = await uploadDocument(file);
      onResult(result);
    } catch (err) {
      console.error(err);
      setError("Upload failed. Make sure the backend is running on port 8000.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed p-10 text-center cursor-pointer transition-colors ${
          dragActive
            ? "border-blue-500 bg-blue-50 dark:bg-blue-950/30"
            : "border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/40 hover:border-blue-400 hover:bg-blue-50/50 dark:hover:bg-blue-950/20"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT_ATTR}
          className="hidden"
          onChange={(e) => selectFile(e.target.files?.[0] || null)}
        />

        {file ? (
          <div className="relative">
            {previewUrl ? (
              <img
                src={previewUrl}
                alt="Preview"
                className="max-h-48 rounded-lg border border-slate-200 dark:border-slate-700 object-contain"
              />
            ) : (
              <div className="flex flex-col items-center gap-2 px-8 py-6 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
                <FileIcon className="w-10 h-10 text-blue-600 dark:text-blue-400" />
                <p className="text-sm font-medium text-slate-700 dark:text-slate-200 max-w-[220px] truncate">
                  {file.name}
                </p>
              </div>
            )}
            <button
              onClick={(e) => {
                e.stopPropagation();
                selectFile(null);
              }}
              className="absolute -top-2 -right-2 rounded-full bg-slate-800 dark:bg-slate-700 text-white p-1 hover:bg-slate-900 dark:hover:bg-slate-600"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <>
            <div className="p-3 rounded-full bg-blue-100 dark:bg-blue-500/10">
              <UploadCloud className="w-8 h-8 text-blue-600 dark:text-blue-400" />
            </div>
            <p className="text-slate-600 dark:text-slate-300 font-medium">
              Drag & drop a document, or click to browse
            </p>
            <p className="text-slate-400 dark:text-slate-500 text-sm flex items-center gap-1">
              <FileIcon className="w-4 h-4" /> Images, PDF, Word, or TXT
            </p>
          </>
        )}
      </div>

      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

      <button
        onClick={handleUpload}
        disabled={!file || loading}
        className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 text-white font-medium rounded-xl disabled:bg-slate-300 dark:disabled:bg-slate-700 disabled:cursor-not-allowed hover:bg-blue-700 transition-colors"
      >
        {loading && <Spinner />}
        {loading ? "Processing document..." : "Upload and Extract"}
      </button>

      {loading && (
        <div className="space-y-2 animate-fade-in">
          {STAGES.map((stage, i) => {
            const Icon = stage.icon;
            const done = i < stageIndex;
            const active = i === stageIndex;

            return (
              <div
                key={stage.label}
                className={`flex items-center gap-2.5 text-sm transition-opacity ${
                  done || active
                    ? "text-slate-700 dark:text-slate-200"
                    : "text-slate-300 dark:text-slate-600"
                }`}
              >
                {active ? <Spinner className="w-3.5 h-3.5" /> : <Icon className="w-3.5 h-3.5" />}
                {stage.label}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
