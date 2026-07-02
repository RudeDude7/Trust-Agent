import { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { Wizard } from './components/Wizard';
import { Results } from './components/Results';
import { Chat } from './components/Chat';
import type { AnalysisResponse, SavedAudit } from './types';
import { Shield } from 'lucide-react';

function App() {
  const [audits, setAudits] = useState<SavedAudit[]>([]);
  const [activeData, setActiveData] = useState<AnalysisResponse | null>(null);

  // Load history on mount
  useEffect(() => {
    const saved = localStorage.getItem('vigilance_audits');
    if (saved) {
      try {
        setAudits(JSON.parse(saved));
      } catch (e) {
        console.error("Failed to parse history", e);
      }
    }
  }, []);

  const handleAnalysisComplete = (res: AnalysisResponse) => {
    setActiveData(res);

    // Save to ledger
    const newAudit: SavedAudit = {
      vendor: res.vendor,
      timestamp: new Date().toISOString(),
      session_id: res.session_id,
      data: res.risk_assessment,
    };
    
    setAudits(prev => {
      const updated = [newAudit, ...prev.filter(a => a.session_id !== res.session_id)];
      localStorage.setItem('vigilance_audits', JSON.stringify(updated));
      return updated;
    });
  };

  const handleNewAudit = () => {
    setActiveData(null);
  };

  return (
    <div className="flex h-screen w-full bg-background overflow-hidden selection:bg-cyan-500/30">
      <Sidebar 
        audits={audits} 
        onSelectAudit={setActiveData} 
        activeSessionId={activeData?.session_id || null} 
      />
      
      <main className="flex-1 relative flex flex-col h-full overflow-hidden">
        
        {/* Top Navbar for Context */}
        {activeData && (
          <div className="bg-slate-900 border-b border-slate-800 p-4 flex justify-between items-center shadow-md z-10">
            <h2 className="text-slate-300 font-mono tracking-widest text-sm flex items-center gap-2">
              <Shield size={16} className="text-cyan-400" />
              ANALYSIS MODE: {activeData.vendor.toUpperCase()}
            </h2>
            <button 
              onClick={handleNewAudit}
              className="text-xs font-mono bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-1.5 rounded transition-colors"
            >
              + NEW AUDIT
            </button>
          </div>
        )}

        {/* Content Area */}
        <div className="flex-1 overflow-auto bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-900 via-background to-background">
          {!activeData ? (
            <Wizard onAnalysisComplete={handleAnalysisComplete} />
          ) : (
            <div className="h-full relative">
              <Results data={activeData} />
              <Chat sessionId={activeData.session_id} />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
