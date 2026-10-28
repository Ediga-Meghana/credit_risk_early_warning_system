from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from .core import Base, now
class User(Base):
    __tablename__="users"
    id=Column(Integer,primary_key=True); email=Column(String(190),unique=True,index=True); full_name=Column(String(120))
    password_hash=Column(String(255)); role=Column(String(20),default="analyst"); is_active=Column(Boolean,default=True)
    last_login=Column(DateTime,nullable=True); created_at=Column(DateTime,default=now)
class Company(Base):
    __tablename__="companies"
    id=Column(Integer,primary_key=True); name=Column(String(190),index=True); registration_no=Column(String(60),nullable=True)
    sector=Column(String(100),nullable=True); country=Column(String(60),nullable=True)
    created_by=Column(Integer,ForeignKey("users.id")); created_at=Column(DateTime,default=now)
    assessments=relationship("Assessment",back_populates="company",cascade="all,delete")
class Assessment(Base):
    __tablename__="assessments"
    id=Column(Integer,primary_key=True); company_id=Column(Integer,ForeignKey("companies.id"),index=True)
    analyst_id=Column(Integer,ForeignKey("users.id")); created_at=Column(DateTime,default=now,index=True)
    probability=Column(Float); risk_level=Column(String(20),index=True); model_name=Column(String(40)); model_version=Column(String(20))
    inputs=Column(JSON); shap=Column(JSON); warnings=Column(JSON); recommendations=Column(JSON); base_value=Column(Float)
    top_risk_factor=Column(String(80),nullable=True); batch_id=Column(String(40),nullable=True)
    company=relationship("Company",back_populates="assessments"); analyst=relationship("User")
class Notification(Base):
    __tablename__="notifications"
    id=Column(Integer,primary_key=True); user_id=Column(Integer,ForeignKey("users.id"),nullable=True)  # null = all admins/analysts
    kind=Column(String(30)); title=Column(String(200)); body=Column(Text); is_read=Column(Boolean,default=False); created_at=Column(DateTime,default=now)
class AuditLog(Base):
    __tablename__="audit_logs"
    id=Column(Integer,primary_key=True); user_id=Column(Integer,nullable=True); email=Column(String(190),nullable=True)
    action=Column(String(60),index=True); detail=Column(Text,nullable=True); ip=Column(String(60),nullable=True); created_at=Column(DateTime,default=now,index=True)
class Setting(Base):
    __tablename__="settings"
    key=Column(String(60),primary_key=True); value=Column(JSON)
class ModelRecord(Base):
    __tablename__="model_records"
    id=Column(Integer,primary_key=True); name=Column(String(40)); version=Column(String(20)); status=Column(String(20)); trained_at=Column(DateTime)
    metrics=Column(JSON); n_features=Column(Integer); dataset_size=Column(Integer); is_active=Column(Boolean,default=False)


class SignupOTP(Base):
    __tablename__ = "signup_otps"
    email = Column(String(190), primary_key=True)
    full_name = Column(String(120), nullable=False)
    password_hash = Column(String(255), nullable=False)
    otp_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=now, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)


class MonitoredCompany(Base):
    """A user's ticker subscription for periodic credit-risk monitoring."""
    __tablename__ = "monitored_companies"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    symbol = Column(String(30), index=True, nullable=False)
    company_name = Column(String(190), nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=now, nullable=False)

class FinancialSnapshot(Base):
    """A dated snapshot of source financials and model risk output."""
    __tablename__ = "financial_snapshots"
    id = Column(Integer, primary_key=True)
    monitored_company_id = Column(Integer, ForeignKey("monitored_companies.id"), index=True, nullable=False)
    observed_at = Column(DateTime, default=now, nullable=False, index=True)
    source_period = Column(String(60), nullable=True)
    financials = Column(JSON, nullable=False)
    model_values = Column(JSON, nullable=False)
    risk_probability = Column(Float, nullable=True)
    risk_level = Column(String(20), nullable=True)
    change_summary = Column(JSON, nullable=True)
