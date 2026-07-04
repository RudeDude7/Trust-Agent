import React, { useEffect, useState } from 'react';
import { ShieldAlert, AlertTriangle, AlertCircle, Info, ExternalLink, Check, Bell } from 'lucide-react';
import type { ThreatAlert } from '../types';
import { fetchThreatAlerts, markAlertRead } from '../api';
import clsx from 'clsx';

export const LiveThreats: React.FC = () => {
  const [alerts, setAlerts] = useState<ThreatAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAlerts();
  }, []);

  const loadAlerts = async () => {
    try {
      setLoading(true);
      const data = await fetchThreatAlerts();
      setAlerts(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load threat alerts');
    } finally {
      setLoading(false);
    }
  };

  const handleMarkRead = async (id: string) => {
    try {
      await markAlertRead(id);
      setAlerts(prev => prev.map(a => a.id === id ? { ...a, is_read: true } : a));
    } catch (err: any) {
      console.error('Failed to mark read', err);
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'CRITICAL': return <ShieldAlert className="text-red-500" size={20} />;
      case 'HIGH': return <AlertTriangle className="text-orange-500" size={20} />;
      case 'MEDIUM': return <AlertCircle className="text-amber-500" size={20} />;
      default: return <Info className="text-blue-500" size={20} />;
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'CRITICAL': return 'bg-red-500/10 text-red-500 border-red-500/20';
      case 'HIGH': return 'bg-orange-500/10 text-orange-500 border-orange-500/20';
      case 'MEDIUM': return 'bg-amber-500/10 text-amber-500 border-amber-500/20';
      default: return 'bg-blue-500/10 text-blue-500 border-blue-500/20';
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-slate-950">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-fuchsia-500"></div>
      </div>
    );
  }

  const unreadCount = alerts.filter(a => !a.is_read).length;

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-950 p-8 overflow-y-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold font-mono text-slate-200 tracking-tight flex items-center gap-3">
            <Bell className="text-fuchsia-500" size={28} />
            Live Threat & Breach Feed
          </h1>
          <p className="text-slate-400 mt-2">Continuous OSINT monitoring for your watched vendors.</p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-lg px-4 py-2 flex items-center gap-3">
          <div className="text-slate-400 text-sm">Unread Alerts</div>
          <div className="text-2xl font-black text-fuchsia-500">{unreadCount}</div>
        </div>
      </div>

      {error && (
        <div className="bg-red-900/20 border border-red-500/50 rounded-lg p-4 mb-6 text-red-400 text-sm">
          {error}
        </div>
      )}

      {alerts.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-slate-500 border-2 border-dashed border-slate-800 rounded-xl">
          <ShieldCheck size={48} className="mb-4 opacity-50" />
          <p className="text-lg font-mono">No Active Threats Detected</p>
          <p className="text-sm mt-2 max-w-md text-center">
            Your watched vendors are currently clear of recent data breaches or major security incidents.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {alerts.map(alert => (
            <div 
              key={alert.id} 
              className={clsx(
                "relative overflow-hidden rounded-xl border p-6 transition-all",
                alert.is_read 
                  ? "bg-slate-900/50 border-slate-800 opacity-60" 
                  : "bg-slate-900 border-slate-700 shadow-lg"
              )}
            >
              {/* Unread indicator strip */}
              {!alert.is_read && (
                <div className="absolute left-0 top-0 bottom-0 w-1 bg-fuchsia-500"></div>
              )}
              
              <div className="flex items-start justify-between gap-6">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-3">
                    {getSeverityIcon(alert.severity)}
                    <span className="text-slate-200 font-bold tracking-tight">
                      {alert.vendor_name}
                    </span>
                    <span className={clsx("text-xs font-mono px-2 py-0.5 rounded border uppercase", getSeverityColor(alert.severity))}>
                      {alert.severity} SEVERITY
                    </span>
                    <span className="text-xs text-slate-500 font-mono">
                      {new Date(alert.created_at).toLocaleString()}
                    </span>
                  </div>
                  
                  <h3 className={clsx("text-lg font-semibold mb-2", alert.is_read ? "text-slate-300" : "text-white")}>
                    {alert.alert_title}
                  </h3>
                  
                  <p className="text-slate-400 text-sm leading-relaxed mb-4">
                    {alert.alert_summary}
                  </p>
                  
                  <div className="flex items-center gap-4">
                    {alert.source_url && (
                      <a 
                        href={alert.source_url} 
                        target="_blank" 
                        rel="noreferrer"
                        className="text-fuchsia-400 hover:text-fuchsia-300 text-sm flex items-center gap-1 transition-colors"
                      >
                        Read Source Article <ExternalLink size={14} />
                      </a>
                    )}
                  </div>
                </div>
                
                <div>
                  {!alert.is_read && (
                    <button 
                      onClick={() => handleMarkRead(alert.id)}
                      className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-1.5 rounded flex items-center gap-1 transition-colors border border-slate-700"
                    >
                      <Check size={14} /> Mark as Read
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// Helper for empty state icon
const ShieldCheck: React.FC<{size: number, className: string}> = ({size, className}) => (
  <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
    <path d="M9 12l2 2 4-4"></path>
  </svg>
);
