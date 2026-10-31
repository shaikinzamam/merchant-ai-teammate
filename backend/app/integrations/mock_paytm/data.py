"""SIMULATED merchant data. Nothing here is real Paytm data or a real API."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MerchantRecord:
    merchant_id: str
    display_name: str
    mid: str
    preferred_language: str
    bank_account_status: str = "ACTIVE"
    kyc_status: str = "VERIFIED"
    kyc_failed_attempts: int = 0
    fraud_flag: bool = False
    open_chargebacks: int = 0
    has_soundbox: bool = False
    has_edc: bool = False
    avg_daily_volume_inr: int = 0
    avg_daily_txn_count: int = 0
    bank_account_changed_days_ago: int | None = None
    devices: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TxnRecord:
    txn_id: str
    merchant_id: str
    amount_inr: int


def seed_merchants() -> dict[str, MerchantRecord]:
    ms = [
        MerchantRecord("M1001", "Ramesh (demo)", "MID_DEMO_1001", "hi",
                       avg_daily_volume_inr=42_000, avg_daily_txn_count=140, devices=["QR_1001"]),
        MerchantRecord("M1002", "Lakshmi (demo)", "MID_DEMO_1002", "te", has_soundbox=True,
                       avg_daily_volume_inr=18_000, avg_daily_txn_count=60,
                       devices=["SB_1002"]),
        MerchantRecord("M1003", "Fraud-flagged (demo)", "MID_DEMO_1003", "kn", fraud_flag=True,
                       avg_daily_volume_inr=30_000, avg_daily_txn_count=90, devices=["QR_1003"]),
        MerchantRecord("M1004", "KYC-failures (demo)", "MID_DEMO_1004", "en",
                       kyc_status="REJECTED", kyc_failed_attempts=3,
                       avg_daily_volume_inr=12_000, devices=["QR_1004"]),
        MerchantRecord("M1005", "Big-volume (demo)", "MID_DEMO_1005", "en",
                       avg_daily_volume_inr=180_000, avg_daily_txn_count=600, devices=["QR_1005"]),
    ]
    return {m.merchant_id: m for m in ms}


def seed_transactions() -> dict[str, TxnRecord]:
    ts = [
        TxnRecord("TXN100001", "M1001", 2_500),
        TxnRecord("TXN100002", "M1001", 250_000),   # high-value -> risk engine escalates disputes
        TxnRecord("TXN200001", "M1002", 900),
    ]
    return {t.txn_id: t for t in ts}


FAQ = {
    "settlement_timing": "Settlements are normally credited on the next banking day; bank "
                         "holidays can delay clearing.",
    "qr_help": "You can request a replacement QR if yours is damaged or lost.",
    "soundbox_setup": "Keep the Soundbox powered, connected to the network and near your phone.",
    "dispute_process": "Share the transaction ID and reason; a team member reviews each dispute.",
    "kyc_process": "KYC needs valid ID and bank details; repeated failures are reviewed by staff.",
}
