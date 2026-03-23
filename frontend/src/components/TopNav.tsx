import React from 'react';

export const TopNav: React.FC = () => {
    return (
        <header className="card flex items-center justify-between mb-8" style={{ borderTop: "4px solid var(--primary-blue)" }}>
            <div className="flex items-center gap-4">
                <div className="badge success">● All agencies online</div>
                <h1 style={{ margin: 0, fontSize: "1.25rem" }}>SF 311 High-Trust Portal</h1>
            </div>
            <div>
                <button className="btn btn-outline" style={{ marginRight: "0.5rem" }}>English</button>
                <button className="btn btn-primary" style={{ backgroundColor: "#111827" }}>Sign in</button>
            </div>
        </header>
    );
};
