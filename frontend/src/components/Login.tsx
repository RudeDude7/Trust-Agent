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
    <div className="flex h-screen w-full items-center justify-center bg-stone-50 selection:bg-accent-500/30">
      <div className="w-full max-w-md p-10 bg-white border border-stone-200 rounded-3xl shadow-soft-xl animate-in fade-in zoom-in-95">
        <div className="flex flex-col items-center gap-3 justify-center mb-10">
          <div className="p-4 bg-stone-50 rounded-2xl border border-stone-200 shadow-sm">
            <Shield size={40} className="text-accent-600" />
          </div>
          <h1 className="text-3xl font-heading text-stone-900 font-black tracking-tight mt-3">Trust Agent</h1>
          <p className="text-stone-500 text-sm font-semibold tracking-widest uppercase">Secure Authentication</p>
        </div>

        <form onSubmit={handleAuth} className="space-y-5">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-stone-50 border border-stone-200 rounded-xl px-4 py-3 text-stone-800 focus:outline-none focus:border-accent-500 focus:ring-2 focus:ring-accent-500/20 font-sans transition-all shadow-inner"
              required
              placeholder="agent@example.com"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-stone-50 border border-stone-200 rounded-xl px-4 py-3 text-stone-800 focus:outline-none focus:border-accent-500 focus:ring-2 focus:ring-accent-500/20 font-sans transition-all shadow-inner"
              required
              placeholder="••••••••"
            />
          </div>

          {isSignUp && (
            <div className="bg-stone-50 border border-stone-200 rounded-xl p-5 space-y-3 text-sm font-medium shadow-sm">
              <div className="text-stone-500 mb-2 font-bold uppercase tracking-wider text-xs">Password Requirements</div>
              <div className={clsx("flex items-center gap-2.5", password.length >= 8 ? "text-emerald-600 font-bold" : "text-stone-400")}>
                {password.length >= 8 ? <CheckCircle2 size={16} /> : <Circle size={16} />}
                At least 8 characters
              </div>
              <div className={clsx("flex items-center gap-2.5", /[A-Z]/.test(password) ? "text-emerald-600 font-bold" : "text-stone-400")}>
                {/[A-Z]/.test(password) ? <CheckCircle2 size={16} /> : <Circle size={16} />}
                One uppercase letter
              </div>
              <div className={clsx("flex items-center gap-2.5", /[a-z]/.test(password) ? "text-emerald-600 font-bold" : "text-stone-400")}>
                {/[a-z]/.test(password) ? <CheckCircle2 size={16} /> : <Circle size={16} />}
                One lowercase letter
              </div>
              <div className={clsx("flex items-center gap-2.5", /[0-9]/.test(password) ? "text-emerald-600 font-bold" : "text-stone-400")}>
                {/[0-9]/.test(password) ? <CheckCircle2 size={16} /> : <Circle size={16} />}
                One number
              </div>
              <div className={clsx("flex items-center gap-2.5", /[^A-Za-z0-9]/.test(password) ? "text-emerald-600 font-bold" : "text-stone-400")}>
                {/[^A-Za-z0-9]/.test(password) ? <CheckCircle2 size={16} /> : <Circle size={16} />}
                One special symbol
              </div>
            </div>
          )}

          {error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm font-semibold text-center">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-accent-600 hover:bg-accent-700 text-white font-bold uppercase tracking-widest py-3.5 rounded-xl transition-colors flex items-center justify-center gap-2 mt-4 disabled:opacity-50 shadow-sm"
          >
            {loading && <Loader2 size={18} className="animate-spin" />}
            {isSignUp ? 'REGISTER' : 'LOGIN'}
          </button>
        </form>

        <div className="mt-8 text-center">
          <button
            onClick={() => {
              setIsSignUp(!isSignUp);
              setError(null);
            }}
            className="text-sm font-semibold text-stone-500 hover:text-accent-600 transition-colors"
          >
            {isSignUp ? 'Already have an account? Login' : "Don't have an account? Register"}
          </button>
        </div>
      </div>
    </div>
  );
};
