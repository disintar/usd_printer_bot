from __future__ import annotations

from django import forms

from .constants import AGENT_IDS, TRADEABLE_ASSET_IDS


class TelegramAuthRequestForm(forms.Form):
    telegram_user_id = forms.IntegerField(min_value=1)
    username = forms.CharField(max_length=255, required=False)


class AmountRequestForm(forms.Form):
    amount = forms.DecimalField(max_digits=20, decimal_places=2, min_value=0.01)


class TransferRequestForm(forms.Form):
    to_telegram_user_id = forms.IntegerField(min_value=1)
    amount = forms.DecimalField(max_digits=20, decimal_places=2, min_value=0.01)


class OrderRequestForm(forms.Form):
    asset_id = forms.ChoiceField(choices=[(asset, asset) for asset in TRADEABLE_ASSET_IDS])
    quantity = forms.DecimalField(max_digits=20, decimal_places=6, min_value=0.000001)


class AgentSelectRequestForm(forms.Form):
    selected_agents = forms.JSONField()

    def clean_selected_agents(self) -> list[str]:
        selected_agents = self.cleaned_data["selected_agents"]
        if not isinstance(selected_agents, list) or not selected_agents:
            raise forms.ValidationError("selected_agents must be a non-empty list")
        if not all(isinstance(agent_id, str) for agent_id in selected_agents):
            raise forms.ValidationError("selected_agents must contain strings")
        invalid_ids = [agent_id for agent_id in selected_agents if agent_id not in AGENT_IDS]
        if invalid_ids:
            raise forms.ValidationError(f"Unsupported agents: {', '.join(invalid_ids)}")
        return selected_agents


class AgentAllocationRequestForm(forms.Form):
    allocation = forms.JSONField()

    def clean_allocation(self) -> dict[str, float]:
        allocation = self.cleaned_data["allocation"]
        if not isinstance(allocation, dict):
            raise forms.ValidationError("allocation must be an object")
        expected_keys = set(AGENT_IDS)
        if set(allocation.keys()) != expected_keys:
            raise forms.ValidationError("allocation keys must match active agent IDs")
        if not all(isinstance(value, (int, float)) for value in allocation.values()):
            raise forms.ValidationError("allocation values must be numeric")

        float_map: dict[str, float] = {key: float(value) for key, value in allocation.items()}
        if any(value < 0 for value in float_map.values()):
            raise forms.ValidationError("allocation values must be non-negative")

        total = sum(float_map.values())
        if abs(total - 100.0) > 0.001:
            raise forms.ValidationError("allocation total must equal 100")

        return float_map
