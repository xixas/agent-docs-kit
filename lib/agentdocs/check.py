"""Orchestrates docs-check: diff -> rule candidates + stale-value hits."""
from pathlib import Path

from . import docsmap, gitdiff, stale

# Machine-generated files whose version churn is never a doc signal.
LOCKFILES = ["*.lock", "**/*.lock", "package-lock.json", "pnpm-lock.yaml", "**/pnpm-lock.yaml",
             "cdk.context.json", "graphify-out/**"]


def run_check(repo, config_path=None, base="main", commit=None):
    repo = Path(repo)
    cfg = docsmap.load_config(config_path or repo / ".docs-map.yaml", repo)
    files = gitdiff.changed_files(repo, commit=commit, base=base)
    lines = gitdiff.diff_lines(repo, commit=commit, base=base)
    rules = docsmap.evaluate_rules(cfg, files, lines)
    tokens = stale.stale_tokens(lines, ignore=LOCKFILES)
    tokens, elsewhere, comments = stale.code_usage(repo, tokens, cfg.docs, cfg.exclude)
    hits = stale.find_in_docs(repo, tokens, cfg.docs, cfg.exclude, files)
    return {
        "rules": [{"id": c.rule_id, "evidence": c.evidence, "targets": c.targets,
                   "run": c.run, "note": c.note} for c in rules],
        "stale": [vars(h) for h in hits],
        "stale_comments": comments,
        "elsewhere": elsewhere if hits else [],
    }


def format_text(result):
    out = []
    for r in result["rules"]:
        out.append(f"[rule] {r['id']}")
        for e in r["evidence"]:
            out.append(f"   because: {e}")
        for t in r["targets"]:
            out.append(f"   update:  {t}")
        if r["run"]:
            out.append(f"   run:     {r['run']}")
        if r["note"]:
            out.append(f"   note:    {r['note']}")
    for h in result["stale"]:
        tag = " (changed in this diff)" if h["changed"] else ""
        out.append(f"[stale] {h['token']}  {h['path']}:{h['line']}{tag}  {h['text']}")
    for c in result.get("stale_comments", []):
        out.append(f"[stale-comment] {c['token']}  {c['path']}:{c['line']}  {c['text']}")
    if result.get("elsewhere"):
        out.append("-- value still used elsewhere in code (may also be stale) --")
        for e in result["elsewhere"]:
            out.append(f"[code] {e['token']}  {e['path']}:{e['line']}  {e['text']}")
    return "\n".join(out) if out else "docs-check: no candidates"
