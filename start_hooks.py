# start_hooks.py
"""
Tiny glue functions to keep handlers.py unchanged except for two one-line calls.
"""

from deep_link_gate import deliver_or_gate_deeplink, complete_deeplink_verification

async def handle_start_v_param(update, context, arg: str) -> bool:
    """
    If arg looks like v_<message_id>, perform gated delivery and return True (handled).
    Otherwise return False so the caller can continue normal logic.
    """
    if not arg.startswith("v_"):
        return False
    try:
        msg_id = int(arg[2:])
    except ValueError:
        return False
    await deliver_or_gate_deeplink(update, context, msg_id)
    return True

async def handle_start_dl_param(update, context, arg: str) -> bool:
    """
    If arg looks like dl_<token>, finalize deep-link verification and return True.
    Otherwise False.
    """
    if not arg.startswith("dl_"):
        return False
    token = arg[3:]
    await complete_deeplink_verification(update, context, token)
    return True
