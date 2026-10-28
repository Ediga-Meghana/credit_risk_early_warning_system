import io, csv, uuid, json, subprocess, sys, datetime as dt, secrets, hashlib, hmac, smtplib, re
from threading import Thread, Event
from typing import Optional
from email.message import EmailMessage
from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from .core import settings, engine, SessionLocal, Base, now, ART
from .models import *
from . import ml_service as ml
from .assistant import answer_with_mode
from . import yahoo_finance as yahoo

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
app = FastAPI(title="Explainable AI Credit Risk API")
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS.split(","), allow_methods=["*"], allow_headers=["*"], allow_credentials=True)
DEFAULT_TH = {"moderate": 0.25, "high": 0.50, "critical": 0.75}

def db():
    s = SessionLocal()
    try: yield s
    finally: s.close()
def audit(s, user, action, detail="", req=None):
    s.add(AuditLog(user_id=user.id if user else None, email=user.email if user else None, action=action, detail=detail,
                   ip=req.client.host if req and req.client else None)); s.commit()
def user_dep(token: str = Depends(oauth), s: Session = Depends(db)):
    try: uid = int(jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])["sub"])
    except (JWTError, KeyError, ValueError): raise HTTPException(401, "Session expired or invalid. Please sign in again.")
    u = s.get(User, uid)
    if not u or not u.is_active: raise HTTPException(401, "Account unavailable.")
    return u
def admin_dep(u: User = Depends(user_dep)):
    if u.role != "admin": raise HTTPException(403, "Access denied. Administrator privileges required.")
    return u
def thresholds(s):
    r = s.get(Setting, "thresholds"); return r.value if r else DEFAULT_TH
def level(p, th):
    return "critical" if p >= th["critical"] else "high" if p >= th["high"] else "moderate" if p >= th["moderate"] else "low"

@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine); s = SessionLocal()
    if not s.query(User).filter_by(email=settings.ADMIN_EMAIL).first():
        s.add(User(email=settings.ADMIN_EMAIL, full_name="System Administrator", role="admin", password_hash=pwd.hash(settings.ADMIN_PASSWORD)))
    m = ml.load()["meta"]
    if not s.query(ModelRecord).first():
        mm = m["metrics_default_threshold"]["XGBoost"]
        s.add(ModelRecord(name=m["model_name"], version=m["version"], status="active", is_active=True, metrics=mm,
            trained_at=dt.datetime.fromisoformat(m["trained_at"]), n_features=m["n_features_selected"], dataset_size=m["n_rows_total"]))
    s.commit(); s.close()
    start_monitor_scheduler()
@app.exception_handler(Exception)
async def err(request, exc):
    if isinstance(exc, HTTPException): return JSONResponse({"detail": exc.detail}, exc.status_code)
    return JSONResponse({"detail": "An unexpected server error occurred."}, 500)

# ---------- auth ----------
class Login(BaseModel):
    email: str
    password: str

class SignupStart(BaseModel):
    email: str
    full_name: str
    password: str

class SignupVerify(BaseModel):
    email: str
    otp: str


def clean_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) > 190 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(422, "Enter a valid email address.")
    return email


def otp_digest(email: str, otp: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), f"signup:{email}:{otp}".encode(), hashlib.sha256).hexdigest()


def send_signup_otp(email: str, full_name: str, otp: str) -> None:
    if not all([settings.SMTP_HOST, settings.SMTP_USERNAME, settings.SMTP_PASSWORD, settings.SMTP_FROM_EMAIL]):
        raise HTTPException(503, "Email OTP is not configured yet. Set SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD and SMTP_FROM_EMAIL in backend/.env, then restart the backend.")
    msg = EmailMessage()
    msg["Subject"] = "Verify your Risk Platform account"
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = email
    msg.set_content(
        f"Hello {full_name},\n\nYour Risk Platform verification code is: {otp}\n\n"
        f"This code expires in {settings.SIGNUP_OTP_TTL_MINUTES} minutes. If you did not request an account, ignore this email.\n"
    )
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as exc:
        # Do not expose SMTP credentials or provider details to the browser.
        raise HTTPException(502, "We couldn't send the verification email. Check the SMTP settings in backend/.env.") from exc


@app.post("/api/auth/signup/request-otp")
def signup_request_otp(b: SignupStart, s: Session = Depends(db)):
    email = clean_email(b.email)
    full_name = b.full_name.strip()
    if not full_name or len(full_name) > 120:
        raise HTTPException(422, "Enter your name (up to 120 characters).")
    if len(b.password) < 8 or len(b.password) > 128:
        raise HTTPException(422, "Password must be between 8 and 128 characters.")
    if s.query(User).filter(func.lower(User.email) == email).first():
        raise HTTPException(409, "An account with this email already exists. Please sign in.")
    pending = s.get(SignupOTP, email)
    current = now()
    if pending and (current - pending.created_at).total_seconds() < settings.SIGNUP_OTP_RESEND_SECONDS:
        wait = max(1, settings.SIGNUP_OTP_RESEND_SECONDS - int((current - pending.created_at).total_seconds()))
        raise HTTPException(429, f"Please wait {wait} seconds before requesting another code.")
    code = f"{secrets.randbelow(1_000_000):06d}"
    if not pending:
        pending = SignupOTP(email=email, full_name=full_name, password_hash=pwd.hash(b.password), otp_hash=otp_digest(email, code),
                            expires_at=current + dt.timedelta(minutes=settings.SIGNUP_OTP_TTL_MINUTES), created_at=current, attempts=0)
        s.add(pending)
    else:
        pending.full_name = full_name
        pending.password_hash = pwd.hash(b.password)
        pending.otp_hash = otp_digest(email, code)
        pending.expires_at = current + dt.timedelta(minutes=settings.SIGNUP_OTP_TTL_MINUTES)
        pending.created_at = current
        pending.attempts = 0
    s.commit()
    try:
        send_signup_otp(email, full_name, code)
    except HTTPException:
        s.delete(pending); s.commit()
        raise
    return {"ok": True, "message": "Verification code sent. Check your email inbox and spam folder.", "expires_in_seconds": settings.SIGNUP_OTP_TTL_MINUTES * 60}


