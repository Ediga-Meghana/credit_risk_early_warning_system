"""Risk assistant with a transparent built-in fallback and optional Anthropic API."""
import json
from .core import settings

KB = {
    "xgboost": "XGBoost is a gradient-boosted decision-tree model. It builds trees sequentially so later trees correct earlier errors. In this platform, XGBoost is the active risk model.",
    "smote": "SMOTE means Synthetic Minority Over-sampling Technique. It creates synthetic examples of the minority class in the training data. It helps the model learn from rare bankruptcy examples, but can make raw model probabilities poorly calibrated to real-world bankruptcy rates.",
    "shap": "SHAP explains a prediction by estimating each feature's contribution relative to a baseline. Positive SHAP values push the prediction toward higher risk; negative values push it toward lower risk. SHAP explains model behaviour, not causation.",
    "liquidity": "Liquidity describes a company's ability to meet short-term obligations. Common indicators compare current or liquid assets with current liabilities. A ratio is only meaningful when its definition and reporting period are consistent.",
    "leverage": "Leverage describes how much a company relies on debt relative to assets or equity. High leverage can increase financial risk, but interpretation depends on the industry, cash flows, and reporting period.",
    "bankruptcy": "The model estimates a bankruptcy-risk score from financial ratios. It is a screening aid, not a guarantee that a company will or will not fail. Review source data, uncertainty, and the SHAP explanation before acting.",
    "risk score": "The risk score is the model's predicted probability for the bankruptcy class. The low/moderate/high/critical label is assigned using the platform's configured thresholds. Because the model was trained with class balancing, its probability should not be treated as a calibrated real-world default probability.",
    "yahoo": "Yahoo Finance provides public-company financial statements when available. Statement labels and coverage vary by company, and the platform may not be able to derive all 20 model features. Missing features are imputed by the model pipeline, so Yahoo-based results are exploratory only.",
}


def _safe_num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _fallback(msg, ctx, meta):
    m = msg.lower().strip()
    if ctx:
        shap_values = ctx.get("shap") or []
        positive = sorted((e for e in shap_values if _safe_num(e.get("shap")) > 0), key=lambda e: _safe_num(e.get("shap")), reverse=True)[:3]
        negative = sorted((e for e in shap_values if _safe_num(e.get("shap")) < 0), key=lambda e: _safe_num(e.get("shap")))[:3]
        asks_factors = any(k in m for k in ("why", "top", "factor", "important", "driver", "explain", "latest", "risk", "high", "low", "score", "chart"))
        if asks_factors:
            raised = "; ".join(f"{e.get('label', e.get('feature', 'Feature'))} (SHAP {_safe_num(e.get('shap')):+.3f})" for e in positive) or "no positive SHAP drivers were supplied"
            protective = "; ".join(f"{e.get('label', e.get('feature', 'Feature'))} (SHAP {_safe_num(e.get('shap')):+.3f})" for e in negative) or "no negative SHAP drivers were supplied"
            return (f"For {ctx.get('company_name', 'the selected company')}, the model score is "
                    f"{_safe_num(ctx.get('probability')) * 100:.1f}% and the configured risk level is "
                    f"{ctx.get('risk_level', 'not available')}. Factors pushing the prediction upward: {raised}. "
                    f"Factors pushing it downward: {protective}. These are model associations, not proof of causation.")
        if any(k in m for k in ("recommend", "review", "should", "next step", "improve")):
            recs = ctx.get("recommendations") or []
            if recs:
                return "Suggested review areas from this assessment: " + "; ".join(
                    f"{r.get('title', 'Review area')}: {r.get('reason', 'Review the underlying financial statement')}" for r in recs[:5]
                ) + ". Validate each item against the original financial statements."
            return "No recommendations were attached to this assessment. Review the financial statements, missing-data warnings, and top SHAP contributors before drawing conclusions."
        if "what does" in m or "mean" in m:
            return (f"The score of {_safe_num(ctx.get('probability')) * 100:.1f}% is the model's estimated bankruptcy probability, "
                    f"labelled {ctx.get('risk_level', 'not available')} under the current configured thresholds. It is not a calibrated lending probability.")
    for key, value in KB.items():
        if key in m or (key == "risk score" and "score" in m):
            return value
    if any(k in m for k in ("company", "ticker", "stock", "financial statement")):
        return KB["yahoo"]
    if any(k in m for k in ("help", "can you", "what can", "how do i", "how can")):
        return "I can help explain risk scores, SHAP factors, liquidity, leverage, XGBoost, SMOTE, Yahoo Finance data coverage, and the limitations of this screening model. Try asking one specific question, such as 'Explain the top risk factors in my latest assessment.'"
    return ("I can answer general questions about this platform's risk model and financial indicators. "
            "For a company-specific explanation, ask about the latest assessment or open an assessment result. "
            "For broader conversational answers, configure an Anthropic API key in the backend .env file; otherwise this built-in assistant uses a limited set of verified explanations.")


def answer_with_mode(msg, ctx, meta):
    """Return reply plus transparent indication of whether a live LLM answered."""
    provider = (settings.AI_PROVIDER or "").strip().lower()
    api_key = (settings.AI_API_KEY or "").strip()
    if provider == "anthropic" and api_key:
        try:
            import httpx
            system_prompt = (
                "You are the RiskIntel credit-risk explainability assistant. Answer in clear, friendly language. "
                "Use provided assessment context and general finance/ML knowledge. Never invent company figures, "
                "never imply SHAP proves causation, and state when information is missing. This tool is decision support only.\n"
                "Assessment context JSON: " + json.dumps(ctx, default=str)[:7000] if ctx else
                "You are the RiskIntel credit-risk explainability assistant. Answer in clear, friendly language. "
                "Use general finance/ML knowledge; never invent project-specific results. This tool is decision support only.\nNo assessment context is available."
            )
            model = (settings.AI_MODEL or "").strip() or "claude-haiku-4-5-20251001"
            response = httpx.post(
                "https://api.anthropic.com/v1/messages",
                timeout=35,
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": model, "max_tokens": 800, "system": system_prompt,
                      "messages": [{"role": "user", "content": msg}]},
            )
            response.raise_for_status()
            data = response.json()
            text = "\n".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text").strip()
            if not text:
                raise ValueError("The AI provider returned an empty answer.")
            return {"reply": text, "mode": "ai", "notice": "AI-generated answer. Verify important financial decisions."}
        except Exception:
            return {"reply": _fallback(msg, ctx, meta), "mode": "fallback",
                    "notice": "The AI provider could not answer this request. Showing the built-in answer instead; check AI_API_KEY, AI_MODEL, API access and billing in backend/.env."}
    return {"reply": _fallback(msg, ctx, meta), "mode": "fallback",
            "notice": "Built-in assistant mode is active. For full conversational AI, configure AI_PROVIDER, AI_API_KEY and AI_MODEL in backend/.env."}


def answer(msg, ctx, meta):
    """Backward-compatible string-only interface."""
    return answer_with_mode(msg, ctx, meta)["reply"]
