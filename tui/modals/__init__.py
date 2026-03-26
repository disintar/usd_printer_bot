"""TUI modals package."""
from __future__ import annotations

from .order import OrderModal
from .transfer import TransferModal
from .deposit_withdraw import DepositWithdrawModal
from .agent_select import AgentSelectModal
from .agent_allocation import AgentAllocationModal

__all__ = [
    "OrderModal",
    "TransferModal",
    "DepositWithdrawModal",
    "AgentSelectModal",
    "AgentAllocationModal",
]
