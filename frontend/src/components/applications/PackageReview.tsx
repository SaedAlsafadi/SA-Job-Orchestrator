// Phase 19 — application package review ("What exactly am I about to submit?").
// Shows JOB → MATCH → CV → COVER LETTER → EMAIL → ANSWERS → QA → WARNINGS → APPROVAL.

import { useCallback, useEffect, useState } from "react";

import {
  packageService,
  type ApplicationPackage,
  type Readiness,
  type SendResult,
} from "@/services/packageService";
import { listResumes } from "@/services/resumeService";
import type { Resume } from "@/types/resume";

const card: React.CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--r-lg)",
  padding: 20,
  marginBottom: 16,
  boxShadow: "var(--shadow-1)",
};
const btn: React.CSSProperties = {
  height: 34,
  padding: "0 14px",
  borderRadius: "var(--r-md)",
  border: "1px solid var(--border)",
  background: "var(--surface-2)",
  color: "var(--text-2)",
  font: "700 12px/1 var(--font)",
  cursor: "pointer",
};
const btnPrimary: React.CSSProperties = {
  ...btn,
  background: "var(--accent)",
  borderColor: "var(--accent)",
  color: "var(--accent-ink)",
};
const mono: React.CSSProperties = { font: "600 12px/1.5 var(--mono)", whiteSpace: "pre-wrap" };

type Props = {
  applicationId: string;
  jobId?: string;
  job?: { title?: string | null; company?: string | null; location?: string | null };
  language?: string;
  matchSummary?: Record<string, unknown>;
  onStatus?: (msg: string, kind: "success" | "error" | "info") => void;
};

export function applicationRouteMessage(route: string | null | undefined): string {
  switch ((route ?? '').toUpperCase()) {
    case 'EMAIL': return 'Application package ready to email after your approval.';
    case 'WORKABLE': return 'Application package ready — continue in Workable.';
    case 'GREENHOUSE': return 'Application package ready — continue in Greenhouse.';
    case 'LEVER': return 'Application package ready — continue in Lever.';
    case 'COMPANY_WEBSITE': return 'Application package ready — continue on the company website.';
    case 'LINKEDIN': return 'Application package ready — continue on LinkedIn.';
    case 'MANUAL': return 'Review the package and follow the application instructions manually.';
    default: return 'Select an application route before submission.';
  }
}

// Part H: dev-only mock AI. Opt in with localStorage.aa_mock_ai = "1" while in
// Vite dev mode; fills package components with deterministic fixtures instead
// of calling the LLM endpoints. Production routing is untouched.
const MOCK_COVER_LETTER = [
  "Dear Hiring Manager,",
  "I am excited to apply for this role. My experience delivering AI-enabled business solutions aligns directly with the requirements outlined in the posting, and the attached tailored CV details the matching evidence.",
  "I would welcome the opportunity to discuss how my background can contribute to your team.",
  "Sincerely,",
].join("\n\n");

const MOCK_EMAIL_BODY = [
  "Dear Hiring Manager,",
  "Please find attached my tailored CV and cover letter for the position. My background in AI-enabled solutions and full-stack delivery matches the requirements described.",
  "I look forward to hearing from you.",
  "Kind regards,",
].join("\n\n");

const MOCK_ANSWERS = [
  { question: "Years of relevant experience?", answer: "See CV - detailed in the experience section.", status: "ANSWERED", confidence: 0.9 },
  { question: "Work authorization?", answer: "", status: "UNKNOWN", confidence: 0 },
];

const MOCK_QUESTION_PROMPTS = [
  "Years of relevant experience?",
  "Work authorization?",
];

const MOCK_QA_ISSUES = [
  { kind: "work_authorization", detail: "Confirm work-authorization requirements before submitting.", severity: "warning" },
];

