/**
 * Client-side tailoring preview merge.
 *
 * Mirrors the deterministic merge logic in backend/app/services/tailoring_merge.py.
 * This allows the CV Tailoring Workbench to show a live draft preview as the user
 * accepts/rejects changes WITHOUT any backend calls or PDF generation.
 *
 * The preview is ALWAYS labeled "DRAFT" until finalized on the backend.
 */

import type { CVTailoringChange } from '@/services/tailoringService';

/** Parsed structured resume data (mirrors TailoredResumeData from backend). */
export interface StructuredResume {
  raw_text?: string;
  name?: string;
  email?: string;
  phone?: string;
  location?: string;
  linkedin?: string;
  github?: string;
  summary?: string;
  skills?: string[];
  experience?: ExperienceEntry[];
  projects?: ProjectEntry[];
  education?: EducationEntry[];
  certifications?: string[];
}

export interface ExperienceEntry {
  title?: string;
  company?: string;
  duration?: string;
  description?: string;
  [key: string]: unknown;
}

export interface ProjectEntry {
  name?: string;
  description?: string;
  tech?: string;
  [key: string]: unknown;
}

export interface EducationEntry {
  degree?: string;
  institution?: string;
  year?: string;
  [key: string]: unknown;
}

/**
 * Parse resume content_text into a StructuredResume.
 * Tries JSON first (tailored CVs store JSON), falls back to plain text extraction.
 */
export function parseResumeContent(contentText: string | null | undefined): StructuredResume | null {
  if (!contentText?.trim()) return null;

  // Try JSON parse (tailored CVs store model_dump_json())
  try {
    const parsed = JSON.parse(contentText);
    if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
      return parsed as StructuredResume;
    }
  } catch {
    // Not JSON — fall through to plain text extraction
  }

  return extractStructuredFromPlainText(contentText);
}

/**
 * Simple section extraction from plain-text resume.
 * Finds headings and captures content beneath them.
 */
function extractStructuredFromPlainText(text: string): StructuredResume {
  const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
  if (lines.length === 0) return {};

  const result: StructuredResume = {};

  // Heuristic: first non-empty line is likely the name
  result.name = lines[0];

  // Look for email/phone in first few lines
  for (const line of lines.slice(0, 5)) {
    if (!result.email && /\S+@\S+\.\S+/.test(line)) {
      const match = line.match(/[\w.+-]+@[\w.-]+\.\w+/);
      if (match) result.email = match[0];
    }
    if (!result.phone && /[+\d][\d\s\-()]{7,}/.test(line)) {
      const match = line.match(/[+\d][\d\s\-()]{7,}/);
      if (match) result.phone = match[0].trim();
    }
  }

  // Section detection — common resume section headings
  const SECTION_PATTERNS: Record<keyof StructuredResume, RegExp> = {
    summary: /^(summary|objective|professional\s+summary|profile|about)/i,
    experience: /^(experience|work\s+experience|employment|professional\s+experience)/i,
    education: /^(education|academic|qualifications)/i,
    skills: /^(skills|technical\s+skills|core\s+competencies|competencies)/i,
    projects: /^(projects|personal\s+projects|key\s+projects)/i,
    certifications: /^(certifications?|licenses?|credentials?)/i,
  } as any;

  let currentSection: string | null = null;
  const sectionContent: Record<string, string[]> = {};

  for (const line of lines.slice(1)) {
    // Check if this line is a section heading
    let matched = false;
    for (const [section, pattern] of Object.entries(SECTION_PATTERNS)) {
      if (pattern.test(line) && line.length < 60) {
        currentSection = section;
        sectionContent[section] = [];
        matched = true;
        break;
      }
    }
    if (!matched && currentSection) {
      if (!sectionContent[currentSection]) sectionContent[currentSection] = [];
      sectionContent[currentSection]!.push(line);
    }
  }

  if (sectionContent.summary) result.summary = sectionContent.summary.join(' ');
  if (sectionContent.skills) {
    result.skills = sectionContent.skills
      .flatMap(l => l.split(/[,;|]/))
      .map(s => s.replace(/^[-•*]\s*/, '').trim())
      .filter(Boolean);
  }
  if (sectionContent.experience) {
    result.experience = [{ description: sectionContent.experience.join('\n') }];
  }
  if (sectionContent.education) {
    result.education = [{ degree: sectionContent.education.join(' ') }];
  }
  if (sectionContent.certifications) {
    result.certifications = sectionContent.certifications
      .map(l => l.replace(/^[-•*]\s*/, '').trim())
      .filter(Boolean);
  }

  const isStructured = result.summary || result.skills || result.experience || result.education || result.certifications;
  if (!isStructured) {
    result.raw_text = text;
  }

  return result;
}

/**
 * Apply a single tailoring change to a structured resume dict (in-place mutation of a clone).
 * Mirrors the Python apply_change() in tailoring_merge.py.
 */
function resolveTarget(obj: any, path: string): [any, string | number] {
  const parts = path.split(/\.|\[/).map(p => p.replace(']', ''));
  let current = obj;
  let parent: any = null;
  let lastKey: string | number = '';

  for (let i = 0; i < parts.length; i++) {
    const part = parts[i];
    if (!part) continue;
    const isLast = i === parts.length - 1;
    parent = current;
    lastKey = /^\d+$/.test(part) ? parseInt(part, 10) : part;

    if (isLast) break;
    current = current[lastKey];
    if (current == null) return [null, lastKey];
  }

  return [parent, lastKey];
}

function applyChange(doc: any, target: string, changeType: string, newValue: any): void {
  const [parent, key] = resolveTarget(doc, target);
  if (parent == null) return;

  if (changeType === 'add') {
    if (Array.isArray(parent)) {
      const idx = typeof key === 'number' ? key : parent.length;
      parent.splice(idx, 0, newValue);
    } else {
      parent[key] = newValue;
    }
  } else if (changeType === 'modify') {
    parent[key] = newValue;
  } else if (changeType === 'remove') {
    if (Array.isArray(parent) && typeof key === 'number') {
      parent.splice(key, 1);
    } else {
      delete parent[key];
    }
  }
}

/**
 * Merge accepted tailoring changes onto a base StructuredResume.
 * Returns a NEW object — does not mutate the input.
 * Mirrors merge_tailoring_changes() from the backend.
 */
export function mergeTailoringChanges(
  base: StructuredResume,
  changes: CVTailoringChange[],
): StructuredResume {
  const doc = JSON.parse(JSON.stringify(base)); // deep clone

  const accepted = changes.filter(c => c.user_decision === 'accepted');
  // Sort deterministically (mirrors backend sort by change_id)
  accepted.sort((a, b) => a.change_id.localeCompare(b.change_id));

  for (const change of accepted) {
    if (doc.raw_text && change.original_text && change.proposed_text && change.change_type !== 'add') {
      doc.raw_text = doc.raw_text.replace(change.original_text, change.proposed_text);
      continue;
    }

    try {
      if (change.change_type === 'remove') {
        applyChange(doc, change.target_reference, 'remove', null);
      } else if (change.change_type === 'add' || change.change_type === 'modify') {
        let value = change.proposed_text;
        try {
          value = JSON.parse(change.proposed_text || '');
        } catch { /* text value */ }
        applyChange(doc, change.target_reference, change.change_type, value);
      }
    } catch {
      // Best-effort client-side merge
    }
  }

  return doc as StructuredResume;
}
