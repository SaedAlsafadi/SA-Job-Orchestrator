import api from './api';
import type { Resume } from '../types/resume';

const LLM_ACTION_TIMEOUT_MS = 300_000;

export interface CVTailoringChange {
    change_id: string;
    target_type: string;
    target_reference: string;
    section: string;
    original_text: string | null;
    proposed_text: string | null;
    change_type: 'add' | 'modify' | 'remove';
    reason: string;
    linked_requirement_ids: string[];
    linked_evidence_ids: string[];
    review_severity: 'safe' | 'warning' | 'blocked';
    review_reason: string;
    user_decision: 'pending' | 'accepted' | 'rejected';
}

export interface CVTailoringSession {
    id: string;
    job_id: string;
    base_resume_id: string;
    status: 'draft' | 'reviewing' | 'approved' | 'rendering' | 'verified' | 'failed';
    final_resume_id?: string | null;
    changes: CVTailoringChange[];
}

export const tailoringService = {
    startSession: async (job_id: string, base_resume_id: string): Promise<CVTailoringSession> => {
        const response = await api.post(
            '/tailoring/start',
            { job_id, base_resume_id },
            { timeout: LLM_ACTION_TIMEOUT_MS },
        );
        return response.data;
    },
    
    getSession: async (session_id: string): Promise<CVTailoringSession> => {
        const response = await api.get('/tailoring/' + session_id);
        return response.data;
    },

    getSessionForResume: async (resume_id: string): Promise<CVTailoringSession> => {
        const response = await api.get('/tailoring/resume/' + resume_id);
        return response.data;
    },

    openRevisionSession: async (resume_id: string): Promise<CVTailoringSession> => {
        const response = await api.post('/tailoring/resume/' + resume_id + '/revision');
        return response.data;
    },
    
    submitDecisions: async (session_id: string, decisions: Record<string, 'accepted' | 'rejected'>): Promise<CVTailoringSession> => {
        const response = await api.post('/tailoring/' + session_id + '/decisions', { decisions });
        return response.data;
    },
    
    regenerateSession: async (session_id: string): Promise<CVTailoringSession> => {
        const response = await api.post(
            '/tailoring/' + session_id + '/regenerate',
            undefined,
            { timeout: LLM_ACTION_TIMEOUT_MS },
        );
        return response.data;
    },
    
    reviseChange: async (session_id: string, change_id: string, instruction: string): Promise<any> => {
        const response = await api.post(
            '/tailoring/' + session_id + '/revise',
            { change_id, instructions: instruction },
            { timeout: LLM_ACTION_TIMEOUT_MS },
        );
        return response.data;
    },
    
    finalizeSession: async (session_id: string): Promise<Resume> => {
        const response = await api.post('/tailoring/' + session_id + '/finalize');
        return response.data;
    }
};




