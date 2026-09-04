import React, { useState } from 'react';
import { DiffViewer } from './DiffViewer';
import { CVTailoringChange } from '../../services/tailoringService';

interface Props {
    change: CVTailoringChange;
    onAccept: () => void;
    onReject: () => void;
    onRevise: (instruction: string) => void;
}

export const ChangeCard: React.FC<Props> = ({ change, onAccept, onReject, onRevise }) => {
    const [isRevising, setIsRevising] = useState(false);
    const [instruction, setInstruction] = useState('');

    const handleReviseSubmit = () => {
        if (instruction.trim()) {
            onRevise(instruction);
            setIsRevising(false);
            setInstruction('');
        }
    };

    let statusColor = 'bg-white border-gray-200';
    if (change.user_decision === 'accepted') statusColor = 'bg-green-50 border-green-200';
    if (change.user_decision === 'rejected') statusColor = 'bg-red-50 border-red-200';

    return (
        <div className={'change-card border p-4 rounded-lg shadow-sm mb-4 transition-colors ' + statusColor}>
            <div className="flex justify-between items-center mb-2">
                <span className="font-bold uppercase text-xs text-gray-500">{change.change_type}</span>
                
                <div className="flex gap-2">
                    {change.review_severity === 'warning' && <span className="bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded font-bold text-xs">WARNING</span>}
                    {change.review_severity === 'blocked' && <span className="bg-red-100 text-red-800 px-2 py-0.5 rounded font-bold text-xs">BLOCKED</span>}
                    {change.user_decision !== 'pending' && (
                        <span className={'px-2 py-0.5 rounded font-bold text-xs ' + (change.user_decision === 'accepted' ? 'text-green-700 bg-green-200' : 'text-red-700 bg-red-200')}>
                            {change.user_decision.toUpperCase()}
                        </span>
                    )}
                </div>
            </div>
            
            <DiffViewer change={change} />
            
            <div className="mt-3 text-sm text-gray-700">
                <strong>Reason:</strong> {change.reason}
            </div>
            
            {change.review_severity !== 'safe' && (
                <div className={'mt-2 text-xs p-2 rounded ' + (change.review_severity === 'blocked' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800')}>
                    <strong>AI Review:</strong> {change.review_reason}
                </div>
            )}
            
            <div className="mt-4 flex gap-2">
                {change.user_decision === 'pending' && (
                    <>
                        <button 
                            disabled={change.review_severity === 'blocked'} 
                            onClick={onAccept}
                            title={change.review_severity === 'blocked' ? 'Cannot accept blocked changes' : ''}
                            className="px-3 py-1 bg-green-600 text-white text-sm rounded disabled:opacity-50 hover:bg-green-700">
                            Accept
                        </button>
                        <button 
                            onClick={onReject}
                            className="px-3 py-1 bg-red-600 text-white text-sm rounded hover:bg-red-700">
                            Reject
                        </button>
                        <button 
                            onClick={() => setIsRevising(!isRevising)}
                            className="px-3 py-1 bg-gray-200 text-gray-800 text-sm rounded hover:bg-gray-300">
                            Revise
                        </button>
                    </>
                )}
                {change.user_decision !== 'pending' && (
                    <button 
                        onClick={() => change.user_decision === 'accepted' ? onReject() : onAccept()}
                        disabled={change.user_decision === 'rejected' && change.review_severity === 'blocked'}
                        className="px-3 py-1 bg-gray-200 text-gray-800 text-sm rounded hover:bg-gray-300 disabled:opacity-50">
                        Undo Decision
                    </button>
                )}
            </div>

            {isRevising && (
                <div className="mt-3 p-3 bg-gray-50 border rounded">
                    <label className="block text-xs font-bold mb-1">What should be changed?</label>
                    <input 
                        type="text" 
                        value={instruction}
                        onChange={e => setInstruction(e.target.value)}
                        className="w-full border p-1 text-sm rounded mb-2" 
                        placeholder="e.g., Make it sound more technical"
                    />
                    <div className="flex gap-2">
                        <button onClick={handleReviseSubmit} className="px-2 py-1 bg-blue-600 text-white text-xs rounded">Submit Revision</button>
                        <button onClick={() => setIsRevising(false)} className="px-2 py-1 bg-gray-300 text-xs rounded">Cancel</button>
                    </div>
                </div>
            )}
        </div>
    );
};