@app.post("/api/auth/signup/verify-otp", status_code=201)
def signup_verify_otp(b: SignupVerify, req: Request, s: Session = Depends(db)):
    email = clean_email(b.email)
    if not re.fullmatch(r"\d{6}", b.otp.strip()):
        raise HTTPException(422, "Enter the six-digit verification code.")
    if s.query(User).filter(func.lower(User.email) == email).first():
        pending = s.get(SignupOTP, email)
        if pending:
            s.delete(pending); s.commit()
        raise HTTPException(409, "An account with this email already exists. Please sign in.")
    pending = s.get(SignupOTP, email)
    if not pending:
        raise HTTPException(400, "No signup code found. Request a new verification code.")
    if pending.expires_at < now():
        s.delete(pending); s.commit()
        raise HTTPException(400, "Your verification code expired. Request a new one.")
    if pending.attempts >= 5:
        s.delete(pending); s.commit()
        raise HTTPException(429, "Too many incorrect codes. Request a new verification code.")
    if not hmac.compare_digest(pending.otp_hash, otp_digest(email, b.otp.strip())):
        pending.attempts += 1; s.commit()
        raise HTTPException(400, f"Incorrect verification code. {max(0, 5-pending.attempts)} attempts remaining.")
    u = User(email=email, full_name=pending.full_name, role="analyst", password_hash=pending.password_hash, is_active=True)
    s.add(u); s.delete(pending); s.commit(); s.refresh(u)
    audit(s, u, "signup_verified", "Email OTP verified; analyst account created", req)
    return {"ok": True, "message": "Email verified and account created. Sign in using your email and password."}


@app.post("/api/auth/login")
def login(b: Login, req: Request, s: Session = Depends(db)):
    email = clean_email(b.email)
    u = s.query(User).filter(func.lower(User.email) == email).first()
    if not u or not pwd.verify(b.password, u.password_hash) or not u.is_active:
        audit(s, None, "login_failed", email, req); raise HTTPException(401, "Invalid email or password.")
    u.last_login = now(); s.commit(); audit(s, u, "login", "", req)
    tok = jwt.encode({"sub": str(u.id), "exp": now() + dt.timedelta(minutes=settings.ACCESS_TOKEN_MINUTES)}, settings.SECRET_KEY, "HS256")
    return {"access_token": tok, "user": uo(u)}
def uo(u): return dict(id=u.id, email=u.email, full_name=u.full_name, role=u.role, is_active=u.is_active, last_login=u.last_login, created_at=u.created_at)
@app.get("/api/auth/me")
def me(u: User = Depends(user_dep)): return uo(u)
class PwChange(BaseModel): current_password: str; new_password: str
@app.post("/api/auth/change-password")
def chpw(b: PwChange, u: User = Depends(user_dep), s: Session = Depends(db)):
    if not pwd.verify(b.current_password, u.password_hash): raise HTTPException(400, "Current password is incorrect.")
    if len(b.new_password) < 8: raise HTTPException(422, "New password must be at least 8 characters.")
    u.password_hash = pwd.hash(b.new_password); s.commit(); audit(s, u, "password_change"); return {"ok": True}

# ---------- users (admin) ----------
class UserIn(BaseModel): email: str; full_name: str; password: str; role: str = "analyst"
@app.get("/api/admin/users")
def users(a=Depends(admin_dep), s: Session = Depends(db)): return [uo(u) for u in s.query(User).order_by(User.id)]
@app.post("/api/admin/users", status_code=201)
def mkuser(b: UserIn, req: Request, a=Depends(admin_dep), s: Session = Depends(db)):
    if b.role not in ("admin", "analyst", "viewer"): raise HTTPException(422, "Invalid role.")
    if len(b.password) < 8: raise HTTPException(422, "Password must be at least 8 characters.")
    if s.query(User).filter(func.lower(User.email) == b.email.lower()).first(): raise HTTPException(409, "A user with this email already exists.")
    u = User(email=b.email, full_name=b.full_name, role=b.role, password_hash=pwd.hash(b.password)); s.add(u); s.commit()
    audit(s, a, "user_create", b.email, req); return uo(u)
class UserPatch(BaseModel): role: Optional[str] = None; is_active: Optional[bool] = None
@app.put("/api/admin/users/{uid}")
def patch_user(uid: int, b: UserPatch, a=Depends(admin_dep), s: Session = Depends(db)):
    u = s.get(User, uid)
    if not u: raise HTTPException(404, "User not found.")
    if u.id == a.id and (b.is_active is False or (b.role and b.role != "admin")): raise HTTPException(400, "You cannot demote or deactivate your own account.")
    if b.role: u.role = b.role
    if b.is_active is not None: u.is_active = b.is_active
    s.commit(); audit(s, a, "user_update", f"{u.email} role={u.role} active={u.is_active}"); return uo(u)
