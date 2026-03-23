import React from 'react';

export interface UnifiedReport {
    id: string;
    title: string;
    status: string;
    lat: number;
    lng: number;
    source: string;
    agency?: string;
    created_at?: string;
    image_url?: string;
}

export const ResolutionCard: React.FC<{ report: UnifiedReport }> = ({ report }) => {
    const isResolved = report.status?.toLowerCase().includes('closed') || report.status?.toLowerCase().includes('resolved');
    const badgeClass = isResolved ? "badge success" : "badge primary";
    
    return (
        <div className="card flex-col gap-4">
            <div className="flex justify-between items-center">
                <div className={badgeClass}>
                    {isResolved ? "✓ Resolved" : "⏳ In Progress"}
                </div>
                <div className="text-secondary text-small">
                    #{report.id?.substring(0, 8)}
                </div>
            </div>
            
            <h3 style={{ margin: 0 }}>{report.title}</h3>
            
            {report.image_url ? (
                <div className="img-wrapper mt-4">
                    <img src={report.image_url} alt="Report evidence" />
                </div>
            ) : (
                <div className="img-wrapper mt-4" style={{ height: '150px', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f3f4f6' }}>
                    <span className="text-secondary">No Image Provided</span>
                </div>
            )}
            
            <div className="text-small text-secondary mt-4">
                <p style={{ margin: '0 0 4px 0' }}><strong>Source:</strong> {report.source}</p>
                <p style={{ margin: '0 0 4px 0' }}><strong>Agency:</strong> {report.agency || 'Unassigned'}</p>
                {report.created_at && (
                    <p style={{ margin: 0 }}><strong>Date:</strong> {new Date(report.created_at).toLocaleDateString()}</p>
                )}
            </div>
        </div>
    );
};
