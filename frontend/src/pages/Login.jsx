import React, { useState } from "react";
import { useAuth } from "../lib/auth";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { formatApiErrorDetail } from "../lib/api";
import { Loader2 } from "lucide-react";
import InstallPWAButton from "../components/InstallPWAButton";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      await login(email, password);
      nav("/");
    } catch (e) {
      setErr(formatApiErrorDetail(e.response?.data?.detail) || e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#050505] flex items-center justify-center px-6">
      <div className="w-full max-w-md">
        <div className="mb-8 text-left">
          <div className="wm-label mb-2">A.S.D. Gestionale</div>
          <h1 className="font-display text-4xl sm:text-5xl font-black tracking-tighter leading-none">
            WOLF'S<br /><span className="text-[#007AFF]">MIND</span>
          </h1>
          <p className="mt-4 text-white/60 text-sm">
            Accedi con le tue credenziali per gestire tesserati, ricevute e movimenti.
          </p>
        </div>

        <form onSubmit={submit} className="wm-card p-6 space-y-4" data-testid="login-form">
          <div className="space-y-2">
            <Label htmlFor="email" className="wm-label">Email</Label>
            <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              required autoComplete="email" data-testid="login-email-input"
              className="bg-black/40 border-white/10 focus:border-[#007AFF] focus:ring-[#007AFF]/30 h-11" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password" className="wm-label">Password</Label>
            <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              required autoComplete="current-password" data-testid="login-password-input"
              className="bg-black/40 border-white/10 focus:border-[#007AFF] focus:ring-[#007AFF]/30 h-11" />
          </div>

          {err && (
            <div data-testid="login-error" className="text-sm text-[#FF3B30] py-2 px-3
                 bg-[#FF3B30]/10 border border-[#FF3B30]/30 rounded">
              {err}
            </div>
          )}

          <Button type="submit" disabled={loading} data-testid="login-submit-button"
            className="w-full h-11 bg-[#007AFF] hover:bg-[#005BB5] text-white font-semibold">
            {loading ? <Loader2 className="animate-spin" size={18} /> : "Accedi"}
          </Button>
        </form>

        <div className="mt-6 text-center text-xs text-white/40">
          Contatta l'amministratore se hai dimenticato le credenziali.
        </div>

        <div className="mt-6">
          <InstallPWAButton />
          <div className="text-center text-[11px] text-white/40 mt-1">
            Installa l'app sul tuo smartphone per un accesso rapido a schermo intero.
          </div>
        </div>
      </div>
    </div>
  );
}
