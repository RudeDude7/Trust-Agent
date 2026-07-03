import React, { useState } from 'react';
import { supabase } from '../supabase';
import { Shield, Loader2, CheckCircle2, Circle } from 'lucide-react';
import clsx from 'clsx';

export const Login: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSignUp, setIsSignUp] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    if (!email.toLowerCase().endsWith('@gmail.com')) {
      setError("Only @gmail.com email addresses are permitted.");
      setLoading(false);
      return;
    }

    const hasMinLength = password.length >= 8;
    const hasUpper = /[A-Z]/.test(password);
    const hasLower = /[a-z]/.test(password);
    const hasNumber = /[0-9]/.test(password);
    const hasSymbol = /[^A-Za-z0-9]/.test(password);
    const isValidPassword = hasMinLength && hasUpper && hasLower && hasNumber && hasSymbol;

    if (isSignUp && !isValidPassword) {
      setError("Please ensure your password meets all requirements.");
      setLoading(false);
      return;
    }

    try {
      if (isSignUp) {
        const { error } = await supabase.auth.signUp({
          email,
          password,
        });
        if (error) throw error;
        // Sometimes signup doesn't auto-login if email confirmation is required,
        // but for this MVP we'll assume it either logs in or shows a message.
        setError("Check your email for the login link if required, or you are now signed up!");
      } else {
        const { error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (error) throw error;
      }
    } catch (err: any) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-full items-center justify-center bg-background selection:bg-cyan-500/30">
      <div className="w-full max-w-md p-8 bg-slate-900 border border-slate-800 rounded-xl shadow-2xl animate-in fade-in zoom-in-95">
        <div className="flex flex-col items-center gap-3 justify-center mb-8">
          <div className="p-4 bg-slate-800 rounded-full border border-slate-700 shadow-inner">
            <Shield size={40} className="text-cyan-400" />
          </div>
          <h1 className="text-2xl font-mono text-slate-100 font-bold tracking-tight mt-2">TRUST AGENT</h1>
          <p className="text-slate-500 text-sm font-mono tracking-widest uppercase">Secure Authentication</p>
        </div>

        <form onSubmit={handleAuth} className="space-y-4">
          <div>
            <label className="block text-xs font-mono text-slate-400 mb-1">EMAIL</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-3 text-slate-200 focus:outline-none focus:border-cyan-500 font-sans transition-colors"
              required
              placeholder="agent@example.com"
            />
          </div>
          <div>
            <label className="block text-xs font-mono text-slate-400 mb-1">PASSWORD</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-3 text-slate-200 focus:outline-none focus:border-cyan-500 font-sans transition-colors"
              required
              placeholder="••••••••"
            />
          </div>

          {isSignUp && (
            <div className="bg-slate-950 border border-slate-800 rounded-lg p-4 space-y-2 text-xs font-mono">
              <div className="text-slate-400 mb-2 font-semibold">PASSWORD REQUIREMENTS</div>
              <div className={clsx("flex items-center gap-2", password.length >= 8 ? "text-emerald-400" : "text-slate-500")}>
                {password.length >= 8 ? <CheckCircle2 size={14} /> : <Circle size={14} />}
                At least 8 characters
              </div>
              <div className={clsx("flex items-center gap-2", /[A-Z]/.test(password) ? "text-emerald-400" : "text-slate-500")}>
                {/[A-Z]/.test(password) ? <CheckCircle2 size={14} /> : <Circle size={14} />}
                One uppercase letter
              </div>
              <div className={clsx("flex items-center gap-2", /[a-z]/.test(password) ? "text-emerald-400" : "text-slate-500")}>
                {/[a-z]/.test(password) ? <CheckCircle2 size={14} /> : <Circle size={14} />}
                One lowercase letter
              </div>
              <div className={clsx("flex items-center gap-2", /[0-9]/.test(password) ? "text-emerald-400" : "text-slate-500")}>
                {/[0-9]/.test(password) ? <CheckCircle2 size={14} /> : <Circle size={14} />}
                One number
              </div>
              <div className={clsx("flex items-center gap-2", /[^A-Za-z0-9]/.test(password) ? "text-emerald-400" : "text-slate-500")}>
                {/[^A-Za-z0-9]/.test(password) ? <CheckCircle2 size={14} /> : <Circle size={14} />}
                One special symbol
              </div>
            </div>
          )}

          {error && (
            <div className="p-3 bg-red-900/20 border border-red-900/50 rounded text-red-400 text-sm font-mono text-center">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-cyan-600 hover:bg-cyan-500 text-white font-mono font-bold tracking-wider py-3 rounded-lg transition-colors flex items-center justify-center gap-2 mt-2 disabled:opacity-50"
          >
            {loading && <Loader2 size={16} className="animate-spin" />}
            {isSignUp ? 'REGISTER' : 'LOGIN'}
          </button>
        </form>

        <div className="mt-6 text-center">
          <button
            onClick={() => {
              setIsSignUp(!isSignUp);
              setError(null);
            }}
            className="text-sm font-mono text-slate-500 hover:text-cyan-400 transition-colors"
          >
            {isSignUp ? 'Already have an account? Login' : "Don't have an account? Register"}
          </button>
        </div>
      </div>
    </div>
  );
};
