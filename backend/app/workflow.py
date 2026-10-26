"""Back-compat shim over the module registry."""
from .registry import MODULES, initial, allowed as _allowed
from . import hooks
FLOWS = {k: v["flow"] for k, v in MODULES.items()}
INITIAL = {k: initial(k) for k in MODULES}
PREFIX = {k: v["prefix"] for k, v in MODULES.items()}
def allowed(module, state): return _allowed(module, state)
def change_risk(data, impact):
    class R: pass
    r = R(); r.data = data; r.impact = impact
    return hooks.change(r)