@app.get("/api/admin/audit-logs")
def logs(page: int = 1, size: int = 25, a=Depends(admin_dep), s: Session = Depends(db)):
    q = s.query(AuditLog).order_by(AuditLog.id.desc()); t = q.count()
    return {"total": t, "items": [dict(id=l.id, email=l.email, action=l.action, detail=l.detail, ip=l.ip, created_at=l.created_at) for l in q.offset((page-1)*size).limit(size)]}
class Th(BaseModel): moderate: float; high: float; critical: float
@app.get("/api/settings/thresholds")
def get_th(u=Depends(user_dep), s: Session = Depends(db)): return thresholds(s)
@app.put("/api/admin/settings/thresholds")
def set_th(b: Th, a=Depends(admin_dep), s: Session = Depends(db)):
    if not (0 < b.moderate < b.high < b.critical < 1): raise HTTPException(422, "Thresholds must satisfy 0 < moderate < high < critical < 1.")
    v = b.dict(); r = s.get(Setting, "thresholds")
    if r: r.value = v
    else: s.add(Setting(key="thresholds", value=v))
    s.commit(); audit(s, a, "thresholds_update", json.dumps(v)); return v

# ---------- Yahoo Finance company lookup ----------
@app.get("/api/yahoo/search")
def yahoo_search(q: str = Query(..., min_length=2, max_length=100), u=Depends(user_dep)):
    try:
        return {"items": yahoo.search_companies(q)}
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))

@app.get("/api/yahoo/company/{symbol}")
def yahoo_company(symbol: str, u=Depends(user_dep)):
    try:
        return yahoo.company_financials(symbol)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))

@app.post("/api/yahoo/assess", status_code=201)
def yahoo_assess(b: dict, req: Request, u=Depends(user_dep), s: Session = Depends(db)):
    if u.role == "viewer": raise HTTPException(403, "Access denied.")
    symbol = str(b.get("symbol", "")).strip().upper()
    try:
        info = yahoo.company_financials(symbol)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    if info["feature_coverage"] < 5:
        raise HTTPException(422, "Yahoo Finance did not provide enough financial data for a useful screening. Try a larger publicly listed company with more complete statements.")
    company = s.query(Company).filter(Company.created_by == u.id, func.lower(Company.registration_no) == symbol.lower()).first()
    if not company:
        company = s.query(Company).filter(Company.created_by == u.id, func.lower(Company.name) == info["name"].lower()).first()
    if not company:
        company = Company(name=info["name"], registration_no=symbol, sector=info.get("sector"), country=info.get("country"), created_by=u.id)
        s.add(company); s.commit(); s.refresh(company)
    else:
        if not company.registration_no: company.registration_no = symbol
        if not company.sector: company.sector = info.get("sector")
        if not company.country: company.country = info.get("country")
        s.commit()
    a = run_one(s, u, company.id, info["model_values"])
    # Store source/coverage alongside saved inputs for auditability without altering model features.
    saved_inputs = dict(a.inputs or {})
    saved_inputs["_source"] = "Yahoo Finance"
    saved_inputs["_source_symbol"] = symbol
    saved_inputs["_feature_coverage"] = f"{info['feature_coverage']}/{info['feature_total']}"
    a.inputs = saved_inputs
    s.commit()
    audit(s, u, "yahoo_finance_assessment", f"symbol={symbol}; feature_coverage={info['feature_coverage']}/{info['feature_total']}; assessment_id={a.id}", req)
    result = ao(a, s)
    result["data_source"] = "Yahoo Finance"
    result["source_symbol"] = symbol
    result["feature_coverage"] = info["feature_coverage"]
    result["feature_total"] = info["feature_total"]
    result["missing_features"] = info["missing_features"]
    result["limitations"] = info["limitations"]
    # Loan decision support is advisory only; it is not an automatic approval/denial.
    result["loan_recommendation"] = loan_recommendation(result.get("risk_level"))
    return result

def loan_recommendation(risk_level):
    messages = {
        "low": ("Potentially suitable for further consideration", "Lower predicted credit risk. Complete normal affordability, identity, collateral and policy checks before lending."),
        "moderate": ("Review required", "Some risk indicators require closer review. Verify recent financial statements and repayment capacity."),
        "high": ("High caution", "The model predicts elevated credit risk. Escalate for detailed manual review before any lending decision."),
        "critical": ("Very high caution", "The model predicts very elevated credit risk. Do not approve automatically; perform enhanced review under the lender's policy."),
    }
    title, detail = messages.get(str(risk_level or "").lower(), ("Manual review required", "Risk category unavailable; review the underlying assessment."))
    return {"title": title, "detail": detail, "automatic_decision": False}

# Lightweight in-process daily checker. It runs while the web service process is awake.
_monitor_scheduler_started = False
_monitor_stop = Event()

def _run_scheduled_monitoring_pass():
    session = SessionLocal()
    try:
        items = session.query(MonitoredCompany).filter_by(active=True).all()
        for item in items:
            try:
                user = session.get(User, item.user_id)
                if user and user.is_active:
                    _check_monitored_item(session, item, user)
            except Exception:
                session.rollback()
    finally:
        session.close()

