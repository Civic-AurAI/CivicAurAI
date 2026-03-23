import React, { useState } from 'react';

export const PrivacyToggle: React.FC = () => {
    const [isAnonymous, setIsAnonymous] = useState(true);

    return (
        <div className="card flex items-center justify-between mb-8">
            <div>
                <h3 style={{ margin: 0 }}>Guest Report (Anonymous)</h3>
                <p className="text-secondary text-small" style={{ margin: "4px 0 0 0" }}>
                    Your identity is hidden. EXIF and GPS data details are stripped from images unless strictly needed.
                </p>
            </div>
            <label className="flex items-center" style={{ cursor: "pointer" }}>
                <div style={{
                    width: "48px",
                    height: "24px",
                    backgroundColor: isAnonymous ? "var(--primary-blue)" : "var(--card-border)",
                    borderRadius: "9999px",
                    position: "relative",
                    transition: "background-color 0.2s"
                }}>
                    <div style={{
                        width: "20px",
                        height: "20px",
                        backgroundColor: "white",
                        borderRadius: "50%",
                        position: "absolute",
                        top: "2px",
                        left: isAnonymous ? "26px" : "2px",
                        transition: "left 0.2s"
                    }} />
                </div>
                <input 
                    type="checkbox" 
                    checked={isAnonymous} 
                    onChange={() => setIsAnonymous(!isAnonymous)} 
                    style={{ opacity: 0, position: "absolute", zIndex: -1 }}
                />
            </label>
        </div>
    );
};
