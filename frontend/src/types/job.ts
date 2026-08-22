import type { PaginatedResponse } from './api';

/**
 * A single job listing from any platform.
 * Corresponds to the backend `JobListingResponse` Pydantic schema.
 */
export interface Job {
  id: string;
  platform: string;
  platform_job_id: string;
  title: string;
  company: string;
  location: string;
  url: string;
  description: string;
  salary_range: string | null;
  job_type: string | null;
  remote: boolean;
  posted_date: string | null;
  experience_level: string | null;
  match_score: number | null;
  skills_required: Record<string, unknown> | null;
  status: string;
  created_at: string;
  updated_at: string;
}

/** Alias matching the backend schema name `JobListingResponse`. */
export type JobListingResponse = Job;

/** Request body for multi-platform job search. */
export interface JobSearchRequest {
  query: string;
  location?: string;
  platforms?: string[];
  filters?: Record<string, unknown>;
  limit?: number;
}

/** Paginated list of job listings. */
export type JobListResponse = PaginatedResponse<Job>;

/** Response from the job analysis endpoint. */
export interface MatchEvidence {
  evidence_id: string;
  description: string;
}

export interface MatchFeatures {
  skills_score: number;
  experience_score: number;
  role_alignment_score: number;
  location_work_model_score: number;
  education_language_score: number;
  ats_score: number;
}

export interface EligibilityResult {
  is_eligible: boolean;
  status: string;
  reasons: string[];
}

export interface MatchProvenance {
  candidate_profile_version: number;
  matching_algorithm_version: string;
  model_provider: string;
  model_name: string;
  generated_at: string;
  ats_method: string;
}

export interface CandidateMatchResult {
  eligibility: EligibilityResult;
  match_score?: number;
  deterministic_score?: number;
  ats_score?: number;
  llm_score?: number;
  feature_scores?: MatchFeatures;
  strengths: MatchEvidence[];
  gaps: string[];
  critical_gaps: string[];
  recommendation: string;
  provenance: MatchProvenance;
}

/** Response from the job analysis endpoint. */
export type JobAnalysisResponse = CandidateMatchResult;

