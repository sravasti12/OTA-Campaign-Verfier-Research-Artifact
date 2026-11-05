"""Shared explicit authorization policy for nominal and recovery version changes."""
from .models import Campaign
from .versions import parse_version


def version_change_allowed(campaign: Campaign, ecu_id: str, before: str, after: str) -> bool:
    """Allow non-downgrades or a permission for this exact ECU and numeric destination."""
    if ecu_id not in {ecu.id for ecu in campaign.ecus}:
        raise ValueError(f'Unknown ECU {ecu_id}')
    if parse_version(after) >= parse_version(before):
        return True
    return any(permission.ecu_id == ecu_id
               and parse_version(permission.version) == parse_version(after)
               for permission in campaign.downgrade_authorizations)
