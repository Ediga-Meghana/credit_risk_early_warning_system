import json, joblib, numpy as np, pandas as pd, shap, threading
from .core import ART
from ml.features import DESC, CATEGORY
_lock = threading.Lock(); _state = {}
def load(force=False):
    with _lock:
        if force or not _state:
            b = joblib.load(ART/"xgb_v1.joblib"); meta = json.loads((ART/"model_meta.json").read_text())
            _state.update(model=b["model"], feats=b["feats"], meta=meta, expl=shap.TreeExplainer(b["model"]))
    return _state
def describe(f):
    i = int(f.replace("Attr","")); return DESC[i]
def category(f): return CATEGORY.get(int(f.replace("Attr","")), "Other")
def feature_catalog():
    s = load(); m = s["meta"]
    return [dict(key=f, label=describe(f), category=category(f), median=m["medians"][f]) for f in s["feats"]]
def _row(values: dict):
    s = load(); m = s["meta"]; r = {}
    missing = []
    for f in s["feats"]:
        v = values.get(f)
        if v is None or v == "" or (isinstance(v, float) and np.isnan(v)): missing.append(f); v = m["medians"][f]
        v = float(v); r[f] = min(max(v, m["clip_lo"][f]), m["clip_hi"][f]) if False else v
    return pd.DataFrame([r])[s["feats"]], missing
def predict_many(rows: list[dict]):
    s = load(); frames = []; miss = []
    for r in rows: d, mi = _row(r); frames.append(d); miss.append(mi)
    X = pd.concat(frames, ignore_index=True)
    p = s["model"].predict_proba(X)[:,1]; sv = s["expl"].shap_values(X)
    return X, p, sv, miss
def explain(X_row, sv_row):
    feats = list(X_row.index); out = []
    for f, v, c in zip(feats, X_row.values, sv_row):
        out.append(dict(feature=f, label=describe(f), category=category(f), value=float(v), shap=float(c)))
    out.sort(key=lambda d: -abs(d["shap"]))
    for rank, d in enumerate(out, 1): d["rank"] = rank; d["direction"] = "increases" if d["shap"] > 0 else "decreases"
    return out
TEXT = {"Liquidity":("Liquidity Risk","Short-term liquidity indicators contributed to the predicted risk.","Review short-term liquidity, working capital and cash coverage of short-term obligations."),
 "Leverage":("Leverage Risk","High liabilities relative to assets or earnings contributed to the predicted risk.","Review leverage exposure, debt maturity profile and debt-service capacity."),
 "Profitability":("Profitability Risk","Weak profitability indicators contributed to the predicted risk.","Review profit margins, earnings trend and cost structure."),
 "Operational Efficiency":("Operational Efficiency Risk","Turnover or cost-efficiency indicators contributed to the predicted risk.","Review receivables, inventory and payables cycles and sales efficiency."),
 "Capital Structure":("Capital Structure Risk","Capital-structure indicators contributed to the predicted risk.","Review equity base, retained earnings and fixed-asset financing."),
 "Other":("Financial Indicator Risk","This indicator contributed to the predicted risk.","Review the indicator with a financial analyst.")}
def warnings_and_recs(expl, level):
    pos = [e for e in expl if e["shap"] > 0][:5]; total = sum(abs(e["shap"]) for e in expl) or 1
    warns, recs, seen = [], [], set()
    for e in pos:
        share = e["shap"]/total
        sev = "critical" if share > .25 else "high" if share > .12 else "moderate" if share > .05 else "low"
        t = TEXT[e["category"]]
        warns.append(dict(severity=sev, indicator=t[0], feature=e["label"], status="open",
            reason=f"{t[1]} ({e['label']} = {e['value']:.3g}; SHAP {e['shap']:+.3f}, {share*100:.0f}% of total attribution)."))
        if e["category"] not in seen:
            seen.add(e["category"]); recs.append(dict(title=f"Review {t[0].replace(' Risk','')}", priority="high" if sev in ("critical","high") else "medium",
                reason=t[2]+f" Driven by: {e['label']}.", category=e["category"]))
    if not warns: warns.append(dict(severity="low", indicator="No adverse drivers", feature="-", status="info", reason="No indicator pushed the prediction toward higher risk."))
    return warns, recs
