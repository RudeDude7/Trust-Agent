import React, { useState } from 'react';
import { uploadPolicy, runAnalysis } from '../api';
import type { AnalysisResponse } from '../types';
import { UploadCloud, Shield, CheckCircle2, Building, ChevronRight, RefreshCw, ArrowLeft } from 'lucide-react';
import clsx from 'clsx';

interface WizardProps {
  onAnalysisComplete: (res: AnalysisResponse) => void;
}

export const Wizard: React.FC<WizardProps> = ({ onAnalysisComplete }) => {
  const [step, setStep] = useState<1 | 2>(1);
  const [internalFile, setInternalFile] = useState<File | null>(null);
  const [vendorFile, setVendorFile] = useState<File | null>(null);
  const [vendorName, setVendorName] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [progressMsg, setProgressMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>, setFile: React.Dispatch<React.SetStateAction<File | null>>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleUploads = async () => {
    if (!internalFile || !vendorFile) {
      setError("Please select both policies before proceeding.");
      return;
    }
    
    setIsUploading(true);
    setError(null);
    try {
      await uploadPolicy(internalFile, 'internal');
      await uploadPolicy(vendorFile, 'vendor');
      setStep(2);
    } catch (err: any) {
      setError(err.message || "Failed to upload policies.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleAnalyze = async () => {
    if (!vendorName.trim()) {
      setError("Please enter a vendor name.");
      return;
    }

    setIsAnalyzing(true);
    setProgressMsg("Booting multi-agent system...");
    setError(null);
    try {
      const res = await runAnalysis(vendorName, undefined, (msg) => {
        setProgressMsg(msg);
      });
      onAnalysisComplete(res);
    } catch (err: any) {
      setError(err.message || "Analysis failed.");
    } finally {
      setIsAnalyzing(false);
      setProgressMsg(null);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-full p-8 w-full max-w-4xl mx-auto">
      
      {/* Signature Abstract Illustration */}
      <div className="mb-12 flex justify-center items-center relative w-full h-48 pointer-events-none">
        <div className="absolute inset-0 flex justify-center items-center">
          {/* Abstract geometric shapes representing connection/security */}
          <svg width="300" height="200" viewBox="0 0 300 200" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="50" y="40" width="120" height="120" rx="30" fill="#ea580c" fillOpacity="0.1" />
            <circle cx="210" cy="130" r="45" fill="#ea580c" fillOpacity="0.15" />
            <path d="M 120 100 Q 160 50 210 130" stroke="#ea580c" strokeWidth="4" strokeLinecap="round" strokeDasharray="8 8" opacity="0.6" />
            <rect x="80" y="70" width="60" height="60" rx="16" fill="#ea580c" />
            <circle cx="110" cy="100" r="12" fill="#ffffff" />
          </svg>
        </div>
        <div className="relative z-10 text-center mt-32">
          <h1 className="text-4xl font-heading font-bold text-stone-900 tracking-tight">Trust Agent</h1>
          <p className="text-stone-500 mt-2 text-lg">AI-powered vendor due diligence & gap analysis</p>
        </div>
      </div>

      <div className="w-full bg-white border border-stone-200/60 rounded-3xl shadow-soft-lg overflow-hidden">
        
        {/* Header */}
        <div className="bg-stone-50/50 px-8 py-6 border-b border-stone-100 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-heading font-semibold text-stone-800 flex items-center gap-2">
              <Shield className="text-accent-600" size={24} />
              New Assessment
            </h2>
          </div>
          <div className="flex gap-3">
            <div className={clsx("w-2.5 h-2.5 rounded-full transition-colors", step >= 1 ? "bg-accent-500 shadow-[0_0_8px_rgba(234,88,12,0.4)]" : "bg-stone-200")} />
            <div className={clsx("w-2.5 h-2.5 rounded-full transition-colors", step >= 2 ? "bg-accent-500 shadow-[0_0_8px_rgba(234,88,12,0.4)]" : "bg-stone-200")} />
          </div>
        </div>

        <div className="p-8 lg:p-10">
          {error && (
            <div className="mb-8 p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm flex items-start gap-3 shadow-sm">
              <Shield size={16} className="mt-0.5 flex-shrink-0 text-red-500" />
              <span className="font-medium">{error}</span>
            </div>
          )}

          {step === 1 ? (
            <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
              <div className="grid md:grid-cols-2 gap-8">
                
                {/* Internal Policy Upload */}
                <div className={clsx("relative group rounded-2xl border-2 border-dashed p-10 text-center transition-all cursor-pointer",
                  internalFile ? "border-emerald-200 bg-emerald-50/50" : "border-stone-200 bg-stone-50 hover:border-accent-300 hover:bg-accent-50/30"
                )}>
                  <input 
                    type="file" 
                    accept=".pdf" 
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10" 
                    onChange={(e) => handleFileChange(e, setInternalFile)}
                  />
                  <div className="flex flex-col items-center gap-4">
                    <div className={clsx("p-4 rounded-full transition-colors shadow-sm", internalFile ? "bg-emerald-100 text-emerald-600" : "bg-white text-stone-400 border border-stone-200")}>
                      {internalFile ? <CheckCircle2 size={32} /> : <Building size={32} />}
                    </div>
                    <div>
                      <h3 className="font-heading font-semibold text-stone-800 text-lg">Internal Policy</h3>
                      <p className="text-sm text-stone-500 mt-1">Upload your master policy PDF</p>
                    </div>
                    {internalFile && <span className="text-sm text-emerald-700 font-medium truncate max-w-[200px] bg-emerald-100/50 px-3 py-1 rounded-lg">{internalFile.name}</span>}
                  </div>
                </div>

                {/* Vendor Policy Upload */}
                <div className={clsx("relative group rounded-2xl border-2 border-dashed p-10 text-center transition-all cursor-pointer",
                  vendorFile ? "border-accent-200 bg-accent-50/50" : "border-stone-200 bg-stone-50 hover:border-accent-300 hover:bg-accent-50/30"
                )}>
                  <input 
                    type="file" 
                    accept=".pdf" 
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10" 
                    onChange={(e) => handleFileChange(e, setVendorFile)}
                  />
                  <div className="flex flex-col items-center gap-4">
                    <div className={clsx("p-4 rounded-full transition-colors shadow-sm", vendorFile ? "bg-accent-100 text-accent-600" : "bg-white text-stone-400 border border-stone-200")}>
                      {vendorFile ? <CheckCircle2 size={32} /> : <UploadCloud size={32} />}
                    </div>
                    <div>
                      <h3 className="font-heading font-semibold text-stone-800 text-lg">Vendor TOS/Policy</h3>
                      <p className="text-sm text-stone-500 mt-1">Upload target vendor document</p>
                    </div>
                    {vendorFile && <span className="text-sm text-accent-700 font-medium truncate max-w-[200px] bg-accent-100/50 px-3 py-1 rounded-lg">{vendorFile.name}</span>}
                  </div>
                </div>

              </div>

              <div className="flex justify-end mt-10">
                <button
                  onClick={handleUploads}
                  disabled={!internalFile || !vendorFile || isUploading}
                  className="bg-stone-800 hover:bg-stone-900 text-white px-8 py-3.5 rounded-xl font-heading font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 shadow-sm"
                >
                  {isUploading ? (
                    <><RefreshCw className="animate-spin" size={18} /> Uploading...</>
                  ) : (
                    <>Next Step <ChevronRight size={18} /></>
                  )}
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-8 animate-in fade-in slide-in-from-right-8 duration-500 max-w-2xl mx-auto">
              <div className="bg-stone-50 p-8 rounded-2xl border border-stone-200">
                <label className="block text-sm font-semibold text-stone-500 mb-3 uppercase tracking-wider">Target Vendor Name</label>
                <input
                  type="text"
                  value={vendorName}
                  onChange={(e) => {
                    setVendorName(e.target.value);
                    setError(null);
                  }}
                  placeholder="e.g. Meta, AWS, Stripe..."
                  className="w-full bg-white border border-stone-200 rounded-xl px-5 py-4 text-xl text-stone-800 placeholder:text-stone-300 focus:outline-none focus:border-accent-500 focus:ring-4 focus:ring-accent-500/10 transition-all font-heading shadow-sm"
                  onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
                />
              </div>

              <div className="flex justify-between items-center mt-10">
                <button
                  onClick={() => setStep(1)}
                  disabled={isAnalyzing}
                  className="text-stone-400 hover:text-stone-700 px-4 py-2 font-semibold flex items-center gap-2 transition-colors disabled:opacity-50"
                >
                  <ArrowLeft size={18} /> Back
                </button>

                <button
                  onClick={handleAnalyze}
                  disabled={!vendorName.trim() || isAnalyzing}
                  className="bg-accent-600 hover:bg-accent-700 text-white px-8 py-4 rounded-xl font-heading font-bold text-lg tracking-wide transition-all disabled:opacity-50 flex flex-col items-center justify-center min-w-[320px] shadow-soft hover:shadow-soft-lg hover:-translate-y-0.5"
                >
                  {isAnalyzing ? (
                    <>
                      <div className="flex items-center gap-3">
                        <RefreshCw className="animate-spin" size={20} /> 
                        <span>Analyzing Gap...</span>
                      </div>
                      {progressMsg && (
                        <div className="text-[11px] text-accent-200 mt-2 animate-pulse tracking-wide font-normal">
                          {progressMsg}
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="flex items-center gap-3">
                      Run Assessment
                    </div>
                  )}
                </button>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
};
