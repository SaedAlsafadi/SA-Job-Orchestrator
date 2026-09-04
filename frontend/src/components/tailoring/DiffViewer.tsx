import React from 'react';
import { CVTailoringChange } from '../../services/tailoringService';

interface Props {
    change: CVTailoringChange;
}

export const DiffViewer: React.FC<Props> = ({ change }) => {
    return (
        <div className="diff-viewer text-sm rounded border bg-gray-50 overflow-hidden">
            <div className="bg-gray-200 px-2 py-1 text-xs text-gray-600 border-b font-mono">
                Target: {change.target_reference}
            </div>
            <div className="p-2">
                {(change.change_type === 'remove' || change.change_type === 'modify') && (
                    <div className="text-red-700 bg-red-50 p-1 mb-1 rounded line-through">
                        - {change.original_text || 'None'}
                    </div>
                )}
                {(change.change_type === 'add' || change.change_type === 'modify') && (
                    <div className="text-green-800 bg-green-50 p-1 rounded">
                        + {change.proposed_text}
                    </div>
                )}
            </div>
        </div>
    );
};
