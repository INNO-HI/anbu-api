"""모델 패키지 — import 시 세 DB의 모든 테이블이 메타데이터에 등록된다."""
from anbu_api.models.accum import (
    Alert,
    AmiUsageA,
    AmiUsageB,
    CareRecord,
    Device,
    DeviceStatusHistory,
    LedRawLog,
    LightingInterval,
    PowerUsage,
    Subject,
)
from anbu_api.models.ops import (
    AuditLog,
    EtlRun,
    PseudonymMapping,
    Subscription,
    SubscriptionReceipt,
    TransferHistory,
    User,
)
from anbu_api.models.transfer import (
    TRANSFER_TABLES,
    TAlert,
    TCareRecord,
    TDevice,
    TDeviceStatusHistory,
    TLightingInterval,
    TPowerUsage,
    TSubject,
)

__all__ = [
    # accum
    "Subject", "Device", "LedRawLog", "LightingInterval", "DeviceStatusHistory",
    "CareRecord", "Alert", "AmiUsageA", "AmiUsageB", "PowerUsage",
    # transfer
    "TSubject", "TDevice", "TLightingInterval", "TDeviceStatusHistory",
    "TCareRecord", "TAlert", "TPowerUsage", "TRANSFER_TABLES",
    # ops
    "PseudonymMapping", "TransferHistory", "SubscriptionReceipt", "Subscription",
    "User", "AuditLog", "EtlRun",
]
