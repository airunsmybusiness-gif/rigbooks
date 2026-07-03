"""OilForge domain models.

Corporate single-owner oilfield contractor:
- Clients → well sites → jobs (work orders) → field-ticket entries → invoices
  (with construction-style holdbacks).
- Equipment with CCA class, maintenance history and disposal tracking.
- Shareholder ledger: withdrawals/contributions/dividends — no payroll.
Monetary values are CAD floats; rounding happens at reporting boundaries.
"""
from datetime import date, datetime, timezone

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey,
                        Integer, String, Text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


# ------------------------------------------------------------------ core

class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(512))


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class AuditLog(Base):
    """Append-only trail of every financial mutation (CRA: keep 6+ years)."""
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    user: Mapped[str] = mapped_column(String(255), default="")
    action: Mapped[str] = mapped_column(String(16))
    entity: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), default="")
    details: Mapped[dict] = mapped_column(JSON, default=dict)


# ------------------------------------------------------------------ banking

class BankTransaction(Base, TimestampMixin):
    __tablename__ = "bank_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(Text)
    debit: Mapped[float] = mapped_column(Float, default=0.0)
    credit: Mapped[float] = mapped_column(Float, default=0.0)
    category: Mapped[str] = mapped_column(String(64), index=True)
    # business | shareholder (owner draw / personal on corp card) | exclude
    status: Mapped[str] = mapped_column(String(16), default="business")
    itc: Mapped[float] = mapped_column(Float, default=0.0)
    source_file: Mapped[str] = mapped_column(String(255), default="")
    receipt_ref: Mapped[str] = mapped_column(String(255), default="")
    posted_shareholder_txn_id: Mapped[int | None] = mapped_column(
        ForeignKey("shareholder_txns.id"), nullable=True)
    split_parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("bank_transactions.id"), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class ClassifierRule(Base):
    __tablename__ = "classifier_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    pattern: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(64))
    priority: Mapped[int] = mapped_column(Integer, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


# ------------------------------------------------------------------ jobs

class Client(Base, TimestampMixin):
    __tablename__ = "clients"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    contact: Mapped[str] = mapped_column(String(255), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(64), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    gst_number: Mapped[str] = mapped_column(String(32), default="")
    notes: Mapped[str] = mapped_column(Text, default="")


class WellSite(Base, TimestampMixin):
    __tablename__ = "well_sites"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    lsd: Mapped[str] = mapped_column(String(64), default="")  # legal land description
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    region: Mapped[str] = mapped_column(String(128), default="")
    notes: Mapped[str] = mapped_column(Text, default="")


class Job(Base, TimestampMixin):
    """A contract / work order for a client at a well site."""
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(32), unique=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    site_id: Mapped[int | None] = mapped_column(ForeignKey("well_sites.id"), nullable=True)
    rate_type: Mapped[str] = mapped_column(String(16), default="day_rate")  # day_rate|hourly|fixed
    day_rate: Mapped[float] = mapped_column(Float, default=0.0)
    hourly_rate: Mapped[float] = mapped_column(Float, default=0.0)
    fixed_price: Mapped[float] = mapped_column(Float, default=0.0)
    mobilization_fee: Mapped[float] = mapped_column(Float, default=0.0)
    holdback_pct: Mapped[float] = mapped_column(Float, default=0.0)  # builders-lien style
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    # quoted | active | complete | closed
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")

    client: Mapped[Client] = relationship()
    site: Mapped[WellSite | None] = relationship()


class JobEntry(Base, TimestampMixin):
    """Field ticket line: a day worked, hours, mobilization or other charge.
    The billing basis for progress invoices; equipment link feeds
    utilization stats."""
    __tablename__ = "job_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    kind: Mapped[str] = mapped_column(String(16), default="day")  # day|hours|mobilization|charge
    description: Mapped[str] = mapped_column(Text, default="")
    quantity: Mapped[float] = mapped_column(Float, default=1.0)
    rate: Mapped[float] = mapped_column(Float, default=0.0)
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"), nullable=True)
    ticket_ref: Mapped[str] = mapped_column(String(64), default="")  # field ticket #
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")

    @property
    def amount(self) -> float:
        return round(self.quantity * self.rate, 2)


# ------------------------------------------------------------------ invoicing

class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(32), unique=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft|sent|paid|void
    gst_rate: Mapped[float] = mapped_column(Float, default=0.05)
    holdback_pct: Mapped[float] = mapped_column(Float, default=0.0)
    holdback_released: Mapped[bool] = mapped_column(Boolean, default=False)
    holdback_released_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")

    client: Mapped[Client] = relationship()
    job: Mapped[Job | None] = relationship()
    lines: Mapped[list["InvoiceLine"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan")

    @property
    def subtotal(self) -> float:
        return round(sum(l.quantity * l.unit_price for l in self.lines), 2)

    @property
    def gst(self) -> float:
        # GST applies to the full consideration, including any held-back part.
        return round(self.subtotal * self.gst_rate, 2)

    @property
    def holdback(self) -> float:
        return round(self.subtotal * self.holdback_pct / 100, 2)

    @property
    def total(self) -> float:
        return round(self.subtotal + self.gst, 2)

    @property
    def amount_due_now(self) -> float:
        due = self.total - (0.0 if self.holdback_released else self.holdback)
        return round(due, 2)


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))
    description: Mapped[str] = mapped_column(Text)
    quantity: Mapped[float] = mapped_column(Float, default=1.0)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)

    invoice: Mapped[Invoice] = relationship(back_populates="lines")


# ------------------------------------------------------------------ expenses

class Expense(Base, TimestampMixin):
    """Corporate expense; optional job link (job costing) and equipment link
    (running costs per asset)."""
    __tablename__ = "expenses"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    vendor: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    amount: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(64), index=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True, index=True)
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"), nullable=True)
    receipt_ref: Mapped[str] = mapped_column(String(255), default="")
    itc: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str] = mapped_column(Text, default="")


