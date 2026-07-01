"""SQLAlchemy models.

Design notes:
- Monetary values are stored as floats (CAD). All tax math rounds at the
  reporting boundary, matching how the original RigBooks app behaved.
- Every financially significant table gets created_at/updated_at plus an
  AuditLog entry written by the routers (CRA record-keeping: 6+ years).
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


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(512))


class Setting(Base):
    """Key/value store for business profile, shareholders, preferences."""
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class BankTransaction(Base, TimestampMixin):
    """A line imported from a bank/credit-card CSV statement."""
    __tablename__ = "bank_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(Text)
    debit: Mapped[float] = mapped_column(Float, default=0.0)
    credit: Mapped[float] = mapped_column(Float, default=0.0)
    category: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), default="business")  # business|personal|exclude
    itc: Mapped[float] = mapped_column(Float, default=0.0)
    source_file: Mapped[str] = mapped_column(String(255), default="")
    notes: Mapped[str] = mapped_column(Text, default="")


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    email: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(64), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    gst_number: Mapped[str] = mapped_column(String(32), default="")
    is_ccpc: Mapped[bool] = mapped_column(Boolean, default=False)  # relevant for T4A box 048
    notes: Mapped[str] = mapped_column(Text, default="")

    invoices: Mapped[list["Invoice"]] = relationship(back_populates="customer")


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(32), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    date: Mapped[date] = mapped_column(Date, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft|sent|paid|void
    gst_rate: Mapped[float] = mapped_column(Float, default=0.05)
    notes: Mapped[str] = mapped_column(Text, default="")

    customer: Mapped[Customer] = relationship(back_populates="invoices")
    lines: Mapped[list["InvoiceLine"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )

    @property
    def subtotal(self) -> float:
        return round(sum(l.quantity * l.unit_price for l in self.lines), 2)

    @property
    def gst(self) -> float:
        return round(self.subtotal * self.gst_rate, 2)

    @property
    def total(self) -> float:
        return round(self.subtotal + self.gst, 2)


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))
    description: Mapped[str] = mapped_column(Text)
    quantity: Mapped[float] = mapped_column(Float, default=1.0)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)

    invoice: Mapped[Invoice] = relationship(back_populates="lines")


class RevenueEntry(Base, TimestampMixin):
    """Manually entered income: hauling tickets, jobs, consulting."""
    __tablename__ = "revenue_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    client: Mapped[str] = mapped_column(String(255), default="")
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    job: Mapped[str] = mapped_column(String(255), default="")
    amount: Mapped[float] = mapped_column(Float)
    gst_included: Mapped[bool] = mapped_column(Boolean, default=True)
    gst_amount: Mapped[float] = mapped_column(Float, default=0.0)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class Expense(Base, TimestampMixin):
    """Unified expense record.

    source: cash | personal (paid from a personal account, reimbursable) |
            other (training/PPE/software) | vehicle (loan, insurance, repairs)
    business_pct lets mixed-use costs (vehicle, phone-like) claim only the
    business portion, per the CRA actual-expense method.
    """
    __tablename__ = "expenses"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    vendor: Mapped[str] = mapped_column(String(255), default="")  # used for T4A box 048 aggregation
    amount: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(16), default="cash", index=True)
    paid_by: Mapped[str] = mapped_column(String(128), default="")
    receipt_ref: Mapped[str] = mapped_column(String(255), default="")
    business_pct: Mapped[float] = mapped_column(Float, default=100.0)
    itc: Mapped[float] = mapped_column(Float, default=0.0)
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class PhoneBill(Base, TimestampMixin):
    __tablename__ = "phone_bills"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner: Mapped[str] = mapped_column(String(128))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    amount: Mapped[float] = mapped_column(Float)
    business_pct: Mapped[float] = mapped_column(Float, default=60.0)
    notes: Mapped[str] = mapped_column(Text, default="")


class Vehicle(Base, TimestampMixin):
    __tablename__ = "vehicles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    make_model: Mapped[str] = mapped_column(String(128), default="")
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    plate: Mapped[str] = mapped_column(String(32), default="")
    notes: Mapped[str] = mapped_column(Text, default="")


class FuelPurchase(Base, TimestampMixin):
    """Fuel is tracked separately from generic expenses because IFTA needs
    litres and jurisdiction, and fuel for the rig is 100% business use."""
    __tablename__ = "fuel_purchases"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"), nullable=True)
    vendor: Mapped[str] = mapped_column(String(255), default="")
    jurisdiction: Mapped[str] = mapped_column(String(8), default="AB")  # province/state code
    litres: Mapped[float] = mapped_column(Float, default=0.0)
    amount: Mapped[float] = mapped_column(Float)
    fuel_type: Mapped[str] = mapped_column(String(16), default="diesel")
    itc: Mapped[float] = mapped_column(Float, default=0.0)
    receipt_ref: Mapped[str] = mapped_column(String(255), default="")
    notes: Mapped[str] = mapped_column(Text, default="")


class Trip(Base, TimestampMixin):
    """Mileage-log entry (CRA logbook + IFTA distance record).

    jurisdiction_km: {"AB": 320, "SK": 110} — distance travelled per
    jurisdiction, used for IFTA apportionment. Defaults to all km in the
    home jurisdiction when not broken out.
    """
    __tablename__ = "trips"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"), nullable=True)
    origin: Mapped[str] = mapped_column(String(255), default="")
    destination: Mapped[str] = mapped_column(String(255), default="")
    purpose: Mapped[str] = mapped_column(String(255), default="")
    odometer_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    odometer_end: Mapped[float | None] = mapped_column(Float, nullable=True)
    business_km: Mapped[float] = mapped_column(Float, default=0.0)
    total_km: Mapped[float] = mapped_column(Float, default=0.0)
    jurisdiction_km: Mapped[dict] = mapped_column(JSON, default=dict)
    revenue_amount: Mapped[float] = mapped_column(Float, default=0.0)  # optional: ticket value for profit-per-km
    notes: Mapped[str] = mapped_column(Text, default="")


class MealEntry(Base, TimestampMixin):
    """Meal/per-diem record. Simplified method = flat rate/meal (TL2 style);
    long-haul drivers deduct 80% instead of 50%."""
    __tablename__ = "meal_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    method: Mapped[str] = mapped_column(String(16), default="simplified")  # simplified|detailed
    meals_count: Mapped[int] = mapped_column(Integer, default=0)  # simplified method
    amount: Mapped[float] = mapped_column(Float, default=0.0)     # detailed method (receipts)
    long_haul: Mapped[bool] = mapped_column(Boolean, default=True)
    location: Mapped[str] = mapped_column(String(255), default="")
    receipt_ref: Mapped[str] = mapped_column(String(255), default="")
    notes: Mapped[str] = mapped_column(Text, default="")


class HomeOffice(Base, TimestampMixin):
    """Annual home-office (workspace-in-home) costs, one row per year."""
    __tablename__ = "home_office"
    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    rent: Mapped[float] = mapped_column(Float, default=0.0)
    property_tax: Mapped[float] = mapped_column(Float, default=0.0)
    insurance: Mapped[float] = mapped_column(Float, default=0.0)
    electricity: Mapped[float] = mapped_column(Float, default=0.0)
    gas: Mapped[float] = mapped_column(Float, default=0.0)
    water: Mapped[float] = mapped_column(Float, default=0.0)
    internet: Mapped[float] = mapped_column(Float, default=0.0)
    pct: Mapped[float] = mapped_column(Float, default=10.0)


class ClassifierRule(Base):
    """User-editable regex → category rules for the bank-CSV classifier."""
    __tablename__ = "classifier_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    pattern: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(64))
    priority: Mapped[int] = mapped_column(Integer, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class AuditLog(Base):
    """Append-only trail of every financial mutation (CRA audit readiness)."""
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    user: Mapped[str] = mapped_column(String(255), default="")
    action: Mapped[str] = mapped_column(String(16))  # create|update|delete|import|export|login
    entity: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), default="")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
