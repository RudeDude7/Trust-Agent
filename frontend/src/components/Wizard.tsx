import React, { useState } from 'react';
import { uploadPolicy, analyzeVendor } from '../api';
import type { AnalysisResponse } from '../types';
import { UploadCloud, Shield, CheckCircle2, Building, ChevronRight, Loader2, ArrowLeft } from 'lucide-react';
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
    setError(null);
    try {
      const res = await analyzeVendor(vendorName);
      onAnalysisComplete(res);
    } catch (err: any) {
      setError(err.message || "Analysis failed.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen p-8 w-full max-w-4xl mx-auto">
      <div className="w-full bg-slate-900 border border-slate-700/50 rounded-xl shadow-2xl overflow-hidden backdrop-blur-sm">
        
        {/* Header */}
        <div className="bg-slate-800/80 px-8 py-6 border-b border-slate-700/50 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-3">
              <Shield className="text-cyan-400" size={28} />
              Vigilance OS
            </h1>
            <p className="text-slate-400 text-sm mt-1 font-mono">Comparative Vendor Risk Assessment</p>
          </div>
          <div className="flex gap-2">
            <div className={clsx("w-3 h-3 rounded-full transition-colors", step >= 1 ? "bg-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.5)]" : "bg-slate-700")} />
            <div className={clsx("w-3 h-3 rounded-full transition-colors", step >= 2 ? "bg-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.5)]" : "bg-slate-700")} />
          </div>
        </div>

        <div className="p-8">
          {error && (
            <div className="mb-6 p-4 bg-red-900/20 border border-red-500/50 rounded-lg text-red-400 text-sm font-mono flex items-start gap-3">
              <Shield size={16} className="mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {step === 1 ? (
            <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
              <div className="grid md:grid-cols-2 gap-6">
                
                {/* Internal Policy Upload */}
                <div className="relative group rounded-xl border-2 border-dashed border-slate-700 bg-slate-800/30 p-8 text-center transition-all hover:border-cyan-500/50 hover:bg-slate-800/50">
                  <input 
                    type="file" 
                    accept=".pdf" 
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10" 
                    onChange={(e) => handleFileChange(e, setInternalFile)}
                  />
                  <div className="flex flex-col items-center gap-4">
                    <div className={clsx("p-4 rounded-full transition-colors", internalFile ? "bg-emerald-900/30 text-emerald-400" : "bg-slate-800 text-slate-400")}>
                      {internalFile ? <CheckCircle2 size={32} /> : <Building size={32} />}
                    </div>
                    <div>
                      <h3 className="font-semibold text-slate-200">Upload Internal Policy</h3>
                      <p className="text-xs text-slate-500 font-mono mt-2">(e.g., FinWise Master Policy.pdf)</p>
                    </div>
                    {internalFile && <span className="text-sm text-cyan-400 font-mono truncate max-w-[200px]">{internalFile.name}</span>}
                  </div>
                </div>

                {/* Vendor Policy Upload */}
                <div className="relative group rounded-xl border-2 border-dashed border-slate-700 bg-slate-800/30 p-8 text-center transition-all hover:border-amber-500/50 hover:bg-slate-800/50">
                  <input 
                    type="file" 
                    accept=".pdf" 
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10" 
                    onChange={(e) => handleFileChange(e, setVendorFile)}
                  />
                  <div className="flex flex-col items-center gap-4">
                    <div className={clsx("p-4 rounded-full transition-colors", vendorFile ? "bg-amber-900/30 text-amber-400" : "bg-slate-800 text-slate-400")}>
                      {vendorFile ? <CheckCircle2 size={32} /> : <UploadCloud size={32} />}
                    </div>
                    <div>
                      <h3 className="font-semibold text-slate-200">Upload Vendor Policy</h3>
                      <p className="text-xs text-slate-500 font-mono mt-2">(e.g., Target Vendor TOS.pdf)</p>
                    </div>
                    {vendorFile && <span className="text-sm text-amber-400 font-mono truncate max-w-[200px]">{vendorFile.name}</span>}
                  </div>
                </div>

              </div>

              <div className="flex justify-end mt-8">
                <button
                  onClick={handleUploads}
                  disabled={!internalFile || !vendorFile || isUploading}
                  className="bg-cyan-600 hover:bg-cyan-500 text-white px-6 py-3 rounded-lg font-mono font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {isUploading ? (
                    <><Loader2 className="animate-spin" size={18} /> INGESTING...</>
                  ) : (
                    <>PROCEED TO ANALYSIS <ChevronRight size={18} /></>
                  )}
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-8 animate-in fade-in slide-in-from-right-8 duration-500">
              <div className="bg-slate-800/50 p-6 rounded-xl border border-slate-700">
                <label className="block text-sm font-mono text-slate-400 mb-3 uppercase tracking-widest">Target Vendor Name</label>
                <input
                  type="text"
                  value={vendorName}
                  onChange={(e) => {
                    setVendorName(e.target.value);
                    setError(null);
                  }}
                  placeholder="e.g. Meta, AWS, Cloudflare..."
                  className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-4 text-xl text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all font-mono"
                  onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
                />
              </div>

              <div className="flex justify-between mt-8">
                <button
                  onClick={() => setStep(1)}
                  disabled={isAnalyzing}
                  className="text-slate-400 hover:text-slate-200 px-4 py-2 font-mono flex items-center gap-2 transition-colors disabled:opacity-50"
                >
                  <ArrowLeft size={18} /> BACK
                </button>

                <button
                  onClick={handleAnalyze}
                  disabled={!vendorName.trim() || isAnalyzing}
                  className="bg-red-600 hover:bg-red-500 text-white px-8 py-4 rounded-lg font-mono font-bold tracking-wider transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-3 shadow-[0_0_15px_rgba(220,38,38,0.4)]"
                >
                  {isAnalyzing ? (
                    <><Loader2 className="animate-spin" size={20} /> INITIATING COMPARATIVE ANALYSIS...</>
                  ) : (
                    <>EXECUTE AUDIT</>
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