export function PackageReview({ applicationId, jobId, job, language = "en", matchSummary, onStatus }: Props) {
  const mockAi = import.meta.env.DEV && (
    localStorage.getItem("aa_mock_ai") === "1" ||
    new URLSearchParams(window.location.search).get("mockAi") === "1"
  );
  const [pkg, setPkg] = useState<ApplicationPackage | null>(null);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [selectedResume, setSelectedResume] = useState<Resume | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [sendResult, setSendResult] = useState<SendResult | null>(null);
  const [manuallySubmitted, setManuallySubmitted] = useState(false);
  // Dev mock QA (Part H): client-side deterministic findings, never persisted.
  const [mockQa, setMockQa] = useState<{
    verdict: "pass" | "warning";
    issues: Array<{ kind: string; detail: string; severity: string }>;
  } | null>(null);

  const notify = useCallback(
    (msg: string, kind: "success" | "error" | "info" = "info") => onStatus?.(msg, kind),
    [onStatus],
  );

  const refresh = useCallback(async () => {
    try {
      const [p, r, resumeList] = await Promise.all([
        packageService.getCurrent(applicationId),
        packageService.readiness(applicationId).catch(() => null),
        listResumes().catch(() => null),
      ]);
      setPkg(p);
      setReadiness(r);
      const resumes = resumeList?.items ?? [];
      setSelectedResume(
        resumes.find((resume) => resume.id === p?.resume_id) ??
        resumes
          .filter((resume) => resume.job_id === jobId && resume.type === "tailored")
          .sort((a, b) => b.created_at.localeCompare(a.created_at))[0] ??
        null,
      );
    } catch {
      setPkg(null);
      setReadiness(null);
    }
  }, [applicationId, jobId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const run = async (step: string, fn: () => Promise<unknown>, okMsg: string) => {
    setBusy(step);
    try {
      const result = await fn();
      if (step === "send") setSendResult(result as SendResult);
      if (["create", "cover", "email", "answers"].includes(step)) setMockQa(null);
      await refresh();
      notify(okMsg, "success");
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        (err as Error).message;
      notify(detail || "Action failed", "error");
    } finally {
      setBusy(null);
    }
  };

  // Phase 19.5: auto-attach the latest tailored resume for this job so the
  // package is complete without the user hunting for IDs.
  const createWithResume = async () => {
    let resume = selectedResume;
    if (!resume && jobId) {
      try {
        const all = await listResumes();
        resume = all.items
          .filter((candidate) => candidate.job_id === jobId && candidate.type === "tailored")
          .sort((a, b) => b.created_at.localeCompare(a.created_at))[0] ?? null;
      } catch {
        /* resume attach is best-effort */
      }
    }
    return packageService.create(applicationId, {
      language,
      resume_id: resume?.id,
    });
  };

  if (!pkg) {
    return (
      <div style={card}>
        <h3 style={{ margin: "0 0 8px" }}>Application package</h3>
        <p style={{ color: "var(--text-2)", fontSize: 13, margin: "0 0 16px" }}>
          Assemble everything you are about to submit: CV, cover letter, email, and answers —
          locked into one reviewable package.
        </p>
        {mockAi && (
          <p style={{ color: "var(--warning, #b8860b)", fontSize: 12, margin: "0 0 12px" }}>
            DEV MOCK AI active — generation actions use deterministic fixtures.
          </p>
        )}
        <button
          style={btnPrimary}
          disabled={busy !== null}
          onClick={() => run("create", createWithResume, "Package created")}
        >
          {busy === "create" ? "Creating…" : "Create application package"}
        </button>
      </div>
    );
  }

  const approved = Boolean(pkg.approval_id);
  const qaVerdict = mockQa?.verdict ?? pkg.qa_verdict;
  const qaIssues = mockQa?.issues ?? pkg.qa_issues ?? [];
  const blocked = qaVerdict === "blocked";
  const canApprove = Boolean(readiness?.ready && qaVerdict && !approved && !blocked);
  const isEmailRoute = readiness?.route?.toUpperCase() === "EMAIL";
  const routeType = readiness?.route?.toUpperCase();
  const isExternalRoute = Boolean(routeType && routeType !== "EMAIL");
  const canSend = approved && isEmailRoute && pkg.send_state !== "sent";
  const rawScore = matchSummary?.score ?? matchSummary?.total_score ?? matchSummary?.match_score;
  const matchScore = typeof rawScore === "number"
    ? `${Math.round(rawScore <= 1 ? rawScore * 100 : rawScore)}%`
    : "Not scored";

  return (
    <div dir="auto">
      <div style={card}>
        <div style={{ color: "var(--text-3)", font: "700 11px/1 var(--font)", textTransform: "uppercase" }}>
          Review application
        </div>
        <h2 style={{ margin: "8px 0 4px", font: "800 20px/1.2 var(--font)" }}>
          {job?.title || "Application package"}
        </h2>
        <div style={{ color: "var(--text-2)", fontSize: 13 }}>
          {[job?.company, job?.location].filter(Boolean).join(" · ") || "Job details retained with this package"}
        </div>
        <div style={{ marginTop: 14, display: "flex", gap: 24, flexWrap: "wrap", fontSize: 13 }}>
          <div><strong>Match:</strong> {matchScore}</div>
          <div><strong>Selected tailored CV:</strong> {selectedResume?.name ?? pkg.resume_id ?? "Missing"}</div>
        </div>
      </div>

      {/* Readiness summary */}
      <div style={card}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ margin: 0 }}>
            {approved && isExternalRoute ? "READY TO APPLY" : readiness?.ready ? "APPLICATION READY" : "NOT READY YET"}
            <span style={{ marginLeft: 10, font: "600 11px/1 var(--mono)", color: "var(--text-3)" }}>
              v{pkg.version} · {pkg.content_hash.slice(0, 10)}
            </span>
          </h3>
          <span style={{ font: "700 11px/1 var(--font)", color: "var(--text-3)" }}>
            QA: {qaVerdict ?? "not run"}
          </span>
        </div>

        <div style={{ marginTop: 12, fontSize: 13 }}>
          <strong>Approval:</strong>{" "}
          {approved
            ? `Approved for version ${pkg.version} (${pkg.content_hash.slice(0, 10)})`
            : `Awaiting approval for version ${pkg.version}`}
        </div>

        {readiness && (
          <>
            <div style={{ marginTop: 12, fontSize: 13 }}>
              <div><strong>Route:</strong> {readiness.route ?? "—"}</div>
              <div style={{ marginTop: 4, color: 'var(--text-2)' }}>{applicationRouteMessage(readiness.route)}</div>
              {readiness.route_instructions && <div style={{ marginTop: 4, color: 'var(--text-3)' }}>{readiness.route_instructions}</div>}
              <div>
                <strong>Posting:</strong> {readiness.posting_quality.signal.replace(/_/g, " ")}
                {" · "}
                <strong>Work auth:</strong> {readiness.work_authorization.status}
              </div>
            </div>

            <div style={{ marginTop: 10, fontSize: 13 }}>
              {readiness.documents.map((d) => (
                <div key={d.name}>{d.ok ? "✓" : "✗"} {d.name} — {d.detail}</div>
              ))}
            </div>

            {readiness.missing.length > 0 && (
              <div style={{ marginTop: 10, fontSize: 13, color: "var(--danger, #c0392b)" }}>
                Missing: {readiness.missing.join(", ")}
              </div>
            )}
            {readiness.warnings.length > 0 && (
              <div style={{ marginTop: 10, fontSize: 13, color: "var(--warning, #b8860b)" }}>
                Warnings: {readiness.warnings.join(" · ")}
              </div>
            )}
          </>
        )}
      </div>

      {/* Route-aware package actions and email compose. */}
      <div style={card}>
        <h3 style={{ margin: "0 0 12px" }}>{isEmailRoute ? "Application email" : "Application actions"}</h3>
        {isEmailRoute ? (
          <div style={mono}>
            <div><strong>TO:</strong> {pkg.email_to ?? "—"}</div>
            <div><strong>SUBJECT:</strong> {pkg.email_subject ?? "—"}</div>
            <div style={{ marginTop: 8 }}><strong>BODY:</strong>{"\n"}{pkg.email_body ?? "—"}</div>
            <div style={{ marginTop: 8 }}><strong>ATTACHMENTS:</strong> {(pkg.attachment_keys ?? []).join(", ") || "—"}</div>
          </div>
        ) : (
          <div style={{ color: "var(--text-2)", fontSize: 13 }}>
            This route does not require an application email. Review the package, then continue manually using the verified route.
          </div>
        )}
        <div style={{ display: "flex", gap: 8, marginTop: 14, flexWrap: "wrap" }}>
          <button style={btn} disabled={busy !== null}
            onClick={() => run("cover", () => (
              mockAi
                ? packageService.create(applicationId, { cover_letter_text: MOCK_COVER_LETTER, language })
                : packageService.generateCoverLetter(applicationId, matchSummary, language)
            ), "Cover letter generated")}>
            {busy === "cover" ? "Generating…" : pkg.cover_letter_text ? "Regenerate cover letter" : "Generate cover letter"}
          </button>
          {isEmailRoute && <button style={btn} disabled={busy !== null}
            onClick={() => run("email", () => (
              mockAi
                ? packageService.create(applicationId, {
                    email_to: pkg.email_to || "hiring@example-company.com",
                    email_subject: "Application - see attached CV and cover letter",
                    email_body: MOCK_EMAIL_BODY,
                    language,
                  })
                : packageService.generateEmail(applicationId, language)
            ), "Email generated")}>
            {busy === "email" ? "Generating…" : pkg.email_body ? "Regenerate email" : "Generate email"}
          </button>}
          <button style={btn} disabled={busy !== null}
            onClick={() => run("answers", () => (
              mockAi
                ? packageService.create(applicationId, { answers: MOCK_ANSWERS, language })
                : packageService.generateAnswers(applicationId, MOCK_QUESTION_PROMPTS, language)
            ), "Answers generated")}>
            {busy === "answers" ? "Generating…" : (pkg.answers?.length ? "Regenerate answers" : "Generate answers")}
          </button>
          <button style={btn} disabled={busy !== null}
            onClick={() => run("qa", async () => {
              if (mockAi) {
                setMockQa({ verdict: "warning", issues: MOCK_QA_ISSUES });
                return;
              }
              return packageService.runQa(applicationId);
            }, "QA completed")}>
            {busy === "qa" ? "Running QA…" : "Run QA"}
          </button>
          <button style={btnPrimary} disabled={!canApprove || busy !== null}
            onClick={() => run("approve", () => packageService.approve(applicationId), "Approved — this exact version is locked")}>
            {busy === "approve" ? "Approving…" : approved ? "Approved ✓" : "Approve package"}
          </button>
          {mockAi ? (
            <span style={{ alignSelf: "center", color: "var(--text-3)", fontSize: 12 }}>
              Review-only mock mode — sending is disabled
            </span>
          ) : isEmailRoute ? (
            <button style={btnPrimary} disabled={!canSend || busy !== null}
              onClick={() => run("send", () => packageService.send(applicationId), "Email sent")}>
              {busy === "send" ? "Sending…" : pkg.send_state === "sent" ? "Sent ✓" : "Send email"}
            </button>
          ) : approved && isExternalRoute && !manuallySubmitted ? (
            <>
              {readiness?.route_url && (
                <button style={btnPrimary} disabled={busy !== null} onClick={() => {
                  window.open(readiness.route_url!, "_blank", "noopener,noreferrer");
                  void packageService.recordRouteOpened(applicationId);
                }}>
                  {routeType === "COMPANY_WEBSITE" ? "Open Company Application" : "Open Application"}
                </button>
              )}
              {routeType === "MANUAL" && <span style={{ alignSelf: "center", fontSize: 12 }}>{readiness?.route_instructions || "Follow the manual application instructions."}</span>}
              <button style={btn} disabled={busy !== null} onClick={() => {
                if (!window.confirm("Confirm that you submitted this application on the employer's website.")) return;
                void run("confirm", async () => {
                  const result = await packageService.confirmManualSubmission(applicationId);
                  setManuallySubmitted(true);
                  return result;
                }, "Marked applied — user-confirmed manual submission");
              }}>Mark as Submitted</button>
            </>
          ) : manuallySubmitted ? (
            <span style={{ alignSelf: "center", color: "var(--success, #2e7d32)", fontSize: 12 }}>
              Applied — user-confirmed manual submission (not system-verified)
            </span>
          ) : null}
        </div>

        {sendResult && (
          <div style={{ marginTop: 12, font: "600 12px/1.5 var(--mono)", color: sendResult.state === "sent" ? "var(--success, #2e7d32)" : "var(--danger, #c0392b)" }}>
            {sendResult.state.toUpperCase()}
            {sendResult.message_id ? ` · Message-ID: ${sendResult.message_id}` : ""}
            {sendResult.provider_response ? ` · ${sendResult.provider_response}` : ""}
          </div>
        )}
      </div>

      {/* Cover letter review */}
      {pkg.cover_letter_text && (
        <div style={card}>
          <h3 style={{ margin: "0 0 12px" }}>Cover letter</h3>
          <div dir="auto" style={mono}>{pkg.cover_letter_text}</div>
        </div>
      )}

      <div style={card}>
        <h3 style={{ margin: "0 0 12px" }}>Application answers</h3>
        {(pkg.answers ?? []).length === 0 ? (
          <div style={{ color: "var(--text-3)", fontSize: 13 }}>No application questions have been answered.</div>
        ) : (
          (pkg.answers ?? []).map((answer, idx) => (
            <div key={idx} style={{ marginBottom: 12, fontSize: 13 }}>
              <strong>{String(answer.question ?? `Question ${idx + 1}`)}</strong>
              <div style={{ marginTop: 4 }}>{String(answer.answer || "Unknown — requires review")}</div>
              <div style={{ marginTop: 3, color: "var(--text-3)", fontSize: 11 }}>
                {String(answer.status ?? "UNKNOWN")}
              </div>
            </div>
          ))
        )}
      </div>

      {/* QA issues */}
      <div style={card}>
        <h3 style={{ margin: "0 0 12px" }}>QA findings</h3>
        {qaIssues.length > 0 ? (
          qaIssues.map((i, idx) => (
            <div key={idx} style={{ fontSize: 13, marginBottom: 6 }}>
              <strong style={{ textTransform: "uppercase" }}>{i.severity}</strong> · {i.kind}: {i.detail}
            </div>
          ))
        ) : (
          <div style={{ color: "var(--text-3)", fontSize: 13 }}>Run QA to check this exact package version.</div>
        )}
      </div>
    </div>
  );
}
