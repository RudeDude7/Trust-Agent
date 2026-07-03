import { useState, useEffect } from 'react';
import { supabase } from './supabase';
import { fetchAudits } from './api';
import { Sidebar } from './components/Sidebar';
import { Wizard } from './components/Wizard';
import { Results } from './components/Results';
import { Chat } from './components/Chat';
import { Login } from './components/Login';
import type { AnalysisResponse, SavedAudit } from './types';
import { Shield } from 'lucide-react';

function App() {
  const [audits, setAudits] = useState<SavedAudit[]>([]);
  const [activeData, setActiveData] = useState<SavedAudit | null>(null);

  const [session, setSession] = useState<any>(null);
  
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
      if (!session) {
        setAudits([]);
        setActiveData(null);
      }
    });

    return () => subscription.unsubscribe();
  }, []);

  // Load history on auth change
  useEffect(() => {
    if (session) {
      fetchAudits()
        .then(data => setAudits(data))
        .catch(err => console.error("Failed to load history", err));
    }
  }, [session]);

  const handleAnalysisComplete = (res: AnalysisResponse) => {
    const newAudit: SavedAudit = {
      vendor_name: res.vendor,
      created_at: new Date().toISOString(),
      session_id: res.session_id,
      risk_assessment: res.risk_assessment,
      chat_history: []
    };
    
    setActiveData(newAudit);
    setAudits(prev => [newAudit, ...prev]);
  };

  const handleNewAudit = () => {
    setActiveData(null);
  };

  if (!session) {
    return <Login />;
  }

  return (
    <div className="flex h-screen w-full bg-background overflow-hidden selection:bg-cyan-500/30">
      <Sidebar 
        audits={audits} 
        onSelectAudit={setActiveData} 
        activeSessionId={activeData?.session_id || null} 
      />
      
      <main className="flex-1 relative flex flex-col h-full overflow-hidden">
        
        {/* Top Navbar for Context */}
        <div className="bg-slate-900 border-b border-slate-800 p-4 flex justify-between items-center shadow-md z-10">
          {activeData ? (
            <h2 className="text-slate-300 font-mono tracking-widest text-sm flex items-center gap-2">
              <Shield size={16} className="text-cyan-400" />
              ANALYSIS MODE: {activeData.vendor_name.toUpperCase()}
            </h2>
          ) : (
            <h2 className="text-slate-300 font-mono tracking-widest text-sm">NEW DUE DILIGENCE AUDIT</h2>
          )}
          
          <div className="flex gap-4">
            {activeData && (
              <button 
                onClick={handleNewAudit}
                className="text-xs font-mono bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-1.5 rounded transition-colors"
              >
                + NEW AUDIT
              </button>
            )}
            <button 
              onClick={() => supabase.auth.signOut()}
              className="text-xs font-mono bg-red-900/50 hover:bg-red-900/80 text-red-200 px-3 py-1.5 rounded transition-colors"
            >
              LOGOUT
            </button>
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-auto bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-900 via-background to-background">
          {!activeData ? (
            <Wizard onAnalysisComplete={handleAnalysisComplete} />
          ) : (
            <div className="h-full relative">
              <Results data={activeData} />
              <Chat 
                key={activeData.session_id} 
                activeData={activeData} 
                onUpdateHistory={(newHistory) => {
                  setActiveData(prev => prev ? { ...prev, chat_history: newHistory } : null);
                  setAudits(prev => prev.map(a => a.session_id === activeData.session_id ? { ...a, chat_history: newHistory } : a));
                }}
              />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
