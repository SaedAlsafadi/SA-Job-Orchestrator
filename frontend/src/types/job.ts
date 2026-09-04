import type { PaginatedResponse } from './api';

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

export type JobListingResponse = Job;

export interface JobSearchRequest {
  query: string;
  location?: string;
  platforms?: string[];
  filters?: Record<string, unknown>;
  limit?: number;
}

export type JobListResponse = PaginatedResponse<Job>;

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

export type RequirementStatus = "MATCH" | "PARTIAL" | "GAP" | "UNKNOWN";
export type RequirementImportance = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

export interface RequirementAnalysis {
  requirement_id: string;
  original_text: string;
  normalized_requirement: string;
  category: string;
  importance: RequirementImportance;
  status: RequirementStatus;
  evidence_ids: string[];
  explanation: string;
}

export type DimensionStatus = "VALID_SCORE" | "UNKNOWN" | "INSUFFICIENT_DATA" | "NOT_APPLICABLE";

export interface DimensionScore {
  status: DimensionStatus;
  score: number | null;
  explanation: string | null;
}

export type MatchVerdict = "STRONG_MATCH" | "GOOD_MATCH" | "PARTIAL_MATCH" | "WEAK_MATCH" | "INSUFFICIENT_DATA";

export interface MatchDimensions {
  skills: DimensionScore;
  experience: DimensionScore;
  role_alignment: DimensionScore;
}

export interface CandidateMatchResult {
  eligibility: EligibilityResult;
  total_score: number | null;
  verdict: MatchVerdict;
  confidence: number;
  data_quality: string;
  data_quality_explanation: string | null;
  explanation: string;
  recommendation: string;
  dimensions: MatchDimensions;
  strong_matches: string[];
  gaps: string[];
  critical_gaps: string[];
  blockers: string[];
  requirement_analysis: RequirementAnalysis[];
  provenance: MatchProvenance;
}

export type JobAnalysisResponse = CandidateMatchResult;
