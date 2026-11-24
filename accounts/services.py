import ipaddress

from .models import AuditEvent


def write_audit(actor, action, object_type, object_id, request=None):
    """Append one entry to the audit log."""
    # Never store request bodies, passwords, JWTs, cookies, or arbitrary headers
    ip = None
    user_agent = ""
    if request is not None:
        candidate = request.META.get("REMOTE_ADDR")
        if candidate:
            try:
                ip = str(ipaddress.ip_address(candidate))
            except ValueError:
                ip = None
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
    return AuditEvent.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action[:100],
        object_type=object_type[:100],
        object_id=str(object_id)[:100],
        ip_address=ip,
        user_agent=user_agent,
    )