import { describe, test, expect, beforeEach, vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { CVTailoringWorkbench } from '../../../pages/CVTailoringWorkbench';
import { tailoringService } from '../../../services/tailoringService';
import { jobService } from '../../../services/jobService';
import { resumeService } from '../../../services/resumeService';

vi.mock('../../../services/tailoringService', () => ({ tailoringService: { getSession: vi.fn(), submitDecisions: vi.fn(), finalizeSession: vi.fn(), reviseChange: vi.fn() } }));
vi.mock('../../../services/jobService', () => ({ jobService: { getJob: vi.fn() } }));
vi.mock('../../../services/resumeService', () => ({ resumeService: { getResume: vi.fn() } }));

const mockSession = {
    id: 'sess-123',
    job_id: 'job-123',
    base_resume_id: 'res-123',
    status: 'reviewing',
    changes: [
        {
            change_id: 'c1',
            target_type: 'inline',
            target_reference: 'skills[0]',
            section: 'skills',
            original_text: 'Python',
            proposed_text: 'Python/Django',
            change_type: 'modify',
            reason: 'Job requires Django',
            linked_requirement_ids: [],
            linked_evidence_ids: [],
            review_severity: 'safe',
            review_reason: '',
            user_decision: 'pending'
        },
        {
            change_id: 'c2',
            target_type: 'inline',
            target_reference: 'experience[0]',
            section: 'experience',
            original_text: 'Dev',
            proposed_text: 'Fake Senior Dev',
            change_type: 'modify',
            reason: 'Make it sound better',
            linked_requirement_ids: [],
            linked_evidence_ids: [],
            review_severity: 'blocked',
            review_reason: 'Hallucination',
            user_decision: 'pending'
        }
    ]
};

describe('CVTailoringWorkbench Integration', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    test('loads session and allows accepting/rejecting changes, then finalizes', async () => {
        (tailoringService.getSession as any).mockResolvedValue(mockSession);
        (jobService.getJob as any).mockResolvedValue({ id: 'job-123', title: 'Test Job', company: 'Test Corp', description: 'desc', url: 'http://u', platform: 'LinkedIn' });
        (resumeService.getResume as any).mockResolvedValue({ id: 'res-123', name: 'Base CV', content_text: '{"name": "Test User", "skills": ["Python"], "experience": [{"title": "Dev", "company": "Corp", "description": "d"}]}' });

        render(
            <MemoryRouter initialEntries={['/cv-tailoring/sess-123']}>
                <Routes>
                    <Route path="/cv-tailoring/:sessionId" element={<CVTailoringWorkbench />} />
                </Routes>
            </MemoryRouter>
        );

        expect(await screen.findByText('Test Job')).toBeInTheDocument();
        expect(screen.getByText('+ Python/Django')).toBeInTheDocument();
        expect(screen.getByText('+ Fake Senior Dev')).toBeInTheDocument();
        
        (tailoringService.submitDecisions as any).mockResolvedValue({ ...mockSession, changes: [ { ...mockSession.changes[0], user_decision: 'accepted' }, mockSession.changes[1] ] });
        const acceptBtns = screen.getAllByText('Accept');
        fireEvent.click(acceptBtns[0]); 
        
        await waitFor(() => {
            expect(tailoringService.submitDecisions).toHaveBeenCalledWith('sess-123', { 'c1': 'accepted' });
        });

        (tailoringService.submitDecisions as any).mockResolvedValue({ ...mockSession, changes: [ { ...mockSession.changes[0], user_decision: 'accepted' }, { ...mockSession.changes[1], user_decision: 'rejected' } ] });
        const rejectBtns = screen.getAllByText('Reject');
        fireEvent.click(rejectBtns[0]); 
        
        await waitFor(() => {
            expect(tailoringService.submitDecisions).toHaveBeenCalledWith('sess-123', { 'c2': 'rejected' });
        });

        const finalizeBtn = screen.getByText('Finalize CV');
        await waitFor(() => expect(finalizeBtn).not.toBeDisabled());
        fireEvent.click(finalizeBtn);
        
        await waitFor(() => {
            expect(tailoringService.finalizeSession).toHaveBeenCalledWith('sess-123');
        });
    });
});
