// Phase 19 — application package API client.

import api from "@/services/api";

// Real structured-output calls regularly exceed the generic 30-second HTTP
// timeout. Keep ordinary API requests fast, but allow bounded completion time
// for the explicitly model-backed package actions.
export const LLM_ACTION_TIMEOUT_MS = 300_000;

export interface ApplicationPackage {
  id: string;
  application_id: string;
  job_id: string;
  route_id: string | null;
  resume_id: string | null;
  cover_letter_key: string | null;
  cover_letter_text: string | null;
  email_to: string | null;
  email_subject: string | null;
  email_body: string | null;
  attachment_keys: string[] | null;
  answers: Array<Record<string, unknown>> | null;
  language: string;
  version: number;
  content_hash: string;
  is_current: boolean;
  qa_verdict: "pass" | "warning" | "blocked" | null;
  qa_issues: Array<{ kind: string; detail: string; severity: string }> | null;
  approval_id: string | null;
  approved_at: string | null;
  send_state: "pending" | "sent" | "failed" | "unknown" | null;
  sent_at: string | null;
  message_id: string | null;
  created_at: string;
}

export interface Readiness {
  ready: boolean;
  missing: string[];
  warnings: string[];
  documents: Array<{ name: string; ok: boolean; detail: string }>;
  route: string | null;
  route_url: string | null;
  route_instructions: string | null;
  posting_quality: { signal: string; reasons: string[] };
  work_authorization: { status: string; requirements: string[]; evidence: string[] };
  package_version: number;
  content_hash: string;
  approved: boolean;
  send_state: string | null;
}

export interface SendResult {
  state: "sent" | "failed" | "unknown";
  message_id?: string | null;
  provider_response?: string | null;
  error?: string | null;
}

export const packageService = {
  getCurrent: (appId: string) =>
    api.get<ApplicationPackage | null>(`/applications/${appId}/package`).then((r) => r.data),

  create: (appId: string, data: Partial<Record<string, unknown>>) =>
    api.post<ApplicationPackage>(`/applications/${appId}/package`, data).then((r) => r.data),

  readiness: (appId: string) =>
    api.get<Readiness>(`/applications/${appId}/readiness`).then((r) => r.data),

  generateCoverLetter: (appId: string, matchSummary?: Record<string, unknown>, language = "en") =>
    api
      .post<ApplicationPackage>(`/applications/${appId}/package/cover-letter`, {
        match_summary: matchSummary ?? null,
        language,
      }, { timeout: LLM_ACTION_TIMEOUT_MS })
      .then((r) => r.data),

  generateEmail: (appId: string, language = "en") =>
    api
      .post<ApplicationPackage>(
        `/applications/${appId}/package/email`,
        { language },
        { timeout: LLM_ACTION_TIMEOUT_MS },
      )
      .then((r) => r.data),

  generateAnswers: (appId: string, questions: string[], language = "en") =>
    api
      .post<ApplicationPackage>(
        `/applications/${appId}/package/answers`,
        { questions, language },
        { timeout: LLM_ACTION_TIMEOUT_MS },
      )
      .then((r) => r.data),

  runQa: (appId: string) =>
    api
      .post<ApplicationPackage>(
        `/applications/${appId}/package/qa`,
        undefined,
        { timeout: LLM_ACTION_TIMEOUT_MS },
      )
      .then((r) => r.data),

  approve: (appId: string) =>
    api.post<ApplicationPackage>(`/applications/${appId}/package/approve`).then((r) => r.data),

  send: (appId: string) =>
    api.post<SendResult>(`/applications/${appId}/package/send`).then((r) => r.data),

  recordRouteOpened: (appId: string) =>
    api.post(`/applications/${appId}/route-opened`).then((r) => r.data),

  confirmManualSubmission: (appId: string) =>
    api.post(`/applications/${appId}/confirm-manual-submission`, { confirmed: true }).then((r) => r.data),
};
