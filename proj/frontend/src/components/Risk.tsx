import { useEffect, useState } from "react";
import { motion, animate } from "framer-motion";
import { LV, RiskBadge } from "./ui";
export function RiskGauge({ probability, level }: { probability: number; level: string }) {
  const [v, setV] = useState(0); const c = (LV[level] || LV.low).c; const R = 80, C = 2 * Math.PI * R;
  useEffect(() => { const a = animate(0, probability * 100, { duration: .9, onUpdate: setV }); return () => a.stop(); }, [probability]);
  return <div className="flex flex-col items-center gap-2" role="img" aria-label={`Risk probability ${(probability * 100).toFixed(1)} percent, ${level}`}>
    <svg width="200" height="200" viewBox="0 0 200 200"><circle cx="100" cy="100" r={R} fill="none" stroke="#E2E8F0" strokeWidth="14" />
      <motion.circle cx="100" cy="100" r={R} fill="none" stroke={c} strokeWidth="14" strokeLinecap="round" strokeDasharray={C} initial={{ strokeDashoffset: C }} animate={{ strokeDashoffset: C * (1 - probability) }} transition={{ duration: .9 }} transform="rotate(-90 100 100)" />
      <text x="100" y="98" textAnchor="middle" className="fill-ink" fontSize="36" fontWeight="700">{v.toFixed(0)}%</text><text x="100" y="124" textAnchor="middle" className="fill-muted" fontSize="11">CREDIT RISK SCORE</text></svg>
    <RiskBadge level={level} /></div>;
}
export function ShapBars({ items, onSelect, selected }: any) {
  const max = Math.max(...items.map((i: any) => Math.abs(i.shap)), 1e-9);
  return <div className="space-y-1">{items.map((i: any) => <button key={i.feature} onClick={() => onSelect(i)} className={`block w-full rounded-lg p-2 text-left hover:bg-soft ${selected?.feature === i.feature ? "bg-soft ring-1 ring-primary" : ""}`}>
    <div className="mb-1 flex justify-between gap-2 text-xs"><span className="font-medium">{i.label}</span><span className="tabular-nums text-muted">{i.shap > 0 ? "+" : ""}{i.shap.toFixed(3)}</span></div>
    <div className="h-2.5 rounded bg-slate-100"><motion.div initial={{ width: 0 }} animate={{ width: `${(Math.abs(i.shap) / max) * 100}%` }} transition={{ duration: .6 }} className="h-full rounded" style={{ background: i.shap > 0 ? "var(--r-high)" : "var(--c-success)" }} /></div></button>)}</div>;
}
