import axios from "axios";
import { DocumentResult, ExportFormat, ReferenceEvaluation, StructuredInfo } from "./types";

const api = axios.create({
  baseURL: "http://localhost:8000",
});

export async function uploadDocument(file: File): Promise<DocumentResult> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await api.post("/upload/", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

  return response.data;
}

export async function translateText(text: string, targetLang: string): Promise<string> {
  const response = await api.post("/translate/", { text, target_lang: targetLang });
  return response.data.translated_text;
}

export async function synthesizeSpeech(text: string, lang: string = "en"): Promise<Blob> {
  const response = await api.post(
    "/tts/",
    { text, lang },
    { responseType: "blob" }
  );
  return response.data;
}

export async function askQuestion(documentId: string, question: string): Promise<string> {
  const response = await api.post("/chat/", { document_id: documentId, question });
  return response.data.answer;
}

export async function exportDocument(
  format: ExportFormat,
  text: string,
  structuredInfo: StructuredInfo,
  documentType: string
): Promise<Blob> {
  const response = await api.post(
    `/export/${format}`,
    { text, structured_info: structuredInfo, document_type: documentType },
    { responseType: "blob" }
  );
  return response.data;
}

export async function downloadRedactedFile(
  filename: string,
  values: string[]
): Promise<{ blob: Blob; missed: number }> {
  const response = await api.post(
    "/privacy/redact",
    { filename, values },
    { responseType: "blob" }
  );
  return { blob: response.data, missed: Number(response.headers["x-redaction-missed"] || 0) };
}

export async function evaluateAccuracy(
  referenceText: string,
  extractedText: string,
  correctedText: string
): Promise<ReferenceEvaluation> {
  const response = await api.post("/accuracy/evaluate", {
    reference_text: referenceText,
    extracted_text: extractedText,
    corrected_text: correctedText,
  });
  return response.data;
}