# ------------------------------------------------------------------ equipment

class Equipment(Base, TimestampMixin):
    """Capital asset with CCA class for depreciation schedules."""
    __tablename__ = "equipment"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    serial: Mapped[str] = mapped_column(String(128), default="")
    cca_class: Mapped[str] = mapped_column(String(8), default="8")
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    acquired: Mapped[date | None] = mapped_column(Date, nullable=True)
    disposed: Mapped[date | None] = mapped_column(Date, nullable=True)
    disposal_proceeds: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active|sold|retired
    notes: Mapped[str] = mapped_column(Text, default="")


class MaintenanceLog(Base, TimestampMixin):
    __tablename__ = "maintenance_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    kind: Mapped[str] = mapped_column(String(16), default="service")  # service|repair|inspection|fuel|parts
    description: Mapped[str] = mapped_column(Text, default="")
    hours_reading: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    vendor: Mapped[str] = mapped_column(String(255), default="")
    receipt_ref: Mapped[str] = mapped_column(String(255), default="")


# ------------------------------------------------------------------ shareholder

class Shareholder(Base, TimestampMixin):
    __tablename__ = "shareholders"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), default="")
    ownership_pct: Mapped[float] = mapped_column(Float, default=100.0)
    notes: Mapped[str] = mapped_column(Text, default="")


class ShareholderTxn(Base, TimestampMixin):
    """One movement on the shareholder loan account.

    Sign convention (corporation's perspective):
      +amount → shareholder owes the corporation more (withdrawal, personal
                expense paid by corp)
      -amount → corporation owes the shareholder more / balance reduced
                (contribution, corp expense paid personally, repayment,
                 dividend applied against the loan)
    The signed direction is derived from `type`; `amount` is entered positive.
    """
    __tablename__ = "shareholder_txns"
    id: Mapped[int] = mapped_column(primary_key=True)
    shareholder_id: Mapped[int] = mapped_column(ForeignKey("shareholders.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    # withdrawal | personal_expense | contribution | corp_expense_paid_personally
    # | loan_repayment | dividend_applied
    amount: Mapped[float] = mapped_column(Float)
    memo: Mapped[str] = mapped_column(Text, default="")
    bank_txn_id: Mapped[int | None] = mapped_column(ForeignKey("bank_transactions.id"),
                                                    nullable=True)


class DividendDeclaration(Base, TimestampMixin):
    """A dividend declared by directors' resolution. `settlement`:
    cash (paid out) or loan (credited against the shareholder loan — the
    typical year-end cleanup for owner draws)."""
    __tablename__ = "dividend_declarations"
    id: Mapped[int] = mapped_column(primary_key=True)
    shareholder_id: Mapped[int] = mapped_column(ForeignKey("shareholders.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[float] = mapped_column(Float)
    kind: Mapped[str] = mapped_column(String(16), default="non_eligible")  # eligible|non_eligible
    settlement: Mapped[str] = mapped_column(String(8), default="loan")  # loan|cash
    resolution_ref: Mapped[str] = mapped_column(String(128), default="")  # minutes / resolution #
    notes: Mapped[str] = mapped_column(Text, default="")
