from __future__ import annotations

from decimal import Decimal
from enum import StrEnum


class SupportedAsset(StrEnum):
    USDT = "USDt"
    TSLAX = "TSLAx"
    HOODX = "HOODx"
    AMZNX = "AMZNx"
    NVDAX = "NVDAx"
    COINX = "COINx"
    GOOGLX = "GOOGLx"
    AAPLX = "AAPLx"
    MSTRX = "MSTRx"


SUPPORTED_ASSET_IDS: tuple[str, ...] = tuple(asset.value for asset in SupportedAsset)
TRADEABLE_ASSET_IDS: tuple[str, ...] = tuple(asset.value for asset in SupportedAsset if asset != SupportedAsset.USDT)

AGENT_IDS: tuple[str, ...] = ("Buy", "Cover", "Sell", "Short", "Hold")
DEFAULT_ADVISOR_IDS: tuple[str, ...] = ("warren_buffett", "pavel_durov")
RISK_PROFILE_IDS: tuple[str, ...] = ("low", "medium", "high")
DEFAULT_RISK_PROFILE: str = "medium"

DEFAULT_STARTING_CASH: Decimal = Decimal("1000.00")

TEST_PRICES: dict[str, Decimal] = {
    SupportedAsset.USDT.value: Decimal("1.00"),
    SupportedAsset.TSLAX.value: Decimal("215.40"),
    SupportedAsset.HOODX.value: Decimal("21.15"),
    SupportedAsset.AMZNX.value: Decimal("174.30"),
    SupportedAsset.NVDAX.value: Decimal("821.70"),
    SupportedAsset.COINX.value: Decimal("198.25"),
    SupportedAsset.GOOGLX.value: Decimal("151.60"),
    SupportedAsset.AAPLX.value: Decimal("192.80"),
    SupportedAsset.MSTRX.value: Decimal("1245.55"),
}
