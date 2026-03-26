"""Risk service for portfolio risk assessment."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from ..models import AssetPosition, WalletAccount
from .prices import PricesService

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class RiskAssessment:
    """Risk assessment result for a portfolio."""

    risk_score: Decimal
    risk_level: str
    max_position_percent: Decimal
    cash_percent: Decimal
    equity_usdt: Decimal


class RiskService:
    """Service for portfolio risk assessment."""

    @classmethod
    def _calculate_risk_score(cls, account: WalletAccount) -> tuple[Decimal, str]:
        """
        Calculate risk score and level for the portfolio.

        Returns (risk_score, risk_level) where risk_score is 0-100.
        """
        positions = list(AssetPosition.objects.filter(account=account, quantity__gt=0))

        if not positions:
            return Decimal("0"), "very_low"

        equity = account.cash_balance
        for position in positions:
            price = PricesService.get_price(position.asset_id)
            equity += position.quantity * price

        if equity <= 0:
            return Decimal("100"), "very_high"

        # Calculate concentration risk (max position as % of equity)
        max_position_percent = Decimal("0")
        for position in positions:
            price = PricesService.get_price(position.asset_id)
            position_value = position.quantity * price
            position_percent = (position_value / equity) * Decimal("100")
            if position_percent > max_position_percent:
                max_position_percent = position_percent

        # Calculate cash ratio
        cash_percent = (account.cash_balance / equity) * Decimal("100")

        # Risk score formula:
        # Higher risk for concentration, lower risk for cash buffer
        concentration_risk = min(float(max_position_percent) / 2, 50.0)
        cash_benefit = min(float(cash_percent) / 2, 25.0)

        risk_score = Decimal(str(50.0 + concentration_risk - cash_benefit))
        risk_score = max(Decimal("0"), min(Decimal("100"), risk_score))

        # Determine risk level
        if risk_score < 20:
            risk_level = "very_low"
        elif risk_score < 40:
            risk_level = "low"
        elif risk_score < 60:
            risk_level = "medium"
        elif risk_score < 80:
            risk_level = "high"
        else:
            risk_level = "very_high"

        return risk_score.quantize(Decimal("0.1")), risk_level

    @classmethod
    def get_risk_assessment(cls, account: WalletAccount) -> RiskAssessment:
        """Get complete risk assessment for an account."""
        positions = list(AssetPosition.objects.filter(account=account, quantity__gt=0))

        equity = account.cash_balance
        for position in positions:
            price = PricesService.get_price(position.asset_id)
            equity += position.quantity * price

        max_position_percent = Decimal("0")
        for position in positions:
            price = PricesService.get_price(position.asset_id)
            position_value = position.quantity * price
            position_percent = (position_value / equity * Decimal("100")) if equity > 0 else Decimal("0")
            if position_percent > max_position_percent:
                max_position_percent = position_percent

        cash_percent = (account.cash_balance / equity * Decimal("100")) if equity > 0 else Decimal("0")

        risk_score, risk_level = cls._calculate_risk_score(account)

        return RiskAssessment(
            risk_score=risk_score,
            risk_level=risk_level,
            max_position_percent=max_position_percent.quantize(Decimal("0.01")),
            cash_percent=cash_percent.quantize(Decimal("0.01")),
            equity_usdt=equity.quantize(Decimal("0.01")),
        )

