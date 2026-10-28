import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Brain, Eye, BellRing, Lock, Loader2, MailCheck, UserRound } from "lucide-react";
import { useAuth } from "../context/Auth";
import { auth } from "../services";
import Background from "../components/Background";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [otp, setOtp] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [notice, setNotice] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const F = [[Brain, "AI Risk Analysis"], [Eye, "Explainable Predictions"], [BellRing, "Early Warning"], [Lock, "Secure Access"]];

  const submitSignin = async (e: any) => {
    e.preventDefault(); setBusy(true); setErr(""); setNotice("");
    try { await login(email.trim(), pw); nav("/"); }
    catch (x: any) { setErr(x.message || "Unable to sign in."); }
    finally { setBusy(false); }
  };

  const requestOtp = async (e: any) => {
    e.preventDefault(); setBusy(true); setErr(""); setNotice("");
    if (pw.length < 8) { setErr("Use a password with at least 8 characters."); setBusy(false); return; }
    if (pw !== confirm) { setErr("The passwords do not match."); setBusy(false); return; }
    try {
      const r: any = await auth.requestSignupOtp(email.trim(), name.trim(), pw);
      setOtpSent(true); setNotice(r.message || "Verification code sent. Check your inbox and spam folder.");
    } catch (x: any) { setErr(x.message || "Could not send verification code."); }
    finally { setBusy(false); }
  };

  const verifyOtp = async (e: any) => {
    e.preventDefault(); setBusy(true); setErr(""); setNotice("");
    try {
      const r: any = await auth.verifySignupOtp(email.trim(), otp.trim());
      setMode("signin"); setOtpSent(false); setOtp(""); setConfirm("");
      setNotice(r.message || "Account created. Sign in with your email and password.");
    } catch (x: any) { setErr(x.message || "Could not verify code."); }
    finally { setBusy(false); }
  };

  return <div className="grid min-h-screen lg:grid-cols-2"><Background />
    <div className="flex flex-col justify-center p-10 lg:p-20"><motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}>
      <h1 className="text-4xl font-bold leading-tight text-slate-900 lg:text-5xl">Explainable AI for Smarter <span className="bg-gradient-to-r from-primary to-sky-400 bg-clip-text text-transparent">Credit Risk</span> Decisions</h1>
      <p className="mt-4 max-w-lg text-slate-600">Predict enterprise financial risk, understand the factors behind every prediction, and identify early warning signals.</p>
      <div className="mt-8 grid max-w-md grid-cols-2 gap-3">{F.map(([I, t]: any) => <div key={t} className="flex items-center gap-2 rounded-xl border border-line bg-white/70 p-3 text-sm font-medium backdrop-blur"><I size={18} className="text-primary" />{t}</div>)}</div>
    </motion.div></div>
    <div className="flex items-center justify-center p-6"><motion.div initial={{ opacity: 0, scale: .97 }} animate={{ opacity: 1, scale: 1 }} className="w-full max-w-sm rounded-2xl border border-line bg-white/90 p-8 shadow-card backdrop-blur">
      <div className="mb-5 grid grid-cols-2 gap-2 rounded-xl bg-slate-100 p-1">
        <button type="button" onClick={() => { setMode("signin"); setErr(""); setNotice(""); }} className={`rounded-lg px-3 py-2 text-sm font-semibold ${mode === "signin" ? "bg-white text-primary shadow-sm" : "text-slate-500"}`}>Sign in</button>
        <button type="button" onClick={() => { setMode("signup"); setErr(""); setNotice(""); }} className={`rounded-lg px-3 py-2 text-sm font-semibold ${mode === "signup" ? "bg-white text-primary shadow-sm" : "text-slate-500"}`}>Create account</button>
      </div>
      {mode === "signin" ? <form onSubmit={submitSignin} className="space-y-4">
        <h2 className="text-xl font-semibold">Welcome back</h2>
        <label className="block text-sm">Email<input className="input mt-1" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" /></label>
        <label className="block text-sm">Password<input className="input mt-1" type="password" required value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="current-password" /></label>
        {notice && <p role="status" className="text-sm text-emerald-700">{notice}</p>}{err && <p role="alert" className="text-sm text-danger">{err}</p>}
        <button type="submit" disabled={busy} className="btn flex w-full items-center justify-center gap-2 bg-primary text-white">{busy && <Loader2 className="animate-spin" size={16} />}Sign in</button>
        <p className="text-xs text-slate-500">New here? Create an account and verify your email once. After that, sign in with your email and password.</p>
      </form> : <form onSubmit={otpSent ? verifyOtp : requestOtp} className="space-y-4">
        <h2 className="text-xl font-semibold">{otpSent ? "Verify your email" : "Create your account"}</h2>
        {!otpSent ? <>
          <label className="block text-sm">Full name<input className="input mt-1" type="text" required maxLength={120} value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" /></label>
          <label className="block text-sm">Email address<input className="input mt-1" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" /></label>
          <label className="block text-sm">Create password<input className="input mt-1" type="password" required minLength={8} maxLength={128} value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="new-password" /></label>
          <label className="block text-sm">Confirm password<input className="input mt-1" type="password" required minLength={8} value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" /></label>
        </> : <>
          <p className="text-sm text-slate-600">We sent a six-digit code to <strong>{email}</strong>. It expires in 10 minutes. Check spam if it isn't in your inbox.</p>
          <label className="block text-sm">Email verification code<input className="input mt-1 tracking-[0.3em]" type="text" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" minLength={6} maxLength={6} required value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))} /></label>
        </>}
        {notice && <p role="status" className="text-sm text-emerald-700">{notice}</p>}{err && <p role="alert" className="text-sm text-danger">{err}</p>}
        <button type="submit" disabled={busy} className="btn flex w-full items-center justify-center gap-2 bg-primary text-white">{busy ? <Loader2 className="animate-spin" size={16} /> : otpSent ? <MailCheck size={16} /> : <UserRound size={16} />}{otpSent ? "Verify code and create account" : "Send verification code"}</button>
        {otpSent && <button type="button" onClick={() => { setOtpSent(false); setOtp(""); setErr(""); setNotice(""); }} className="w-full text-sm text-primary">Back to signup details</button>}
      </form>}
    </motion.div></div></div>;
}