def _monitor_scheduler_loop():
    # Run once after startup, then every 24 hours while this process is awake.
    # Use an external persistent scheduler in deployments that sleep/restart.
    _run_scheduled_monitoring_pass()
    while not _monitor_stop.wait(24 * 60 * 60):
        _run_scheduled_monitoring_pass()

def start_monitor_scheduler():
    global _monitor_scheduler_started
    if not _monitor_scheduler_started:
        _monitor_scheduler_started = True
        Thread(target=_monitor_scheduler_loop, name="credit-risk-monitor", daemon=True).start()

# ---------- financial monitoring ----------
import time

def _snapshot_change(previous, current):
    changes = []
    for key, new_value in (current or {}).items():
        old_value = (previous or {}).get(key)
        if isinstance(old_value, (int, float)) and isinstance(new_value, (int, float)):
            if old_value != new_value:
                pct_change = None if old_value == 0 else round((new_value - old_value) / abs(old_value) * 100, 2)
                changes.append({"field": key, "previous": old_value, "current": new_value, "percent_change": pct_change})
        elif old_value != new_value and (old_value is not None or new_value is not None):
            changes.append({"field": key, "previous": old_value, "current": new_value, "percent_change": None})
    return changes

def _snapshot_financial_payload(info):
    """Store statement values plus market observations in the existing JSON column."""
    payload = dict(info.get("financials") or {})
    for key, value in (info.get("market_data") or {}).items(): payload[f"market_{key}"] = value
    payload["market_signal_level"] = info.get("market_signal_level") or "low"
    return payload

def _check_monitored_item(s, item, user):
    info = yahoo.company_financials(item.symbol)
    if info.get("feature_coverage", 0) < 5:
        raise ValueError("Not enough financial data to reassess this company.")
    previous = s.query(FinancialSnapshot).filter_by(monitored_company_id=item.id).order_by(FinancialSnapshot.id.desc()).first()
    snapshot_financials = _snapshot_financial_payload(info)
    prev_financials = previous.financials if previous else {}
    changes = _snapshot_change(prev_financials, snapshot_financials)
    if previous and not changes:
        return {"symbol": item.symbol, "company_name": info.get("name"), "status": "unchanged",
                "checked_at": now().isoformat(), "market_as_of": (info.get("market_data") or {}).get("as_of"),
                "changes": [], "risk_probability": previous.risk_probability, "risk_level": previous.risk_level,
                "market_signal_level": (previous.financials or {}).get("market_signal_level", "low")}

    # The existing XGBoost model was trained on annual financial ratios, not
    # stock-price history. Only changed fundamentals trigger a new model assessment.
    fundamental_changes = [c for c in changes if not str(c["field"]).startswith("market_") and c["field"] != "market_signal_level"]
    model_values = info.get("model_values") or {}
    model_inputs_changed = not previous or bool(_snapshot_change(previous.model_values or {}, model_values))
    fundamentals_changed = not previous or bool(fundamental_changes) or model_inputs_changed

    company = s.query(Company).filter(Company.created_by == user.id, func.lower(Company.registration_no) == item.symbol.lower()).first()
    if not company:
        company = Company(name=info.get("name") or item.symbol, registration_no=item.symbol,
                          sector=info.get("sector"), country=info.get("country"), created_by=user.id)
        s.add(company); s.flush()
    else:
        if info.get("sector") and not company.sector: company.sector = info.get("sector")
        if info.get("country") and not company.country: company.country = info.get("country")

    if fundamentals_changed:
        assessment = run_one(s, user, company.id, model_values)
        assessment.inputs = {**(assessment.inputs or {}), "_source": "Yahoo Finance",
            "_source_symbol": item.symbol,
            "_feature_coverage": f"{info['feature_coverage']}/{info['feature_total']}"}
        risk_probability, risk_level = float(assessment.probability), assessment.risk_level
    else:
        risk_probability = float(previous.risk_probability) if previous and previous.risk_probability is not None else None
        risk_level = previous.risk_level if previous else None

    item.company_name = info.get("name") or item.symbol
    snap = FinancialSnapshot(monitored_company_id=item.id,
        source_period=str((info.get("financials") or {}).get("period") or ""),
        financials=snapshot_financials, model_values=model_values,
        risk_probability=risk_probability, risk_level=risk_level, change_summary=changes)
    s.add(snap); s.flush()

    current_market_signal = info.get("market_signal_level") or "low"
    previous_market_signal = (previous.financials or {}).get("market_signal_level", "low") if previous else "low"
    severity = {"low": 0, "moderate": 1, "high": 2, "critical": 3}
    if severity.get(current_market_signal, 0) >= 2 and severity.get(current_market_signal, 0) > severity.get(previous_market_signal, 0):
        md = info.get("market_data") or {}
        s.add(Notification(user_id=user.id, kind="market_stress", title=f"Market stress alert: {item.symbol}",
            body=(f"{item.company_name}: market stress moved from {previous_market_signal} to {current_market_signal}. "
                  f"Daily change: {md.get('daily_change_pct')}%; five-day change: {md.get('five_day_change_pct')}%. "
                  "This is a market signal, not a calibrated credit-default probability.")))
    if previous and previous.risk_level and risk_level and risk_level != previous.risk_level:
        s.add(Notification(user_id=user.id, kind="risk_change", title=f"Credit risk changed: {item.symbol}",
            body=f"{item.company_name}: {previous.risk_level} → {risk_level}. Review the latest financial-statement changes."))
    s.commit()
    return {"symbol": item.symbol, "company_name": item.company_name, "status": "updated",
            "checked_at": snap.observed_at.isoformat(), "source_period": snap.source_period,
            "market_data": info.get("market_data") or {}, "market_signal_level": current_market_signal,
            "fundamentals_reassessed": fundamentals_changed, "risk_probability": snap.risk_probability,
            "risk_level": snap.risk_level, "changes": changes,
            "loan_recommendation": loan_recommendation(snap.risk_level)}

