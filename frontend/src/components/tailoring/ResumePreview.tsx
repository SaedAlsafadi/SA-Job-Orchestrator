import React from 'react';
import { CVTailoringChange } from '../../services/tailoringService';

interface Props {
    baseResumeText: string;
    changes: CVTailoringChange[];
}

export const ResumePreview: React.FC<Props> = ({ baseResumeText, changes }) => {
    
    let resumeData: any = {};
    try {
        resumeData = JSON.parse(baseResumeText);
    } catch {
        return <pre className="whitespace-pre-wrap text-sm">{baseResumeText}</pre>;
    }

    const getFieldStatus = (path: string) => {
        const related = changes.filter(c => c.target_reference.startsWith(path));
        if (related.length === 0) return null;
        
        if (related.some(c => c.user_decision === 'pending')) return 'bg-yellow-100 border-l-4 border-yellow-400';
        if (related.some(c => c.user_decision === 'accepted')) return 'bg-green-50 border-l-4 border-green-400';
        if (related.some(c => c.user_decision === 'rejected')) return 'bg-red-50 border-l-4 border-red-400 opacity-50';
        return null;
    };

    return (
        <div className="resume-preview font-sans">
            <div className={'text-center mb-6 p-2 ' + (getFieldStatus('name') || getFieldStatus('email') || getFieldStatus('phone') || '')}>
                <h1 className="text-3xl font-bold">{resumeData.name}</h1>
                <div className="text-sm text-gray-600 space-x-2 mt-2">
                    <span>{resumeData.email}</span>
                    <span>{resumeData.phone}</span>
                    <span>{resumeData.location}</span>
                </div>
            </div>

            {resumeData.summary && (
                <div className={'mb-6 p-2 ' + (getFieldStatus('summary') || '')}>
                    <h2 className="text-lg font-bold border-b mb-2 uppercase">Summary</h2>
                    <p className="text-sm">{resumeData.summary}</p>
                </div>
            )}

            {resumeData.skills && resumeData.skills.length > 0 && (
                <div className={'mb-6 p-2 ' + (getFieldStatus('skills') || '')}>
                    <h2 className="text-lg font-bold border-b mb-2 uppercase">Skills</h2>
                    <p className="text-sm">{resumeData.skills.join(', ')}</p>
                </div>
            )}

            {resumeData.experience && resumeData.experience.length > 0 && (
                <div className="mb-6">
                    <h2 className="text-lg font-bold border-b mb-2 uppercase">Experience</h2>
                    {resumeData.experience.map((exp: any, idx: number) => (
                        <div key={idx} className={'mb-4 p-2 ' + (getFieldStatus('experience[' + idx + ']') || '')}>
                            <div className="flex justify-between items-baseline">
                                <h3 className="font-bold">{exp.title}</h3>
                                <span className="text-sm text-gray-600">{exp.duration}</span>
                            </div>
                            <div className="text-sm font-semibold text-gray-700">{exp.company}</div>
                            {exp.description && (
                                <ul className="list-disc list-outside ml-5 mt-1 text-sm">
                                    {exp.description.split('\n').map((bullet: string, i: number) => (
                                        <li key={i}>{bullet}</li>
                                    ))}
                                </ul>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};
