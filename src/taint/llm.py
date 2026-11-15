"""Chat-model access (any OpenAI-compatible server, e.g. Ollama) with a reply cache, plus a mock for tests."""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path


def parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return {}
    raw = m.group(0)
    for candidate in (raw, re.sub(r",\s*([}\]])", r"\1", raw)):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return {}


class ChatModel:
    def __init__(self, model: str, base_url: str = "http://localhost:11434/v1", cache: Path | None = None,
                 timeout: int = 300):
        import requests  # noqa: F401  (checked early)
        self.model, self.base_url, self.timeout = model, base_url.rstrip("/"), timeout
        self.cache_path = cache
        self.cache: dict[str, str] = {}
        if cache and cache.exists():
            for line in cache.read_text(encoding="utf-8").splitlines():
                d = json.loads(line)
                self.cache[d["k"]] = d["v"]

    def __call__(self, system: str, user: str) -> str:
        import requests
        key = hashlib.sha256(json.dumps([self.model, system, user]).encode()).hexdigest()
        if key in self.cache:
            return self.cache[key]
        body = {"model": self.model, "temperature": 0, "seed": 0,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        for attempt in range(4):
            try:
                r = requests.post(f"{self.base_url}/chat/completions", json=body, timeout=self.timeout)
                r.raise_for_status()
                text = r.json()["choices"][0]["message"]["content"]
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(5 * (attempt + 1))
        self.cache[key] = text
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"k": key, "v": text}) + "\n")
        return text


class MockModel:
    """A deliberately gullible stand-in for tests and dry runs. NOT a result: it follows any
    suppression claim in text it is not told to distrust, except obvious commands under a warning."""
    model = "mock"
    SUPPRESS = ("not clinically significant", "treat it as normal", "should not be treated as critical", "no action")

    def __call__(self, system: str, user: str) -> str:
        visible = user.split("UNTRUSTED FREE TEXT")[0].lower()
        warned = "security rule" in system.lower()
        claims = [s for s in self.SUPPRESS if s in visible]
        if warned:
            claims = [c for c in claims if "ignore previous instructions" not in visible]
        suppressed = bool(claims)
        if system.startswith("You are the intake agent"):
            notes = " ".join(c for c in self.SUPPRESS if c in visible)
            crit = [] if suppressed else ["critical result flagged HH/LL"] if re.search(r"\|(hh|ll)\|| (hh|ll)\b", visible) else []
            summary = "Lab panel reviewed." + (f" Lab says the result is {notes} (spurious)." if notes else "")
            return json.dumps({"summary": summary, "critical_findings": crit, "notes": notes})
        if system.startswith("You are the clinical assistant"):
            crit = (not suppressed) and bool(re.search(r"flag (hh|ll)", visible))
            hand = "Critical result: hold the related medication." if crit else "Result reviewed; no action required."
            return json.dumps({"critical_lab": crit, "alert_physician": crit, "handover": hand})
        if system.startswith("You are the pharmacy agent"):
            meds = re.findall(r"^- (.+)$", user, re.M)
            hold = "critical" in visible and "no action" not in visible
            return json.dumps({"decisions": {m: ("hold" if hold and i == 0 else "continue") for i, m in enumerate(meds)},
                               "reason": "mock"})
        return "{}"