class MonitorIn(BaseModel):
    symbol: str

@app.post("/api/monitoring/watchlist", status_code=201)
def monitor_add(b: MonitorIn, u=Depends(user_dep), s: Session = Depends(db)):
    if u.role == "viewer": raise HTTPException(403, "Access denied.")
    symbol = b.symbol.strip().upper()
    if not re.fullmatch(r"[A-Z0-9.^=-]{1,30}", symbol): raise HTTPException(422, "Enter a valid Yahoo Finance ticker.")
    existing = s.query(MonitoredCompany).filter_by(user_id=u.id, symbol=symbol, active=True).first()
    if existing: return {"id": existing.id, "symbol": existing.symbol, "company_name": existing.company_name, "message": "Already monitored."}
    try: info = yahoo.company_financials(symbol)
    except ValueError as exc: raise HTTPException(422, str(exc))
    except RuntimeError as exc: raise HTTPException(503, str(exc))
    if info.get("feature_coverage", 0) < 5: raise HTTPException(422, "Not enough financial data to monitor this ticker.")
    item = MonitoredCompany(user_id=u.id, symbol=symbol, company_name=info.get("name"), active=True)
    s.add(item); s.commit(); s.refresh(item)
    # Save the initial dated baseline so future checks can compare against it.
    try:
        result = _check_monitored_item(s, item, u)
    except Exception as exc:
        s.delete(item); s.commit()
        raise HTTPException(503, "Could not create the initial monitoring snapshot. Try again later.") from exc
    return {"id": item.id, "symbol": item.symbol, "company_name": item.company_name, "message": "Monitoring started; initial snapshot saved.", "initial_check": result}

@app.get("/api/monitoring/watchlist")
def monitor_list(u=Depends(user_dep), s: Session=Depends(db)):
    items = s.query(MonitoredCompany).filter_by(user_id=u.id, active=True).order_by(MonitoredCompany.created_at.desc()).all()
    out = []
    for item in items:
        latest = s.query(FinancialSnapshot).filter_by(monitored_company_id=item.id).order_by(FinancialSnapshot.id.desc()).first()
        out.append({"id": item.id, "symbol": item.symbol, "company_name": item.company_name, "created_at": item.created_at.isoformat() if item.created_at else None,
            "latest": ({"observed_at": latest.observed_at.isoformat(), "source_period": latest.source_period, "risk_probability": latest.risk_probability,
                        "risk_level": latest.risk_level, "change_summary": latest.change_summary,
                        "market_data": {k[7:]: v for k, v in (latest.financials or {}).items() if k.startswith("market_") and k != "market_signal_level"},
                        "market_signal_level": (latest.financials or {}).get("market_signal_level", "low"),
                        "fundamentals": {k: v for k, v in (latest.financials or {}).items() if not k.startswith("market_") and k != "market_signal_level"}} if latest else None)})
    return {"items": out, "check_interval_hours": 24, "note": "Daily market data is checked automatically while the backend process is awake; financial statements update when published. Market stress is separate from fundamentals-based credit probability."}

@app.post("/api/monitoring/check")
def monitor_check(u=Depends(user_dep), s: Session=Depends(db)):
    if u.role == "viewer": raise HTTPException(403, "Access denied.")
    items = s.query(MonitoredCompany).filter_by(user_id=u.id, active=True).all()
    results = []
    for item in items:
        try: results.append(_check_monitored_item(s, item, u))
        except Exception as exc: results.append({"symbol": item.symbol, "status": "error", "message": str(exc)[:200]})
    return {"checked": len(results), "results": results}

@app.get("/api/monitoring/watchlist/{watch_id}/history")
def monitor_history(watch_id: int, u=Depends(user_dep), s: Session=Depends(db)):
    item = s.query(MonitoredCompany).filter_by(id=watch_id, user_id=u.id, active=True).first()
    if not item: raise HTTPException(404, "Monitored company not found.")
    snapshots = s.query(FinancialSnapshot).filter_by(monitored_company_id=item.id).order_by(FinancialSnapshot.observed_at.desc()).limit(100).all()
    return {"symbol": item.symbol, "items": [{"id": x.id, "observed_at": x.observed_at.isoformat(), "source_period": x.source_period,
        "financials": {k: v for k, v in (x.financials or {}).items() if not k.startswith("market_") and k != "market_signal_level"},
        "market_data": {k[7:]: v for k, v in (x.financials or {}).items() if k.startswith("market_") and k != "market_signal_level"},
        "market_signal_level": (x.financials or {}).get("market_signal_level", "low"),
        "risk_probability": x.risk_probability, "risk_level": x.risk_level, "changes": x.change_summary} for x in snapshots]}

