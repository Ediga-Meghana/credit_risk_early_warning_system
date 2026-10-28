"""Yahoo Finance lookup and transparent mapping to the existing bankruptcy model.

Yahoo Finance data is unofficial and can be incomplete. This module deliberately
leaves ratios unknown when source statements cannot support a defensible formula;
the existing model then imputes its training median and the API reports coverage.
"""
from __future__ import annotations
from typing import Any
import math

MODEL_FEATURES = [
    "Attr26", "Attr27", "Attr24", "Attr34", "Attr6", "Attr35", "Attr22",
    "Attr38", "Attr42", "Attr46", "Attr10", "Attr16", "Attr5", "Attr13",
    "Attr25", "Attr39", "Attr41", "Attr61", "Attr63", "Attr20",
]


def _number(value: Any) -> float | None:
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def _row_value(frame: Any, names: tuple[str, ...], column: int = 0) -> float | None:
    """Find a statement row by case-insensitive exact/substring aliases."""
    if frame is None or getattr(frame, "empty", True):
        return None
    try:
        for alias in names:
            for idx in frame.index:
                label = str(idx).casefold()
                if label == alias.casefold() or alias.casefold() in label:
                    if column < len(frame.columns):
                        return _number(frame.loc[idx].iloc[column])
    except Exception:
        return None
    return None


def _get_statement(ticker: Any, attr: str):
    try:
        return getattr(ticker, attr)
    except Exception:
        return None


def search_companies(query: str, limit: int = 8) -> list[dict[str, Any]]:
    if len(query.strip()) < 2:
        return []
    try:
        import yfinance as yf
        result = yf.Search(query.strip(), max_results=limit, news_count=0)
        quotes = getattr(result, "quotes", []) or []
        cleaned = []
        for q in quotes:
            symbol = q.get("symbol")
            if not symbol:
                continue
            cleaned.append({
                "symbol": symbol,
                "name": q.get("longname") or q.get("shortname") or symbol,
                "exchange": q.get("exchDisp") or q.get("exchange") or "",
                "type": q.get("quoteType") or "",
            })
        return cleaned
    except Exception as exc:
        raise RuntimeError("Yahoo Finance search is temporarily unavailable. Check your internet connection and try again.") from exc




def company_market_data(ticker: Any, symbol: str) -> dict[str, Any]:
    """Return recent daily market observations from Yahoo Finance.

    These are monitoring indicators, not inputs to the bankruptcy model, which
    was trained on annual financial ratios.
    """
    import pandas as pd
    empty = {"as_of": None, "close": None, "previous_close": None,
             "daily_change_pct": None, "volume": None, "five_day_change_pct": None,
             "twenty_day_volatility_pct": None}
    try:
        history = ticker.history(period="3mo", interval="1d", auto_adjust=False)
        if history is None or history.empty or "Close" not in history:
            return empty
        close = history["Close"]
        volume = history["Volume"] if "Volume" in history else None
        if getattr(close, "ndim", 1) > 1: close = close.iloc[:, 0]
        close = pd.to_numeric(close, errors="coerce").dropna()
        if close.empty: return empty
        last_date = close.index[-1]
        latest = float(close.iloc[-1])
        previous = float(close.iloc[-2]) if len(close) >= 2 else None
        daily = ((latest / previous) - 1) * 100 if previous not in (None, 0) else None
        five_day = (latest / float(close.iloc[-6]) - 1) * 100 if len(close) >= 6 and float(close.iloc[-6]) != 0 else None
        returns = close.pct_change().dropna().tail(20)
        volatility = float(returns.std(ddof=1) * (252 ** 0.5) * 100) if len(returns) >= 2 else None
        latest_volume = None
        if volume is not None:
            try:
                if getattr(volume, "ndim", 1) > 1: volume = volume.iloc[:, 0]
                v = pd.to_numeric(volume, errors="coerce").dropna()
                if not v.empty: latest_volume = int(v.iloc[-1])
            except Exception: pass
        as_of = last_date.date().isoformat() if hasattr(last_date, "date") else str(last_date)[:10]
        return {"as_of": as_of, "close": round(latest, 4),
                "previous_close": round(previous, 4) if previous is not None else None,
                "daily_change_pct": round(daily, 2) if daily is not None else None,
                "volume": latest_volume,
                "five_day_change_pct": round(five_day, 2) if five_day is not None else None,
                "twenty_day_volatility_pct": round(volatility, 2) if volatility is not None else None}
    except Exception:
        return empty


def market_signal_level(market: dict[str, Any] | None) -> str:
    """Transparent market-stress rules; not a calibrated default probability."""
    market = market or {}
    daily, five_day = market.get("daily_change_pct"), market.get("five_day_change_pct")
    if (daily is not None and daily <= -10) or (five_day is not None and five_day <= -20): return "critical"
    if (daily is not None and daily <= -5) or (five_day is not None and five_day <= -10): return "high"
    if (daily is not None and daily <= -3) or (five_day is not None and five_day <= -5): return "moderate"
    return "low"


