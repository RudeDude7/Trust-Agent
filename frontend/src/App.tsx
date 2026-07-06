import { useState, useEffect } from 'react';
import { supabase } from './supabase';
import { fetchAudits } from './api';
import { Sidebar } from './components/Sidebar';
import { Wizard } from './components/Wizard';
import { Results } from './components/Results';
import { Chat } from './components/Chat';
import { Login } from './components/Login';
import { LiveThreats } from './components/LiveThreats';
import { TeamSettings } from './components/TeamSettingsView';
import type { AnalysisResponse, SavedAudit } from './types';
import { Shield, Bell } from 'lucide-react';

function App() {
  const [audits, setAudits] = useState<SavedAudit[]>([]);
  const [activeData, setActiveData] = useState<SavedAudit | null>(null);
  const [isThreatFeedOpen, setIsThreatFeedOpen] = useState(false);
  const [isTeamSettingsOpen, setIsTeamSettingsOpen] = useState(false);

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
    setIsThreatFeedOpen(false);
    setIsTeamSettingsOpen(false);
  };

  const handleSelectAudit = (audit: SavedAudit) => {
    setActiveData(audit);
    setIsThreatFeedOpen(false);
    setIsTeamSettingsOpen(false);
  };

  const handleOpenThreatFeed = () => {
    setActiveData(null);
    setIsThreatFeedOpen(true);
    setIsTeamSettingsOpen(false);
  };

  const handleOpenTeamSettings = () => {
    setActiveData(null);
    setIsThreatFeedOpen(false);
    setIsTeamSettingsOpen(true);
  };

  const handleDeleteAudit = async (sessionId: string) => {
    if (!confirm('Are you sure you want to delete this audit?')) return;
    try {
      const { deleteAudit } = await import('./api');
      await deleteAudit(sessionId);
      setAudits(prev => prev.filter(a => a.session_id !== sessionId));
      if (activeData?.session_id === sessionId) {
        handleNewAudit();
      }
    } catch (err) {
      console.error('Failed to delete audit:', err);
      alert('Failed to delete audit.');
    }
  };

  if (!session) {
    return <Login />;
  }

  return (
    <div className="flex h-screen w-full bg-stone-50 overflow-hidden selection:bg-accent-200">
      <Sidebar 
        audits={audits} 
        onSelectAudit={handleSelectAudit} 
        onOpenThreatFeed={handleOpenThreatFeed}
        onOpenTeamSettings={handleOpenTeamSettings}
        onDeleteAudit={handleDeleteAudit}
        activeSessionId={activeData?.session_id || null} 
        isThreatFeedOpen={isThreatFeedOpen}
        isTeamSettingsOpen={isTeamSettingsOpen}
      />
      
      <main className="flex-1 relative flex flex-col h-full overflow-hidden">
        
        {/* Top Navbar for Context */}
        <div className="bg-white border-b border-stone-200 p-5 flex justify-between items-center z-10 shadow-sm">
          {isThreatFeedOpen ? (
            <h2 className="text-stone-800 font-heading font-semibold tracking-wide text-sm flex items-center gap-2 uppercase">
              <Bell size={18} className="text-accent-600" />
              Live Threat Monitor
            </h2>
          ) : activeData ? (
            <h2 className="text-stone-800 font-heading font-semibold tracking-wide text-sm flex items-center gap-2 uppercase">
              <Shield size={18} className="text-accent-600" />
              Analysis Mode: {activeData.vendor_name}
            </h2>
          ) : (
            <h2 className="text-stone-800 font-heading font-semibold tracking-wide text-sm uppercase">New Due Diligence Audit</h2>
          )}
          
          <div className="flex gap-4">
            {activeData && (
              <button 
                onClick={handleNewAudit}
                className="text-xs font-semibold bg-stone-100 hover:bg-stone-200 text-stone-700 px-4 py-2 rounded-xl transition-colors"
              >
                + New Audit
              </button>
            )}
            <button 
              onClick={() => supabase.auth.signOut()}
              className="text-xs font-semibold bg-white border border-stone-200 hover:bg-red-50 text-red-600 px-4 py-2 rounded-xl transition-colors"
            >
              Logout
            </button>
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-auto bg-stone-50">
          {isThreatFeedOpen ? (
            <LiveThreats />
          ) : isTeamSettingsOpen ? (
            <TeamSettings />
          ) : !activeData ? (
            <Wizard onAnalysisComplete={handleAnalysisComplete} />
          ) : (
            <div className="min-h-full relative">
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