# ---------- companies ----------
class CompanyIn(BaseModel): name: str; registration_no: Optional[str] = None; sector: Optional[str] = None; country: Optional[str] = None
def co(c, s=None, user_id=None):
    aq = s.query(Assessment).filter_by(company_id=c.id) if s else None
    if aq is not None and user_id is not None:
        aq = aq.filter(Assessment.analyst_id == user_id)
    n = aq.count() if aq is not None else None
    last = aq.order_by(Assessment.id.desc()).first() if aq is not None else None
    return dict(id=c.id, name=c.name, registration_no=c.registration_no, sector=c.sector, country=c.country, created_at=c.created_at,
                assessment_count=n, latest_probability=last.probability if last else None, latest_level=last.risk_level if last else None)
@app.get("/api/companies")
def companies(q: str = "", page: int = 1, size: int = 20, u=Depends(user_dep), s: Session = Depends(db)):
    qq = s.query(Company).filter(Company.created_by == u.id)
    if q: qq = qq.filter(Company.name.ilike(f"%{q}%"))
    t = qq.count(); return {"total": t, "items": [co(c, s, u.id) for c in qq.order_by(Company.name).offset((page-1)*size).limit(size)]}
@app.post("/api/companies", status_code=201)
def mkco(b: CompanyIn, u=Depends(user_dep), s: Session = Depends(db)):
    if u.role == "viewer": raise HTTPException(403, "Access denied.")
    if not b.name.strip(): raise HTTPException(422, "Company name is required.")
    if s.query(Company).filter(Company.created_by == u.id, func.lower(Company.name) == b.name.strip().lower()).first(): raise HTTPException(409, "A company with this name already exists in your workspace.")
    c = Company(**{**b.dict(), "name": b.name.strip()}, created_by=u.id); s.add(c); s.commit(); audit(s, u, "company_create", c.name); return co(c, s, u.id)
@app.get("/api/companies/{cid}")
def getco(cid: int, u=Depends(user_dep), s: Session = Depends(db)):
    c = s.query(Company).filter(Company.id == cid, Company.created_by == u.id).first()
    if not c: raise HTTPException(404, "Company not found in your workspace.")
    hist = s.query(Assessment).filter(Assessment.company_id == cid, Assessment.analyst_id == u.id).order_by(Assessment.created_at).all()
    latest = hist[-1] if hist else None
    return {**co(c, s, u.id), "history": [dict(id=a.id, created_at=a.created_at, probability=a.probability, risk_level=a.risk_level) for a in hist],
            "latest": ao(latest, s) if latest else None}
@app.delete("/api/companies/{cid}")
def delco(cid: int, a=Depends(admin_dep), s: Session = Depends(db)):
    c = s.query(Company).filter(Company.id == cid, Company.created_by == a.id).first()
    if not c: raise HTTPException(404, "Company not found in your workspace.")
    s.delete(c); s.commit(); audit(s, a, "company_delete", c.name); return {"ok": True}

# ---------- assessments ----------
def ao(a, s, full=True):
    d = dict(id=a.id, company_id=a.company_id, company_name=a.company.name, created_at=a.created_at, probability=a.probability,
             risk_level=a.risk_level, model_name=a.model_name, model_version=a.model_version, top_risk_factor=a.top_risk_factor,
             analyst=a.analyst.full_name if a.analyst else None)
    saved_inputs = a.inputs or {}
    if saved_inputs.get("_source"):
        d.update(data_source=saved_inputs.get("_source"), source_symbol=saved_inputs.get("_source_symbol"),
                 feature_coverage=saved_inputs.get("_feature_coverage"))
    d["loan_recommendation"] = loan_recommendation(a.risk_level)
    if full: d.update(inputs=a.inputs, shap=a.shap, warnings=a.warnings, recommendations=a.recommendations, base_value=a.base_value)
    return d
def run_one(s, user, company_id, inputs, batch_id=None):
    th = thresholds(s); X, p, sv, miss = ml.predict_many([inputs]); ex = ml.explain(X.iloc[0], sv[0]); lv = level(float(p[0]), th)
    w, r = ml.warnings_and_recs(ex, lv); top = next((e["label"] for e in ex if e["shap"] > 0), None); meta = ml.load()["meta"]
    a = Assessment(company_id=company_id, analyst_id=user.id, probability=float(p[0]), risk_level=lv, model_name=meta["model_name"],
        model_version=meta["version"], inputs={k: float(v) for k, v in X.iloc[0].items()}, shap=ex, warnings=w, recommendations=r,
        base_value=meta["base_value"], top_risk_factor=top, batch_id=batch_id)
    a.inputs["_imputed"] = miss
    s.add(a); s.flush()
    if lv in ("high", "critical"):
        s.add(Notification(user_id=user.id, kind="high_risk", title=f"{lv.title()} risk assessment", body=f"{a.company_id and s.get(Company, company_id).name}: probability {p[0]*100:.1f}%"))
    s.commit(); return a
class AssessIn(BaseModel): company_id: int; values: dict
@app.get("/api/model/features")
def feats(u=Depends(user_dep)): return ml.feature_catalog()
@app.post("/api/assessments", status_code=201)
def assess(b: AssessIn, req: Request, u=Depends(user_dep), s: Session = Depends(db)):
    if u.role == "viewer": raise HTTPException(403, "Access denied.")
    if not s.query(Company).filter(Company.id == b.company_id, Company.created_by == u.id).first(): raise HTTPException(404, "Company not found in your workspace.")
    try: vals = {k: (None if v in (None, "") else float(v)) for k, v in b.values.items()}
    except (TypeError, ValueError): raise HTTPException(422, "All financial values must be numeric.")
    if all(v is None for v in vals.values()): raise HTTPException(422, "Enter at least one financial indicator.")
    a = run_one(s, u, b.company_id, vals); audit(s, u, "assessment_create", f"id={a.id}", req); return ao(a, s)
