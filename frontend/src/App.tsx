import React, { useEffect, useState } from 'react';
import { TopNav } from './components/TopNav';
import { PrivacyToggle } from './components/PrivacyToggle';
import { ReportTypeCard } from './components/ReportTypeCard';
import type { ReportCategory } from './components/ReportTypeCard';
import { ResolutionCard } from './components/ResolutionCard';
import type { UnifiedReport } from './components/ResolutionCard';

const App: React.FC = () => {
    const [categories, setCategories] = useState<ReportCategory[]>([]);
    const [reports, setReports] = useState<UnifiedReport[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // Fetch categories
        fetch('http://localhost:8000/api/categories')
            .then(res => res.json())
            .then(data => setCategories(data))
            .catch(err => console.error("Error fetching categories:", err));

        // Fetch reports
        fetch('http://localhost:8000/api/reports')
            .then(res => res.json())
            .then(data => {
                setReports(data);
                setLoading(false);
            })
            .catch(err => {
                console.error("Error fetching reports:", err);
                setLoading(false);
            });
    }, []);

    return (
        <div className="container" style={{ paddingBottom: '4rem', paddingTop: '2rem' }}>
            <TopNav />
            <PrivacyToggle />

            <section className="mb-8">
                <h2 style={{ fontSize: '1.5rem', marginBottom: '4px' }}>Select Report Type</h2>
                <p className="text-secondary mb-6 mt-0">Choose the category that best describes the issue.</p>
                
                <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))' }}>
                    {categories.map(cat => (
                        <ReportTypeCard key={cat.category_id} category={cat} />
                    ))}
                </div>
            </section>

            <section>
                <h2 style={{ fontSize: '1.5rem', marginBottom: '4px' }}>Recent Verified Resolutions</h2>
                <p className="text-secondary mb-6 mt-0">See how SF agencies are resolving issues in real time.</p>

                {loading ? (
                    <p>Loading recent reports...</p>
                ) : (
                    <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))' }}>
                        {reports.map((report, idx) => (
                            <ResolutionCard key={`${report.id}-${idx}`} report={report} />
                        ))}
                    </div>
                )}
            </section>
        </div>
    );
};

export default App;
