"""Train & evaluate models on the Polish bankruptcy dataset. Run: python -m ml.train"""
import json, time, joblib, numpy as np, pandas as pd, pathlib, sys
from scipy.io import arff
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
    confusion_matrix, roc_curve, precision_recall_curve, average_precision_score)
from imblearn.over_sampling import SMOTE
from xgboost import XGBClassifier
import shap
ROOT = pathlib.Path(__file__).resolve().parent.parent
ART = ROOT/"ml"/"artifacts"; ART.mkdir(exist_ok=True)
N_FEATURES = 20; SEED = 42

def load():
    frames = []
    for i in range(1, 6):
        d, _ = arff.loadarff(ROOT/"data"/f"{i}year.arff")
        df = pd.DataFrame(d); df["class"] = df["class"].apply(lambda v: int(v.decode() if isinstance(v, bytes) else v))
        df["horizon"] = i; frames.append(df)
    return pd.concat(frames, ignore_index=True)

def curve_pts(x, y, n=60):
    idx = np.linspace(0, len(x)-1, min(n, len(x))).astype(int)
    return [[float(x[i]), float(y[i])] for i in idx]

def main():
    df = load(); cols = [f"Attr{i}" for i in range(1, 65)]
    X = df[cols].replace([np.inf, -np.inf], np.nan); y = df["class"].values
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, stratify=y, random_state=SEED)
    lo, hi = Xtr.quantile(0.01), Xtr.quantile(0.99)           # winsorise bounds (train only)
    med = Xtr.clip(lo, hi, axis=1).median()                   # impute values (train only)
    prep = lambda A: A.clip(lo, hi, axis=1).fillna(med)
    Xtr_p, Xte_p = prep(Xtr), prep(Xte)
    # feature selection by XGB gain on training data only
    sel = XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.1, random_state=SEED, n_jobs=-1,
                        scale_pos_weight=(ytr==0).sum()/(ytr==1).sum()).fit(Xtr_p, ytr)
    imp = pd.Series(sel.get_booster().get_score(importance_type="gain")).reindex(cols).fillna(0)
    feats = list(imp.sort_values(ascending=False).index[:N_FEATURES])
    Xtr_f, Xte_f = Xtr_p[feats], Xte_p[feats]
    # SMOTE only on training split (no leakage into the test set)
    Xs, ys = SMOTE(random_state=SEED).fit_resample(Xtr_f, ytr)
    sc = StandardScaler().fit(Xs)
    models = {
        "XGBoost": XGBClassifier(n_estimators=400, max_depth=5, learning_rate=0.05, subsample=0.9, colsample_bytree=0.9,
                                 random_state=SEED, n_jobs=-1, eval_metric="logloss"),
        "Random Forest": RandomForestClassifier(n_estimators=300, n_jobs=-1, random_state=SEED),
        "SVM (RBF)": SVC(kernel="rbf", probability=True, C=3, random_state=SEED),
    }
    results, detail = {}, {}
    for n, m in models.items():
        t = time.time()
        if n == "SVM (RBF)":
            ix = np.random.RandomState(SEED).choice(len(Xs), min(8000, len(Xs)), replace=False)
            m.fit(sc.transform(Xs.iloc[ix]), ys[ix]); p = m.predict_proba(sc.transform(Xte_f))[:, 1]
        else: m.fit(Xs, ys); p = m.predict_proba(Xte_f)[:, 1]
        pred = (p >= 0.5).astype(int)
        results[n] = dict(accuracy=accuracy_score(yte, pred), precision=precision_score(yte, pred, zero_division=0),
            recall=recall_score(yte, pred), f1=f1_score(yte, pred), roc_auc=roc_auc_score(yte, p),
            pr_auc=average_precision_score(yte, p), train_seconds=round(time.time()-t, 1))
        detail[n] = p; print(n, {k: round(v, 3) for k, v in results[n].items()}, flush=True)
    xgb = models["XGBoost"]; p = detail["XGBoost"]
    # operating thresholds: 0.5 default; F1-optimal reported
    pr, rc, th = precision_recall_curve(yte, p); f1s = 2*pr*rc/(pr+rc+1e-12)
    best_th = float(th[np.argmax(f1s[:-1])])
    fpr, tpr, _ = roc_curve(yte, p)
    pred = (p >= 0.5).astype(int); tn, fp, fn, tp = confusion_matrix(yte, pred).ravel()
    expl = shap.TreeExplainer(xgb)
    sv = expl.shap_values(Xte_f.sample(1000, random_state=SEED))
    gshap = pd.Series(np.abs(sv).mean(0), index=feats).sort_values(ascending=False)
    prob_all = xgb.predict_proba(Xte_f)[:, 1]
    meta = dict(model_name="XGBoost", version="v1.0", trained_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        dataset="Polish Companies Bankruptcy (UCI), 5 forecasting horizons pooled",
        n_rows_total=int(len(df)), n_train=int(len(Xtr)), n_test=int(len(Xte)), n_train_after_smote=int(len(Xs)),
        bankrupt_rate=float(y.mean()), n_features_all=64, n_features_selected=len(feats), features=feats,
        medians={f: float(med[f]) for f in cols}, clip_lo={f: float(lo[f]) for f in cols}, clip_hi={f: float(hi[f]) for f in cols},
        metrics_default_threshold=results, best_f1_threshold=best_th,
        confusion_matrix=dict(tn=int(tn), fp=int(fp), fn=int(fn), tp=int(tp)),
        roc_curve=curve_pts(fpr, tpr), pr_curve=curve_pts(rc[::-1], pr[::-1]),
        shap_importance=[{"feature": k, "mean_abs_shap": float(v)} for k, v in gshap.items()],
        base_value=float(np.ravel(expl.expected_value)[0]),
        notes="SVM(RBF) is used as a stand-in for LSSVM; CNN not implemented. SMOTE applied to training split only.")
    joblib.dump(dict(model=xgb, feats=feats), ART/"xgb_v1.joblib")
    (ART/"model_meta.json").write_text(json.dumps(meta, indent=1))
    print("saved; selected:", feats[:8])
if __name__ == "__main__": main()