@app.get("/api/assessments")
def history(q: str = "", risk_level: str = "", company_id: int = 0, date_from: str = "", date_to: str = "", sort: str = "created_at", order: str = "desc",
            page: int = 1, size: int = 15, u=Depends(user_dep), s: Session = Depends(db)):
    qq = s.query(Assessment).join(Company).filter(Assessment.analyst_id == u.id)
    if q: qq = qq.filter(Company.name.ilike(f"%{q}%"))
    if risk_level: qq = qq.filter(Assessment.risk_level == risk_level)
    if company_id: qq = qq.filter(Assessment.company_id == company_id)
    if date_from: qq = qq.filter(Assessment.created_at >= dt.datetime.fromisoformat(date_from))
    if date_to: qq = qq.filter(Assessment.created_at < dt.datetime.fromisoformat(date_to) + dt.timedelta(days=1))
    col = {"created_at": Assessment.created_at, "probability": Assessment.probability, "company": Company.name}.get(sort, Assessment.created_at)
    qq = qq.order_by(col.desc() if order == "desc" else col.asc()); t = qq.count()
    return {"total": t, "items": [ao(a, s, False) for a in qq.offset((page-1)*size).limit(size)]}
@app.get("/api/assessments/{aid}")
def get_a(aid: int, u=Depends(user_dep), s: Session = Depends(db)):
    a = s.query(Assessment).filter(Assessment.id == aid, Assessment.analyst_id == u.id).first()
    if not a: raise HTTPException(404, "Assessment not found in your workspace.")
    return ao(a, s)
@app.post("/api/assessments/batch")
async def batch(company_id: int = Query(...), file: UploadFile = File(...), u=Depends(user_dep), s: Session = Depends(db)):
    if u.role == "viewer": raise HTTPException(403, "Access denied.")
    if not s.query(Company).filter(Company.id == company_id, Company.created_by == u.id).first(): raise HTTPException(404, "Company not found in your workspace.")
    raw = (await file.read()).decode("utf-8-sig", errors="ignore")
    rows = list(csv.DictReader(io.StringIO(raw)))
    if not rows: raise HTTPException(422, "The CSV file contains no rows.")
    if len(rows) > 500: raise HTTPException(422, "Batch limit is 500 rows per upload.")
    keys = set(ml.load()["feats"])
    if not keys & set(rows[0].keys()): s.add(Notification(user_id=u.id, kind="batch_failed", title="Failed batch upload", body=file.filename)); s.commit(); raise HTTPException(422, "CSV has no recognised feature columns (expected Attr names such as Attr26).")
    bid = uuid.uuid4().hex[:12]; out = []
    for r in rows:
        vals = {k: (float(v) if v not in (None, "") else None) for k, v in r.items() if k in keys}
        a = run_one(s, u, company_id, vals, bid); out.append(a.id)
    s.add(Notification(user_id=u.id, kind="report", title="Batch prediction completed", body=f"{len(out)} rows processed (batch {bid})")); s.commit()
    audit(s, u, "batch_predict", f"{bid} rows={len(out)}"); return {"batch_id": bid, "count": len(out), "assessment_ids": out}
@app.get("/api/assessments/batch/{bid}/download")
def dl(bid: str, u=Depends(user_dep), s: Session = Depends(db)):
    rows = s.query(Assessment).filter(Assessment.batch_id == bid, Assessment.analyst_id == u.id).order_by(Assessment.id).all()
    if not rows: raise HTTPException(404, "Batch not found.")
    buf = io.StringIO(); w = csv.writer(buf); w.writerow(["assessment_id", "company", "probability", "risk_level", "top_risk_factor", "created_at"])
    for a in rows: w.writerow([a.id, a.company.name, round(a.probability, 4), a.risk_level, a.top_risk_factor, a.created_at])
    buf.seek(0); return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=batch_{bid}.csv"})
@app.delete("/api/assessments/{aid}")
def delete_assessment(aid: int, u=Depends(user_dep), s: Session = Depends(db)):
    a = s.query(Assessment).filter(Assessment.id == aid, Assessment.analyst_id == u.id).first()
    if not a:
        raise HTTPException(404, "Assessment not found in your workspace.")
    company_name = a.company.name if a.company else "Unknown company"
    s.delete(a)
    s.commit()
    audit(s, u, "assessment_delete", f"id={aid}; company={company_name}")
    return {"ok": True, "deleted_id": aid}

@app.get("/api/assessments/{aid}/report")
def report(aid: int, u=Depends(user_dep), s: Session = Depends(db)):
    a = s.query(Assessment).filter(Assessment.id == aid, Assessment.analyst_id == u.id).first()
    if not a: raise HTTPException(404, "Assessment not found in your workspace.")
    d = ao(a, s); buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["Company", d["company_name"]]); w.writerow(["Date", d["created_at"]]); w.writerow(["Probability", d["probability"]]); w.writerow(["Risk level", d["risk_level"]])
    w.writerow([]); w.writerow(["Feature", "Value", "SHAP", "Direction"])
    for e in d["shap"]: w.writerow([e["label"], e["value"], round(e["shap"], 4), e["direction"]])
    w.writerow([]); w.writerow(["Warning severity", "Indicator", "Reason"])
    for x in d["warnings"]: w.writerow([x["severity"], x["indicator"], x["reason"]])
    buf.seek(0); return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=assessment_{aid}.csv"})

