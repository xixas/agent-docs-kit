"""Load/validate .docs-map.yaml and evaluate rules against a diff."""
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import yaml


class ConfigError(Exception):
    """Invalid config or a rule target that does not exist (CLI exit 2)."""


TOP_KEYS = {"docs", "exclude", "rules"}
RULE_KEYS = {"id", "when", "update", "run", "note"}
WHEN_KEYS = {"paths", "added", "diff_regex"}


@dataclass
class Rule:
    id: str
    update: list
    paths: list = field(default_factory=list)
    added: list = field(default_factory=list)
    diff_regex: str = None
    run: str = None
    note: str = None


@dataclass
class Config:
    docs: list
    exclude: list
    rules: list


def _strlist(val, where):
    if val is None:
        return []
    if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
        raise ConfigError(f"{where}: expected a list of strings")
    return val


def load_config(path, repo):
    try:
        data = yaml.safe_load(Path(path).read_text()) or {}
    except (OSError, yaml.YAMLError) as e:
        raise ConfigError(f"cannot read {path}: {e}")
    if not isinstance(data, dict):
        raise ConfigError("config must be a mapping")
    bad = set(data) - TOP_KEYS
    if bad:
        raise ConfigError(f"unknown top-level key(s): {sorted(bad)}")
    rules, seen = [], set()
    for i, raw in enumerate(data.get("rules") or []):
        if not isinstance(raw, dict):
            raise ConfigError(f"rules[{i}]: expected a mapping")
        bad = set(raw) - RULE_KEYS
        if bad:
            raise ConfigError(f"rules[{i}]: unknown key(s) {sorted(bad)}")
        rid = raw.get("id")
        if not isinstance(rid, str) or not rid:
            raise ConfigError(f"rules[{i}]: missing id")
        if rid in seen:
            raise ConfigError(f"duplicate rule id {rid}")
        seen.add(rid)
        when = raw.get("when") or {}
        bad = set(when) - WHEN_KEYS
        if bad:
            raise ConfigError(f"rule {rid}: unknown when key(s) {sorted(bad)}")
        rx = when.get("diff_regex")
        if rx is not None:
            try:
                re.compile(rx)
            except re.error as e:
                raise ConfigError(f"rule {rid}: bad diff_regex: {e}")
        if not when:
            raise ConfigError(f"rule {rid}: empty `when`")
        update = _strlist(raw.get("update"), f"rule {rid}.update")
        for t in update:
            if not (Path(repo) / t).exists():
                raise ConfigError(f"rule {rid}: target does not exist: {t}")
        rules.append(Rule(
            id=rid, update=update,
            paths=_strlist(when.get("paths"), f"rule {rid}.when.paths"),
            added=_strlist(when.get("added"), f"rule {rid}.when.added"),
            diff_regex=rx, run=raw.get("run"), note=raw.get("note")))
    return Config(docs=_strlist(data.get("docs"), "docs"),
                  exclude=_strlist(data.get("exclude"), "exclude"), rules=rules)


@dataclass
class Candidate:
    rule_id: str
    evidence: list
    targets: list
    run: str = None
    note: str = None


def glob_match(path, pattern):
    return PurePosixPath(path).full_match(pattern)


def any_glob(path, patterns):
    return any(glob_match(path, p) for p in patterns)


def evaluate_rules(config, files, lines):
    """files: {path: status}; lines: {path: FileDiff}. Returns [Candidate]."""
    out = []
    for rule in config.rules:
        evidence = []
        if rule.paths:
            hit = sorted(p for p in files if any_glob(p, rule.paths))
            if not hit:
                continue
            evidence += [f"changed {p}" for p in hit]
        if rule.added:
            hit = sorted(p for p, s in files.items()
                         if s == "A" and any_glob(p, rule.added))
            if not hit:
                continue
            evidence += [f"added {p}" for p in hit]
        if rule.diff_regex:
            rx = re.compile(rule.diff_regex)
            hits = []
            for p, fd in sorted(lines.items()):
                if rule.paths and not any_glob(p, rule.paths):
                    continue
                for no, text in fd.added:
                    if rx.search(text):
                        hits.append(f"{p}:{no} +{text.strip()[:100]}")
                for text in fd.removed:
                    if rx.search(text):
                        hits.append(f"{p} -{text.strip()[:100]}")
            if not hits:
                continue
            evidence += hits[:5]
        stale = [t for t in rule.update if t not in files]
        if rule.update and not stale:
            continue
        out.append(Candidate(rule.id, evidence, stale, rule.run, rule.note))
    return out
