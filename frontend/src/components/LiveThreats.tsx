import React, { useEffect, useState } from 'react';
import { ShieldAlert, AlertTriangle, AlertCircle, Info, ExternalLink, Check, Bell } from 'lucide-react';
import type { ThreatAlert } from '../types';
import { fetchThreatAlerts, markAlertRead, fetchWatchedVendors, unwatchVendor } from '../api';
import { X } from 'lucide-react';
import clsx from 'clsx';

export const LiveThreats: React.FC = () => {
  const [alerts, setAlerts] = useState<ThreatAlert[]>([]);
  const [watchedVendors, setWatchedVendors] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAlerts();
    loadWatchedVendors();
  }, []);

  const loadWatchedVendors = async () => {
    try {
      const data = await fetchWatchedVendors();
      setWatchedVendors(data);
    } catch (err) {
      console.error('Failed to load watched vendors', err);
    }
  };

  const handleUnwatch = async (vendorName: string) => {
    try {
      await unwatchVendor(vendorName);
      setWatchedVendors(prev => prev.filter(v => v.vendor_name !== vendorName));
    } catch (err) {
      console.error('Failed to unwatch', err);
    }
  };

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
      case 'CRITICAL': return 'bg-red-50 text-red-600 border-red-200';
      case 'HIGH': return 'bg-orange-50 text-orange-600 border-orange-200';
      case 'MEDIUM': return 'bg-amber-50 text-amber-600 border-amber-200';
      default: return 'bg-blue-50 text-blue-600 border-blue-200';
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-stone-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent-600"></div>
      </div>
    );
  }

  const unreadCount = alerts.filter(a => !a.is_read).length;

  return (
    <div className="flex-1 flex flex-col h-full p-8 overflow-y-auto w-full max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-10">
        <div>
          <h1 className="text-3xl font-bold font-heading text-stone-900 tracking-tight flex items-center gap-3">
            <Bell className="text-accent-600" size={28} />
            Live Threat & Breach Feed
          </h1>
          <p className="text-stone-500 mt-2 text-lg">Continuous OSINT monitoring for your watched vendors.</p>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl px-5 py-3 flex items-center gap-4 shadow-sm">
          <div className="text-stone-500 font-semibold text-sm uppercase tracking-wider">Unread Alerts</div>
          <div className="text-3xl font-heading font-bold text-accent-600">{unreadCount}</div>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-8 text-red-600 font-medium">
          {error}
        </div>
      )}

      <div className="grid md:grid-cols-4 gap-8">
        <div className="md:col-span-3">
          {alerts.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center text-stone-400 border-2 border-dashed border-stone-200 rounded-3xl p-16 bg-white">
              <ShieldCheck size={48} className="mb-4 text-stone-300" />
              <p className="text-xl font-heading font-bold text-stone-500">No Active Threats Detected</p>
              <p className="text-sm mt-2 max-w-md text-center text-stone-400">
                Your watched vendors are currently clear of recent data breaches or major security incidents.
              </p>
            </div>
          ) : (
        <div className="space-y-6">
          {alerts.map(alert => (
            <div 
              key={alert.id} 
              className={clsx(
                "relative overflow-hidden rounded-2xl border p-6 transition-all shadow-soft",
                alert.is_read 
                  ? "bg-stone-50 border-stone-200 opacity-60" 
                  : "bg-white border-stone-200 hover:shadow-soft-lg hover:-translate-y-0.5"
              )}
            >
              {/* Unread indicator strip */}
              {!alert.is_read && (
                <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-accent-500"></div>
              )}
              
              <div className="flex items-start justify-between gap-6 pl-2">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-4">
                    {getSeverityIcon(alert.severity)}
                    <span className="text-stone-900 font-bold tracking-tight">
                      {alert.vendor_name}
                    </span>
                    <span className={clsx("text-[10px] font-bold px-2.5 py-1 rounded-md border uppercase tracking-widest", getSeverityColor(alert.severity))}>
                      {alert.severity} SEVERITY
                    </span>
                    <span className="text-xs text-stone-400 font-medium">
                      {new Date(alert.created_at).toLocaleString()}
                    </span>
                  </div>
                  
                  <h3 className={clsx("text-xl font-heading font-bold mb-3", alert.is_read ? "text-stone-600" : "text-stone-900")}>
                    {alert.alert_title}
                  </h3>
                  
                  <p className="text-stone-600 text-sm leading-relaxed mb-5">
                    {alert.alert_summary}
                  </p>
                  
                  <div className="flex items-center gap-4">
                    {alert.source_url && (
                      <a 
                        href={alert.source_url} 
                        target="_blank" 
                        rel="noreferrer"
                        className="text-accent-600 hover:text-accent-700 font-semibold text-sm flex items-center gap-1.5 transition-colors bg-accent-50 hover:bg-accent-100 px-3 py-1.5 rounded-lg"
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
                      className="text-xs font-semibold bg-white hover:bg-stone-50 text-stone-600 px-4 py-2 rounded-xl flex items-center gap-1.5 transition-colors border border-stone-200 shadow-sm"
                    >
                      <Check size={14} className="text-emerald-500" /> Mark as Read
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
          </div>
        )}
        </div>

        <div className="md:col-span-1">
          <div className="bg-white border border-stone-200 rounded-3xl overflow-hidden shadow-soft sticky top-8">
            <div className="bg-stone-50 p-5 border-b border-stone-200">
              <h3 className="font-bold text-stone-600 text-sm uppercase tracking-widest flex items-center justify-between">
                Watched Vendors
                <span className="bg-accent-100 text-accent-700 font-bold text-xs px-2.5 py-0.5 rounded-full">
                  {watchedVendors.length}
                </span>
              </h3>
            </div>
            
            {watchedVendors.length === 0 ? (
              <div className="p-8 text-center text-stone-400 text-sm font-medium italic">
                No vendors being monitored.
              </div>
            ) : (
              <div className="divide-y divide-stone-100 max-h-[500px] overflow-y-auto">
                {watchedVendors.map(v => (
                  <div key={v.vendor_name} className="p-4 flex items-center justify-between hover:bg-stone-50 transition-colors group">
                    <span className="text-stone-700 font-semibold text-sm truncate pr-2">
                      {v.vendor_name}
                    </span>
                    <button 
                      onClick={() => handleUnwatch(v.vendor_name)}
                      className="p-1.5 text-stone-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors opacity-0 group-hover:opacity-100 shadow-sm border border-transparent hover:border-red-100"
                      title="Stop Watching"
                    >
                      <X size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
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
