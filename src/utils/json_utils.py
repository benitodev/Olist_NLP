import json
from typing import Any, Dict, List


def _as_list(recs: Any) -> List[Dict[str, Any]]:
    if recs is None:
        return []
    if isinstance(recs, str):
        return json.loads(recs)
    return recs
