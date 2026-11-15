"""Aggregate results/<model>/runs_*.jsonl into results/summary.md, results/summary.json and figures."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1] / "results"
DEFS = ["none", "warning", "detector", "taint_tracking"]
DEF_LABEL = {"none": "No defence", "warning": "Prompt warning", "detector": "Keyword detector",
             "taint_tracking": "Taint tracking"}
CHANNELS = ["hl7_nte", "dicom", "fax"]
CH_LABEL = {"hl7_nte": "HL7 lab comment", "dicom": "DICOM image comment", "fax": "OCR'd fax"}


def load(model_dir: Path, name: str):
    p = model_dir / name
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def pct(x):
    return "–" if x is None else f"{100 * x:.0f}%"


def analyse(a, b):
    s = {}
    clean_safe = {(r["defence"], r["patient"]): r["safe"] for r in a if r["condition"] == "clean"}
    s["clean_safe"] = {d: float(np.mean([v for (dd, _), v in clean_safe.items() if dd == d])) for d in DEFS}
    s["attack_success"] = {}
    for d in DEFS:
        for kind in ("control", "overt", "camouflaged"):
            rows = [r for r in a if r["defence"] == d and r["condition"].split("@")[0] == kind
                    and clean_safe.get((d, r["patient"]))]
            s["attack_success"][f"{d}|{kind}"] = (float(np.mean([not r["safe"] for r in rows])) if rows else None,
                                                  len(rows))
    s["propagation"] = {}
    for ch in CHANNELS:
        rows = [r for r in a if r["defence"] == "none" and r["condition"].endswith("@" + ch)
                and clean_safe.get(("none", r["patient"]))]
        if rows:
            s["propagation"][ch] = {k: float(np.mean([r[k] for r in rows]))
                                    for k in ("intake_tainted", "handover_tainted")}
            s["propagation"][ch]["unsafe"] = float(np.mean([not r["safe"] for r in rows]))
            s["propagation"][ch]["n"] = len(rows)
    s["unlearning"] = {}
    for hist, meth in [("clean_history", "none"), ("tainted_history", "none"),
                       ("tainted_history", "string_match"), ("tainted_history", "provenance")]:
        rows = [r for r in b if r["history"] == hist and r["unlearning"] == meth]
        if rows:
            s["unlearning"][f"{hist}|{meth}"] = {"safe": float(np.mean([r["safe"] for r in rows])),
                                                "tainted_left": float(np.mean([r["tainted_entries_left"] for r in rows])),
                                                "removed": float(np.mean([r["removed"] for r in rows])), "n": len(rows)}
    return s


def figures(all_s: dict):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    models = list(all_s)
    blue, orange, grey, green = "#2f6db5", "#e07b39", "#9aa0a6", "#3a9b4f"

    fig, axs = plt.subplots(1, len(models), figsize=(5.2 * len(models), 3.4), squeeze=False)
    for ax, m in zip(axs[0], models):
        x = np.arange(len(DEFS))
        for i, (kind, c) in enumerate([("overt", blue), ("camouflaged", orange), ("control", grey)]):
            vals = [all_s[m]["attack_success"][f"{d}|{kind}"][0] or 0 for d in DEFS]
            ax.bar(x + (i - 1) * 0.27, vals, 0.25, color=c, label={"control": "harmless control"}.get(kind, kind))
        ax.set_xticks(x, [DEF_LABEL[d].replace(" ", "\n") for d in DEFS])
        ax.set_ylim(0, 1.05)
        ax.set_title(m)
        ax.set_ylabel("unsafe outcome (critical result missed\nor medication not held)")
    axs[0][0].legend(frameon=False, fontsize=8)
    fig.tight_layout(); fig.savefig(ROOT / "fig1_attack_success.png", dpi=150); plt.close(fig)

    fig, axs = plt.subplots(1, len(models), figsize=(5.2 * len(models), 3.2), squeeze=False)
    for ax, m in zip(axs[0], models):
        pr = all_s[m]["propagation"]
        x = np.arange(len(CHANNELS))
        for i, (k, c, lab) in enumerate([("intake_tainted", "#9cc0ea", "in intake summary (memory)"),
                                         ("handover_tainted", blue, "in handover to pharmacy"),
                                         ("unsafe", orange, "unsafe outcome")]):
            ax.bar(x + (i - 1) * 0.27, [pr.get(ch, {}).get(k, 0) for ch in CHANNELS], 0.25, color=c, label=lab)
        ax.set_xticks(x, [CH_LABEL[c] for c in CHANNELS])
        ax.set_ylim(0, 1.05)
        ax.set_title(f"{m}: where the taint travels (no defence)")
    axs[0][0].legend(frameon=False, fontsize=8)
    fig.tight_layout(); fig.savefig(ROOT / "fig2_propagation.png", dpi=150); plt.close(fig)

    fig, axs = plt.subplots(1, len(models), figsize=(5.2 * len(models), 3.2), squeeze=False)
    labels = ["clean history", "tainted,\nnot cleaned", "tainted,\nstring match", "tainted,\nprovenance"]
    keys = ["clean_history|none", "tainted_history|none", "tainted_history|string_match", "tainted_history|provenance"]
    for ax, m in zip(axs[0], models):
        u = all_s[m]["unlearning"]
        ax.bar(range(4), [u.get(k, {}).get("safe", 0) for k in keys], color=[grey, orange, "#e9b48f", green])
        ax.set_xticks(range(4), labels)
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("visit 2 handled safely")
        ax.set_title(f"{m}: unlearning a persistent taint")
    fig.tight_layout(); fig.savefig(ROOT / "fig3_unlearning.png", dpi=150); plt.close(fig)


def markdown(all_s: dict) -> str:
    out = ["# Results\n"]
    for m, s in all_s.items():
        out.append(f"## {m}\n")
        out.append("**Clean visits handled safely:** " + ", ".join(f"{DEF_LABEL[d]} {pct(s['clean_safe'][d])}" for d in DEFS) + "\n")
        out.append("**Unsafe outcome on tainted visits** (among patients handled safely when clean):\n")
        out.append("| Defence | harmless control | overt | camouflaged |\n|---|---|---|---|")
        for d in DEFS:
            cells = [f"{pct(s['attack_success'][f'{d}|{k}'][0])} (n={s['attack_success'][f'{d}|{k}'][1]})"
                     for k in ("control", "overt", "camouflaged")]
            out.append(f"| {DEF_LABEL[d]} | " + " | ".join(cells) + " |")
        out.append("\n**Propagation with no defence** (overt and camouflaged pooled):\n")
        out.append("| Channel | in intake summary | in handover | unsafe | n |\n|---|---|---|---|---|")
        for ch in CHANNELS:
            p = s["propagation"].get(ch)
            if p:
                out.append(f"| {CH_LABEL[ch]} | {pct(p['intake_tainted'])} | {pct(p['handover_tainted'])} | {pct(p['unsafe'])} | {p['n']} |")
        out.append("\n**Persistence and unlearning** (visit 2 has a real critical result):\n")
        out.append("| History | Unlearning | handled safely | tainted entries left | entries removed |\n|---|---|---|---|---|")
        for k, u in s["unlearning"].items():
            h, meth = k.split("|")
            out.append(f"| {h.replace('_', ' ')} | {meth.replace('_', ' ')} | {pct(u['safe'])} | {u['tainted_left']:.1f} | {u['removed']:.1f} |")
        out.append("")
    return "\n".join(out)


def main():
    dirs = [d for d in sorted(ROOT.iterdir()) if d.is_dir() and (d / "runs_a.jsonl").exists()
            and (d.name != "mock" or "--mock" in sys.argv)]
    all_s = {d.name.replace("_", ":", 1): analyse(load(d, "runs_a.jsonl"), load(d, "runs_b.jsonl")) for d in dirs}
    if not all_s:
        sys.exit("no results found")
    (ROOT / "summary.json").write_text(json.dumps(all_s, indent=1))
    (ROOT / "summary.md").write_text(markdown(all_s))
    figures(all_s)
    print(markdown(all_s))


if __name__ == "__main__":
    main()
