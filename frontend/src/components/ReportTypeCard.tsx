import React from 'react';

export interface ReportCategory {
    category_id: string;
    name: string;
    description?: string;
}

export const ReportTypeCard: React.FC<{ category: ReportCategory }> = ({ category }) => {
    return (
        <div className="card flex-col gap-4" style={{ cursor: 'pointer' }}>
            <div className="flex justify-between items-center">
                <div style={{
                    width: '48px', height: '48px',
                    borderRadius: '50%', backgroundColor: 'var(--card-border)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: '24px'
                }}>
                    📋
                </div>
                <div className="badge primary">🛡️ Non-Police</div>
            </div>
            <div>
                <h3 style={{ margin: 0, fontSize: '1.125rem' }}>{category.name}</h3>
                {category.description && (
                    <p className="text-secondary text-small mt-2">{category.description}</p>
                )}
            </div>
            <div className="text-small text-secondary mt-2">
                <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
                    <li>Responded by City Services</li>
                </ul>
            </div>
        </div>
    );
};