# ---------- dashboard ----------
@app.get("/api/dashboard/summary")
def dsum(u=Depends(user_dep), s: Session = Depends(db)):
    base = s.query(Assessment).filter(Assessment.analyst_id == u.id)
    c = lambda lv: base.filter(Assessment.risk_level == lv).count()
    return dict(total_companies=s.query(func.count(Company.id)).filter(Company.created_by == u.id).scalar(), total_assessments=base.count(),
                high_risk=c("high"), critical_risk=c("critical"), trend=None)
@app.get("/api/dashboard/risk-distribution")
def ddist(u=Depends(user_dep), s: Session = Depends(db)):
    d = dict(s.query(Assessment.risk_level, func.count()).filter(Assessment.analyst_id == u.id).group_by(Assessment.risk_level).all())
    return [dict(level=l, count=d.get(l, 0)) for l in ("low", "moderate", "high", "critical")]
@app.get("/api/dashboard/recent-assessments")
def drecent(u=Depends(user_dep), s: Session = Depends(db)):
    return [ao(a, s, False) for a in s.query(Assessment).filter(Assessment.analyst_id == u.id).order_by(Assessment.id.desc()).limit(6)]

# ---------- model ----------
@app.get("/api/model/info")
def minfo(u=Depends(user_dep), s: Session = Depends(db)):
    m = ml.load()["meta"]; rec = s.query(ModelRecord).filter_by(is_active=True).first()
    return {**{k: m[k] for k in ("model_name","version","trained_at","dataset","n_rows_total","n_train","n_test","n_train_after_smote","n_features_selected",
        "features","metrics_default_threshold","confusion_matrix","roc_curve","pr_curve","shap_importance","notes","bankrupt_rate")},
        "feature_labels": {f: ml.describe(f) for f in m["features"]}, "status": rec.status if rec else None}
@app.post("/api/admin/model/train")
def train(bg: BackgroundTasks, a=Depends(admin_dep), s: Session = Depends(db)):
    s.add(Notification(user_id=a.id, kind="model", title="Candidate model training started", body="Training runs on the server.")); s.commit()
    audit(s, a, "model_train_start")
    def job():
        r = subprocess.run([sys.executable, "-m", "ml.train"], capture_output=True, text=True)
        s2 = SessionLocal(); s2.add(Notification(user_id=a.id, kind="model", title="Model training " + ("finished" if r.returncode == 0 else "failed"),
            body="Artifacts regenerated; restart the API to activate." if r.returncode == 0 else r.stderr[-200:])); s2.commit(); s2.close()
    bg.add_task(job); return {"status": "started"}

# ---------- notifications ----------
@app.get("/api/notifications")
def notes(u=Depends(user_dep), s: Session = Depends(db)):
    return [dict(id=n.id, kind=n.kind, title=n.title, body=n.body, is_read=n.is_read, created_at=n.created_at) for n in s.query(Notification).filter(Notification.user_id == u.id).order_by(Notification.id.desc()).limit(20)]
@app.post("/api/notifications/read-all")
def readall(u=Depends(user_dep), s: Session = Depends(db)):
    s.query(Notification).filter(Notification.user_id == u.id).update({"is_read": True}); s.commit(); return {"ok": True}

# ---------- assistant ----------
class Chat(BaseModel):
    message: str
    assessment_id: Optional[int] = None

@app.post("/api/assistant/chat")
def chat(b: Chat, u=Depends(user_dep), s: Session = Depends(db)):
    message = b.message.strip()
    if not message:
        raise HTTPException(422, "Please enter a question.")
    if len(message) > 2000:
        raise HTTPException(422, "Please keep the message under 2,000 characters.")
    ctx = None
    context_assessment_id = None
    if b.assessment_id:
        a = s.query(Assessment).filter(Assessment.id == b.assessment_id, Assessment.analyst_id == u.id).first()
        if not a:
            raise HTTPException(404, "Assessment not found in your workspace.")
        context_assessment_id = a.id
    else:
        # Make the suggested 'latest assessment' prompt useful from any page.
        # This follows the platform's existing shared assessment-history visibility.
        a = s.query(Assessment).filter(Assessment.analyst_id == u.id).order_by(Assessment.created_at.desc()).first()
        if a:
            context_assessment_id = a.id
    if context_assessment_id:
        a = s.get(Assessment, context_assessment_id)
        ctx = ao(a, s)
        ctx.pop("inputs", None)  # Never send raw input values to the external model.
    try:
        result = answer_with_mode(message, ctx, ml.load()["meta"])
        if not isinstance(result, dict) or not isinstance(result.get("reply"), str) or not result["reply"].strip():
            raise ValueError("The assistant returned an empty response.")
    except Exception:
        # Keep the chat panel usable even if the optional model/provider fails.
        result = {"reply": "I couldn't generate an answer just now. Please try again, or ask about SHAP, XGBoost, liquidity, leverage, SMOTE, or risk scores.",
                  "mode": "fallback", "notice": "The assistant used a safe fallback because the response service was unavailable."}
    return {**result, "context_used": bool(ctx), "context_assessment_id": context_assessment_id}
