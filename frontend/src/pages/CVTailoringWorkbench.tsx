import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { tailoringService, CVTailoringSession, CVTailoringChange } from '../services/tailoringService';
import { jobService } from '../services/jobService';
import { resumeService } from '../services/resumeService';
import { Job, Resume } from '../types';
import { ChangeCard } from '../components/tailoring/ChangeCard';
import { ResumePreview } from '../components/tailoring/ResumePreview';

export const CVTailoringWorkbench: React.FC = () => {
    const { sessionId } = useParams<{ sessionId: string }>();
    const navigate = useNavigate();

    const [session, setSession] = useState<CVTailoringSession | null>(null);
    const [job, setJob] = useState<Job | null>(null);
    const [baseResume, setBaseResume] = useState<Resume | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    
    // UI State
    const [filter, setFilter] = useState<'ALL' | 'ADDED' | 'MODIFIED' | 'REMOVED' | 'WARNING' | 'BLOCKED'>('ALL');
    const [finalResume, setFinalResume] = useState<Resume | null>(null);
    const [verifying, setVerifying] = useState(false);

    useEffect(() => {
        if (sessionId) {
            loadData(sessionId);
        }
    }, [sessionId]);

    const loadData = async (id: string) => {
        try {
            setLoading(true);
            const s = await tailoringService.getSession(id);
            setSession(s);
            
            const [j, r] = await Promise.all([
                jobService.getJob(s.job_id),
                resumeService.getResume(s.base_resume_id)
            ]);
            setJob(j);
            setBaseResume(r);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to load tailoring session');
        } finally {
            setLoading(false);
        }
    };

    const handleDecision = async (changeId: string, decision: 'accepted' | 'rejected') => {
        if (!session) return;
        
        // Optimistic UI updates are banned. Wait for backend.
        const originalChanges = [...session.changes];
        
        try {
            // But we do need to show a loading state for this card? 
            // For now, we block or just rely on fast API.
            const updated = await tailoringService.submitDecisions(session.id, { [changeId]: decision });
            setSession(updated);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to submit decision');
            // Revert is automatic since we didn't optimistically update state
        }
    };

    const handleBulkAccept = async () => {
        if (!session) return;
        const decisions: Record<string, 'accepted'> = {};
        session.changes.forEach(c => {
            if (c.user_decision === 'pending' && c.review_severity === 'safe') {
                decisions[c.change_id] = 'accepted';
            }
        });
        
        if (Object.keys(decisions).length === 0) return;
        
        try {
            const updated = await tailoringService.submitDecisions(session.id, decisions);
            setSession(updated);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to submit bulk decisions');
        }
    };

    const handleRevise = async (changeId: string, instruction: string) => {
        if (!session) return;
        try {
            await tailoringService.reviseChange(session.id, changeId, instruction);
            await loadData(session.id); // Reload to get new changes
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to revise change. Revision may not be implemented yet.');
        }
    };

    const handleFinalize = async () => {
        if (!session) return;
        try {
            setVerifying(true);
            const newResume = await tailoringService.finalizeSession(session.id);
            setFinalResume(newResume);
            setSession({ ...session, status: 'verified' });
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to finalize resume');
        } finally {
            setVerifying(false);
        }
    };

    if (loading) {
        return <div className="flex items-center justify-center h-screen">
            <h2 className="text-xl">Analyzing this job against your CV...</h2>
        </div>;
    }

    if (error) {
        return <div className="flex flex-col items-center justify-center h-screen">
            <h2 className="text-xl text-red-600 mb-4">Error</h2>
            <p>{error}</p>
            <button onClick={() => navigate(-1)} className="mt-4 px-4 py-2 bg-blue-600 text-white rounded">Go Back</button>
        </div>;
    }

    if (!session || !job || !baseResume) return null;

    const filteredChanges = session.changes.filter(c => {
        if (filter === 'ALL') return true;
        if (filter === 'ADDED') return c.change_type === 'add';
        if (filter === 'MODIFIED') return c.change_type === 'modify';
        if (filter === 'REMOVED') return c.change_type === 'remove';
        if (filter === 'WARNING') return c.review_severity === 'warning';
        if (filter === 'BLOCKED') return c.review_severity === 'blocked';
        return true;
    });

    const pendingCount = session.changes.filter(c => c.user_decision === 'pending').length;
    const blockedCount = session.changes.filter(c => c.user_decision === 'pending' && c.review_severity === 'blocked').length;
    const canFinalize = pendingCount === 0 && session.changes.every(c => !(c.user_decision === 'accepted' && c.review_severity === 'blocked'));

    return (
        <div className="flex h-screen bg-gray-50 overflow-hidden text-gray-900">
            {/* Left Panel: Job Summary */}
            <div className="w-1/4 flex flex-col border-r bg-white overflow-y-auto">
                <div className="p-4 border-b bg-gray-100">
                    <button onClick={() => navigate(-1)} className="text-blue-600 hover:underline mb-2 block">&larr; Back to Job</button>
                    <h2 className="text-xl font-bold">{job.title}</h2>
                    <p className="text-sm text-gray-600">{job.company} &bull; {job.location}</p>
                </div>
                <div className="p-4 flex-1">
                    <h3 className="font-bold mb-2">Match Intelligence</h3>
                    <div className="mb-4 p-3 bg-blue-50 rounded">
                        <div className="text-sm font-semibold">Score: {job.match_score ?? 'N/A'}%</div>
                        {/* We would render actual gap/strength data here */}
                        <p className="text-xs text-gray-700 mt-2">The AI has analyzed requirements and suggested changes to highlight relevant experience.</p>
                    </div>
                </div>
            </div>

            {/* Center Panel: CV Preview */}
            <div className="w-1/2 flex flex-col">
                <div className="p-4 border-b bg-white flex justify-between items-center">
                    <h2 className="text-lg font-bold">Structured Resume Preview</h2>
                    {verifying && <span className="text-blue-600 animate-pulse">Creating and verifying your tailored CV...</span>}
                    {session.status === 'verified' && <span className="text-green-600 font-bold">&#10003; CV verified</span>}
                </div>
                <div className="flex-1 overflow-y-auto p-8 bg-gray-100">
                    <div className="bg-white shadow-lg min-h-full p-8">
                        <ResumePreview 
                            baseResumeText={baseResume.content_text || ''} 
                            changes={session.changes} 
                        />
                    </div>
                </div>
            </div>

            {/* Right Panel: Changes */}
            <div className="w-1/4 flex flex-col border-l bg-white">
                <div className="p-4 border-b">
                    <h2 className="text-lg font-bold">{session.changes.length} Proposed Changes</h2>
                    
                    <div className="flex flex-wrap gap-2 mt-3">
                        {['ALL', 'ADDED', 'MODIFIED', 'REMOVED', 'WARNING', 'BLOCKED'].map(f => (
                            <button 
                                key={f}
                                onClick={() => setFilter(f as any)}
                                className={'text-xs px-2 py-1 rounded ' + (filter === f ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700')}
                            >
                                {f}
                            </button>
                        ))}
                    </div>
                </div>
                
                <div className="flex-1 overflow-y-auto p-4">
                    <div className="mb-4 flex justify-between">
                        <button 
                            onClick={handleBulkAccept}
                            className="text-sm text-blue-600 hover:underline">
                            Accept All Safe
                        </button>
                    </div>

                    {filteredChanges.map(change => (
                        <ChangeCard 
                            key={change.change_id} 
                            change={change} 
                            onAccept={() => handleDecision(change.change_id, 'accepted')}
                            onReject={() => handleDecision(change.change_id, 'rejected')}
                            onRevise={(instr) => handleRevise(change.change_id, instr)}
                        />
                    ))}
                    
                    {filteredChanges.length === 0 && <p className="text-gray-500 text-sm text-center mt-8">No changes match filter.</p>}
                </div>
                
                <div className="p-4 border-t bg-gray-50">
                    <div className="text-xs mb-2 text-gray-600">
                        Accepted: {session.changes.filter(c => c.user_decision === 'accepted').length} | 
                        Rejected: {session.changes.filter(c => c.user_decision === 'rejected').length} | 
                        Pending: {pendingCount}
                    </div>
                    
                    {session.status === 'verified' ? (
                        <div className="flex gap-2">
                            <button 
                                className="flex-1 bg-green-600 text-white py-2 rounded font-bold"
                                onClick={() => window.open('/api/v1/resumes/' + finalResume?.id + '/pdf', '_blank')}
                            >
                                Download PDF
                            </button>
                        </div>
                    ) : (
                        <button 
                            disabled={!canFinalize || verifying}
                            onClick={handleFinalize}
                            className="w-full bg-blue-600 text-white py-2 rounded font-bold disabled:opacity-50"
                        >
                            {verifying ? 'Finalizing...' : 'Finalize CV'}
                        </button>
                    )}
                    
                    {pendingCount > 0 && <p className="text-xs text-red-500 mt-2">Must resolve all pending changes to finalize.</p>}
                </div>
            </div>
        </div>
    );
};


