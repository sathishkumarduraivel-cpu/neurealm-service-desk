"""In-process event bus. Subscribers: no-code workflow engine, integration connectors, auto-resolution."""
_subs = []
def subscribe(fn): _subs.append(fn); return fn
def emit(db, record, event, actor=None, changes=None):
    for fn in list(_subs):
        try: fn(db, record, event, actor, changes or {})
        except Exception as e:  # subscribers must never break core writes
            import logging; logging.exception("bus subscriber failed: %s", e)
