export interface StructuredInfo {
  names: string[];
  dates: string[];
  emails: string[];
  phones: string[];
  amounts: string[];
}

export type RiskLevel = "High" | "Medium" | "Low" | "None";

export interface PrivacyFinding {
  type: string;
  severity: Exclude<RiskLevel, "None">;
  value: string;
  masked_value: string;
}

export interface PrivacyReport {
  risk_level: RiskLevel;
  risk_score: number;
  findings: PrivacyFinding[];
  redacted_text: string;
  recommendations: string[];
}

export type DiffSegment =
  | { type: "equal"; text: string }
  | {
      type: "replace" | "insert" | "delete";
      before: string;
      after: string;
      category: string;
      reasons: string[];
    };

export interface AccuracyReport {
  segments: DiffSegment[];
  stats: {
    total_words: number;
    changed_words: number;
    change_rate: number;
    estimated_accuracy_before: number;
    estimated_accuracy_after: number;
    unresolved_issues: number;
    fixes_by_category: Record<string, number>;
    protected: Record<string, number>;
  };
}

export interface ErrorRates {
  cer: number;
  wer: number;
  character_accuracy: number;
  word_accuracy: number;
}

export interface ReferenceEvaluation {
  before: ErrorRates;
  after: ErrorRates;
  cer_improvement: number;
  wer_improvement: number;
}

export interface DocumentResult {
  document_id: string;
  filename: string;
  extracted_text: string;
  corrected_text: string;
  document_type: string;
  structured_info: StructuredInfo;
  summary: string;
  privacy: PrivacyReport;
  accuracy: AccuracyReport;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export type ExportFormat = "pdf" | "docx" | "xlsx";