def company_financials(symbol: str) -> dict[str, Any]:
    symbol = symbol.strip().upper()
    if not symbol or len(symbol) > 30 or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-^=" for c in symbol):
        raise ValueError("Enter a valid Yahoo Finance ticker symbol.")
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        market_data = company_market_data(ticker, symbol)
        bs = _get_statement(ticker, "balance_sheet")
        inc = _get_statement(ticker, "financials")
        cf = _get_statement(ticker, "cashflow")
        # Prefer current/most recent annual statements. Yahoo may return fewer years.
        assets = _row_value(bs, ("Total Assets",))
        liabilities = _row_value(bs, ("Total Liabilities Net Minority Interest", "Total Liabilities"))
        equity = _row_value(bs, ("Stockholders Equity", "Total Equity Gross Minority Interest"))
        current_assets = _row_value(bs, ("Current Assets",))
        current_liabilities = _row_value(bs, ("Current Liabilities",))
        inventory = _row_value(bs, ("Inventory",))
        cash = _row_value(bs, ("Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents", "Cash Financial"))
        receivables = _row_value(bs, ("Accounts Receivable", "Receivables"))
        retained = _row_value(bs, ("Retained Earnings",))
        long_debt = _row_value(bs, ("Long Term Debt", "Long Term Debt And Capital Lease Obligation"))
        revenue = _row_value(inc, ("Total Revenue", "Operating Revenue"))
        gross = _row_value(inc, ("Gross Profit",))
        operating_income = _row_value(inc, ("Operating Income",))
        net_income = _row_value(inc, ("Net Income", "Net Income Common Stockholders"))
        operating_expenses = _row_value(inc, ("Operating Expense", "Operating Expenses"))
        interest_expense = _row_value(inc, ("Interest Expense Non Operating", "Interest Expense"))
        depreciation = _row_value(cf, ("Depreciation And Amortization", "Depreciation Amortization Depletion", "Depreciation"))
        if depreciation is None:
            depreciation = _row_value(inc, ("Reconciled Depreciation",))
        # Gross profit across up to the latest three annual columns.
        gross_3yr = None
        try:
            if inc is not None and not inc.empty:
                matches = [idx for idx in inc.index if "gross profit" == str(idx).casefold()]
                if matches:
                    values = [_number(v) for v in inc.loc[matches[0]].iloc[:3].tolist()]
                    valid = [v for v in values if v is not None]
                    if len(valid) >= 2:
                        gross_3yr = sum(valid)
        except Exception:
            pass
        # Some rows are not disclosed consistently. Do not fabricate share capital,
        # profit-on-sales, or constant capital from unrelated line items.
        def div(n: float | None, d: float | None) -> float | None:
            return n / d if n is not None and d not in (None, 0) else None
        features: dict[str, float | None] = {k: None for k in MODEL_FEATURES}
        if net_income is not None and depreciation is not None:
            features["Attr26"] = div(net_income + depreciation, liabilities)
        if operating_income is not None:
            features["Attr27"] = div(operating_income, abs(interest_expense) if interest_expense is not None else None)
            features["Attr22"] = div(operating_income, assets)
            features["Attr42"] = div(operating_income, revenue)
        if gross_3yr is not None:
            features["Attr24"] = div(gross_3yr, assets)
        if operating_expenses is not None:
            features["Attr34"] = div(operating_expenses, liabilities)
        if retained is not None:
            features["Attr6"] = div(retained, assets)
        if current_assets is not None and inventory is not None:
            features["Attr46"] = div(current_assets - inventory, current_liabilities)
        features["Attr10"] = div(equity, assets)
        if gross is not None and depreciation is not None:
            features["Attr16"] = div(gross + depreciation, liabilities)
            features["Attr13"] = div(gross + depreciation, revenue)
        if cash is not None and receivables is not None and current_liabilities is not None and operating_expenses is not None and depreciation is not None:
            features["Attr5"] = div(cash + receivables - current_liabilities, operating_expenses - depreciation)
            if features["Attr5"] is not None:
                features["Attr5"] *= 365
        if liabilities is not None and operating_income is not None and depreciation is not None:
            features["Attr41"] = div(liabilities, (operating_income + depreciation) * (12 / 365))
        if revenue is not None and receivables is not None:
            features["Attr61"] = div(revenue, receivables)
        if revenue is not None and current_liabilities is not None:
            features["Attr63"] = div(revenue, current_liabilities)
        if revenue is not None and inventory is not None:
            features["Attr20"] = div(inventory * 365, revenue)
        available = [k for k, v in features.items() if v is not None]
        missing = [k for k, v in features.items() if v is None]
        display_financials = {
            "currency": info.get("financialCurrency") or info.get("currency") or "Reported currency",
            "period": str(getattr(inc, "columns", [""])[0])[:10] if inc is not None and len(getattr(inc, "columns", [])) else "Latest available annual period",
            "revenue": revenue, "gross_profit": gross, "operating_income": operating_income,
            "net_income": net_income, "total_assets": assets, "total_liabilities": liabilities,
            "equity": equity, "cash": cash, "current_assets": current_assets,
            "current_liabilities": current_liabilities, "inventory": inventory,
            "receivables": receivables, "long_term_debt": long_debt,
        }
        return {
            "symbol": symbol,
            "name": info.get("longName") or info.get("shortName") or symbol,
            "exchange": info.get("exchange") or info.get("fullExchangeName") or "",
            "sector": info.get("sector") or info.get("industry") or "Public company",
            "country": info.get("country") or "",
            "website": info.get("website") or "",
            "financials": display_financials,
            "model_values": features,
            "feature_coverage": len(available),
            "feature_total": len(MODEL_FEATURES),
            "available_features": available,
            "missing_features": missing,
            "market_data": market_data,
            "market_signal_level": market_signal_level(market_data),
            "source": "Yahoo Finance",
            "limitations": [
                "Yahoo Finance statement labels and reporting conventions can differ by company.",
                "The risk model was trained on Polish company bankruptcy data, not a representative sample of Yahoo-listed companies.",
                "Undisclosed ratios are imputed using training-set medians; this is an exploratory screening result, not a calibrated credit decision.",
            ],
        }
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError("Could not retrieve this company's financial statements from Yahoo Finance. Try another ticker or try again later.") from exc
