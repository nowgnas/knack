#!/usr/bin/env python3
"""knack 조회·관리 도구. bin/knack 가 호출한다 (python3 표준 라이브러리만 사용).

에이전트가 하네스 파일을 통째로 읽지 않도록 짧은 출력을 기본으로 한다.
list → show --toc → show --section 순서로 필요한 부분만 조회하게 하는 것이 목적이다.
"""
import argparse
import copy
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

import usage as U

KNACK = Path(__file__).resolve().parent.parent
HOME = Path.home()
CODEX_HOME = Path(os.environ.get("CODEX_HOME") or HOME / ".codex")
CLAUDE = HOME / ".claude"

SKILL_DIRS = {"claude": CLAUDE / "skills", "codex": HOME / ".agents" / "skills"}
AGENT_DIR = CLAUDE / "agents"
RULE_FILES = {"claude": CLAUDE / "CLAUDE.md", "codex": CODEX_HOME / "AGENTS.md"}
HOOK_FILES = {"claude": CLAUDE / "settings.json", "codex": CODEX_HOME / "hooks.json"}
EXTERNAL_SKILL_DIRS = [CLAUDE / "skills", HOME / ".agents" / "skills", CODEX_HOME / "skills"]
# 데스크톱 앱(Cowork) 데이터 폴더. macOS 경로로 확인했고 Linux·Windows 는 같은 구조라고 가정한다.
DESKTOP_DIRS = [HOME / "Library" / "Application Support" / "Claude", HOME / ".config" / "Claude"] + \
    ([Path(os.environ["APPDATA"]) / "Claude"] if os.environ.get("APPDATA") else [])

TYPES = ("skills", "rules", "agents", "hooks", "plugins", "mcp")
HOOK_EVENTS = ("PreToolUse", "PostToolUse", "PermissionRequest", "UserPromptSubmit",
               "SessionStart", "Stop", "SubagentStart", "SubagentStop", "PreCompact", "PostCompact", "Notification")
HOOK_MARK = "--knack-hook"
# 개명(harness → knack) 전 표식·마커. 이미 설치된 머신에서 구 항목을 걷어내려고만 쓴다.
# 쓰는 곳: managed_name(구 훅 인식), OLD_BLOCKS(구 지시 블록 제거), old_paths(구 경로 정리).
OLD_HOOK_MARK = "--harness-hook"
BLOCK_START, BLOCK_END = "<!-- knack:start", "<!-- knack:end -->"
TOML_START, TOML_END = "# knack:start", "# knack:end"
OLD_BLOCKS = (("<!-- harness:start", "<!-- harness:end -->"), ("# harness:start", "# harness:end"))
AGENTS_SUPPORTED = ("claude", "codex")

MODELS = KNACK / "models.json"
TIER_RANK = {"fast": 0, "standard": 1, "deep": 2}
CLAUDE_MODELS = {"opus", "sonnet", "haiku", "inherit", "opusplan", "opus[1m]", "sonnet[1m]"}
EFFORTS = ("low", "medium", "high", "xhigh", "max", "ultra")
CODEX_CONFIG = CODEX_HOME / "config.toml"
CODEX_ROLE_DIR = CODEX_HOME / "knack" / "agents"
OLD_CODEX_ROLE_DIR = CODEX_HOME / "harness" / "agents"  # 개명 전 역할 폴더
OLD_CLI_LINK = HOME / ".local" / "bin" / "harness"      # 개명 전 CLI 링크
GEN_MARK = "<!-- knack:generated"
OLD_GEN_MARK = "<!-- harness:generated"  # 개명 전 생성물 표식 (우리 파일로 인식해 교체하려고만 쓴다)

# 스킬 작성 기준 (Astra 가이드: 짧고 의도가 드러나는 description, 목차형 본문)
DESC_MAX, BODY_MAX = 160, 70
BROAD_TRIGGERS = ("구현해줘", "개발해줘", "에러 나", "이상하게 동작해", "원인 찾아줘", "프로젝트 구조 설명")
NAME_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
GIT_URL = re.compile(r"^(https?|ssh|git|file)://|^git@|\.git$")


# ── 공통 ─────────────────────────────────────
def pretty(p):
    s, h = str(p), str(HOME)
    return "~" + s[len(h):] if s == h or s.startswith(h + "/") else s


def rel(p):
    return str(Path(p).relative_to(KNACK))


def fail(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def read_md(path):
    """(frontmatter dict, 본문)"""
    text = Path(path).read_text(encoding="utf-8")
    meta = {}
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            for line in text[4:end].splitlines():
                m = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
                if m:
                    meta[m.group(1)] = m.group(2).strip()
            text = text[end + 4:].lstrip("\n")
    return meta, text


def summary(desc, width=60):
    first = re.split(r"(?<=[.!?])\s", (desc or "").strip(), maxsplit=1)[0].rstrip(".")
    return first if len(first) <= width else first[: width - 1] + "…"


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def linked(link, target):
    return link.is_symlink() and os.path.realpath(link) == os.path.realpath(target)


def in_knack(p):
    return os.path.realpath(p).startswith(str(KNACK) + os.sep)


def mark(v):
    return "-" if v is None else ("✓" if v else "✗")


def backup(path, backup_dir):
    """설정 파일을 실행당 한 번만 백업한다 (같은 실행에서 여러 번 써도 원본이 남도록)."""
    path = Path(path)
    if not backup_dir or not (path.exists() or path.is_symlink()):
        return
    s = str(path)
    dst = Path(backup_dir + (s[len(str(HOME)):] if s.startswith(str(HOME)) else s))
    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)


# ── 하네스 항목 ───────────────────────────────
def knack_skills():
    out = []
    for d in sorted((KNACK / "skills").iterdir()):
        if (d / "SKILL.md").is_file():
            meta, _ = read_md(d / "SKILL.md")
            external = any((d / f).is_file() for f in (".knack-source", ".harness-source"))
            out.append({"name": d.name, "meta": meta, "desc": meta.get("description", ""),
                        "path": d / "SKILL.md", "external": external})
    return out


def knack_rules():
    out = []
    for f in sorted((KNACK / "rules").glob("*.md")):
        meta, body = read_md(f)
        out.append({"name": meta.get("name", f.stem), "meta": meta, "desc": meta.get("description", ""),
                    "load": meta.get("load", "always"), "when": meta.get("when", ""), "path": f, "body": body})
    return out


def knack_agents():
    out = []
    for f in sorted((KNACK / "agents").glob("*.md")):
        meta, _ = read_md(f)
        out.append({"name": meta.get("name", f.stem), "meta": meta, "desc": meta.get("description", ""), "path": f})
    return out


def knack_hooks():
    out = []
    root = KNACK / "hooks"
    for d in sorted(root.iterdir()) if root.is_dir() else []:
        f = d / "hook.json"
        if f.is_file():
            spec = json.loads(f.read_text(encoding="utf-8"))
            spec.update(name=spec.get("name", d.name), path=f, dir=d)
            out.append(spec)
    return out


# ── 설치 상태 ─────────────────────────────────
def block_text(path):
    """(knack 블록 내용 | None, 블록 밖 내용)"""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return None, ""
    pat = re.escape(BLOCK_START) + r"[^\n]*\n(.*?)\n?" + re.escape(BLOCK_END)
    m = re.search(pat, text, re.S)
    return (m.group(1) if m else None), re.sub(pat, "", text, flags=re.S)


def skill_installed(name):
    return {a: linked(d / name, KNACK / "skills" / name) for a, d in SKILL_DIRS.items()}


def rule_installed(rule):
    if rule["load"] != "always":
        return {"claude": None, "codex": None}
    claude_block, _ = block_text(RULE_FILES["claude"])
    codex_block, _ = block_text(RULE_FILES["codex"])
    first = next((l for l in rule["body"].splitlines() if l.strip()), "")
    return {
        "claude": bool(claude_block and re.search(r"^@.*/rules/" + re.escape(rule["path"].name) + r"$", claude_block, re.M)),
        "codex": bool(codex_block and first and first in codex_block),
    }


def hook_groups(data):
    for event, groups in ((data or {}).get("hooks") or {}).items():
        for g in groups or []:
            if isinstance(g, dict):
                yield event, g


def managed_name(group):
    for h in group.get("hooks") or []:
        m = re.search(r"(?:" + re.escape(HOOK_MARK) + "|" + re.escape(OLD_HOOK_MARK) + r")\s+(\S+)",
                      str(h.get("command", "")))
        if m:
            return m.group(1)
    return None


def installed_agents():
    """지시 파일에 하네스 블록이 있는 에이전트. 설치하지 않은 에이전트를 갱신 대상에서 뺀다."""
    out = []
    for agent, f in RULE_FILES.items():
        try:
            if BLOCK_START in f.read_text(encoding="utf-8"):
                out.append(agent)
        except OSError:
            pass
    return out


def hook_installed(hook):
    res = {}
    for agent in ("claude", "codex"):
        if agent not in hook.get("targets", {}) or not hook.get("enabled", True):
            res[agent] = None
        else:
            res[agent] = any(managed_name(g) == hook["name"] for _, g in hook_groups(load_json(HOOK_FILES[agent])))
    return res


# ── 외부 항목 (조회 전용) ──────────────────────
def plugin_skills(root):
    d = root / "skills"
    return sorted(s.name for s in d.iterdir() if (s / "SKILL.md").is_file()) if d.is_dir() else []


def plugins():
    data = load_json(CLAUDE / "plugins" / "installed_plugins.json") or {}
    enabled = (load_json(CLAUDE / "settings.json") or {}).get("enabledPlugins") or {}
    out = []
    for pid, installs in (data.get("plugins") or {}).items():
        inst = installs[0] if isinstance(installs, list) and installs else (installs if isinstance(installs, dict) else {})
        skills = plugin_skills(Path(inst["installPath"])) if inst.get("installPath") else []
        out.append({"id": pid, "short": pid.split("@")[0], "version": inst.get("version", ""),
                    "enabled": bool(enabled.get(pid)), "skills": skills})
    return out


def desktop_plugins():
    """데스크톱 앱(Cowork)이 계정별로 내려받은 플러그인. Claude Code 의 installed_plugins.json 에는 기록되지 않는다.
    rpm/ 은 마켓플레이스에서 설치한 것, skills-plugin/ 은 앱이 기본 제공하는 스킬 묶음이다."""
    out, seen = [], set()

    def add(pid, version, origin, root):
        if pid not in seen:
            seen.add(pid)
            out.append({"id": pid, "short": pid.split("@")[0], "version": version, "origin": origin,
                        "skills": plugin_skills(root)})

    for base in DESKTOP_DIRS:
        sessions = base / "local-agent-mode-sessions"
        if not sessions.is_dir():
            continue
        for manifest in sorted(sessions.glob("*/*/rpm/manifest.json")):
            for p in (load_json(manifest) or {}).get("plugins") or []:
                root = manifest.parent / p.get("id", "")
                meta = load_json(root / ".claude-plugin" / "plugin.json") or {}
                name = p.get("name") or meta.get("name") or p.get("id", "?")
                add(f'{name}@{p.get("marketplaceName", "?")}', meta.get("version", ""),
                    f'{p.get("installedBy", "?")} 설치', root)
        for meta_file in sorted(sessions.glob("skills-plugin/*/*/.claude-plugin/plugin.json")):
            meta = load_json(meta_file) or {}
            add(meta.get("name") or "skills-plugin", meta.get("version", ""), "앱 기본 제공", meta_file.parent.parent)
    return out


def external_skills():
    found = {}

    def add(name, where):
        if where not in found.setdefault(name, []):
            found[name].append(where)

    for base in EXTERNAL_SKILL_DIRS:
        if not base.is_dir():
            continue
        for e in sorted(base.iterdir()):
            if e.name.startswith(".") or in_knack(e):
                continue
            via = f" → {pretty(os.path.realpath(e))}" if e.is_symlink() else ""
            if (e / "SKILL.md").is_file():
                add(e.name, pretty(base) + via)
            elif e.is_dir():  # 스킬 묶음 (예: superpowers)
                for c in sorted(e.iterdir()):
                    if (c / "SKILL.md").is_file():
                        add(f"{e.name}/{c.name}", pretty(e) + via)
    for p in plugins():
        for s in p["skills"]:
            add(f'{p["short"]}:{s}', f'plugin {p["id"]}')
    for p in desktop_plugins():
        for s in p["skills"]:
            add(f'{p["short"]}:{s}', f'desktop {p["id"]}')
    return found


def external_agents():
    return [e.name for e in sorted(AGENT_DIR.glob("*.md")) if not in_knack(e)] if AGENT_DIR.is_dir() else []


def mask(s):
    return re.sub(r"(?i)(token|key|secret|password)=[^&\s\"']+", r"\1=***", s)


def external_hooks():
    out = []
    for agent, f in HOOK_FILES.items():
        for event, g in hook_groups(load_json(f)):
            if managed_name(g):
                continue
            for h in g.get("hooks") or []:
                what = mask(str(h.get("command") or h.get("url") or ""))
                out.append({"agent": agent, "event": event, "matcher": g.get("matcher", ""), "type": h.get("type", ""),
                            "what": what if len(what) <= 70 else what[:69] + "…"})
    return out


def external_rules():
    out = []
    for agent, f in RULE_FILES.items():
        _, outside = block_text(f)
        lines = [l for l in outside.splitlines() if l.strip()]
        if lines:
            imports = [l for l in lines if l.startswith("@")]
            head = next((l for l in lines if l.startswith("#")), lines[0])
            detail = "import " + ", ".join(imports) if imports else head[:50]
            out.append({"agent": agent, "file": pretty(f), "detail": f"블록 밖 {len(lines)}줄 · {detail}"})
    toml = CODEX_HOME / "config.toml"
    if toml.is_file():
        m = re.search(r'^model_instructions_file\s*=\s*"([^"]+)"', toml.read_text(encoding="utf-8"), re.M)
        if m:
            out.append({"agent": "codex", "file": pretty(toml), "detail": f"model_instructions_file = {pretty(m.group(1))}"})
    return out


def mcp_servers():
    found = {}
    for src in (HOME / ".claude.json", CLAUDE / "mcp.json"):
        for name in (load_json(src) or {}).get("mcpServers") or {}:
            found.setdefault(name, []).append(f"claude {pretty(src)}")
    toml = CODEX_HOME / "config.toml"
    if toml.is_file():
        names = re.findall(r'^\[mcp_servers\.(?:"([^"]+)"|([A-Za-z0-9_-]+))', toml.read_text(encoding="utf-8"), re.M)
        for quoted, bare in names:
            where = f"codex {pretty(toml)}"
            if where not in found.setdefault(quoted or bare, []):
                found[quoted or bare].append(where)
    return found


# ── list ─────────────────────────────────────
def norm_type(t):
    t = t.lower()
    if t == "all" or t in TYPES:
        return t
    if t + "s" in TYPES:
        return t + "s"
    raise argparse.ArgumentTypeError(f"종류: all, {', '.join(TYPES)}")


def cmd_list(a):
    types = TYPES if a.type == "all" else (a.type,)
    ext = a.all or a.type in ("plugins", "mcp")
    out = {}
    if "skills" in types:
        out["skills"] = [{"name": s["name"], "summary": summary(s["desc"]), "installed": skill_installed(s["name"])}
                         for s in knack_skills()]
        if ext:
            out["external_skills"] = external_skills()
    if "rules" in types:
        out["rules"] = [{"name": r["name"], "load": r["load"], "summary": summary(r["desc"]), "installed": rule_installed(r)}
                        for r in knack_rules()]
        if ext:
            out["external_rules"] = external_rules()
    if "agents" in types:
        out["agents"] = [{"name": g["name"], "summary": summary(g["desc"]), "installed": agent_installed(g)}
                         for g in knack_agents()]
        if ext:
            out["external_agents"] = external_agents()
    if "hooks" in types:
        out["hooks"] = [{"name": h["name"], "enabled": h.get("enabled", True),
                         "events": sorted({t["event"] for t in h.get("targets", {}).values()}),
                         "summary": summary(h.get("description", "")), "installed": hook_installed(h)}
                        for h in knack_hooks()]
        if ext:
            out["external_hooks"] = external_hooks()
    if "plugins" in types and ext:
        out["plugins"] = plugins()
        out["desktop_plugins"] = desktop_plugins()
    if "mcp" in types and ext:
        out["mcp"] = mcp_servers()
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print_list(out)


def print_list(out):
    print(f"하네스 {pretty(KNACK)} · 설치 상태 [claude codex]")
    for key, label in (("skills", "스킬"), ("rules", "룰"), ("agents", "서브에이전트"), ("hooks", "훅")):
        if key not in out:
            continue
        print(f"\n[{label} {len(out[key])}]")
        for it in out[key]:
            extra = ""
            if key == "rules":
                extra = f"({it['load']}) "
            elif key == "hooks":
                extra = f"({'on' if it['enabled'] else 'off'} {','.join(it['events'])}) "
            inst = it["installed"]
            print(f"  [{mark(inst['claude'])} {mark(inst['codex'])}] {it['name']:<24} {extra}{it['summary']}")
    names = {s["name"] for s in out.get("skills", [])}
    if "external_skills" in out:
        es = out["external_skills"]
        print(f"\n[외부 스킬 {len(es)} — 하네스 관리 아님]")
        for name, locs in sorted(es.items()):
            dup = "  ⚠ 하네스에도 같은 이름" if name in names else ""
            print(f"  {name:<32} {', '.join(locs)}{dup}")
    if "external_rules" in out:
        print(f"\n[외부 룰 {len(out['external_rules'])}]")
        for r in out["external_rules"]:
            print(f"  {r['agent']:<6} {r['file']}  {r['detail']}")
    if "external_agents" in out:
        print(f"\n[외부 서브에이전트 {len(out['external_agents'])}]")
        for n in out["external_agents"]:
            print(f"  {n}")
    if "external_hooks" in out:
        print(f"\n[외부 훅 {len(out['external_hooks'])}]")
        for h in out["external_hooks"]:
            matcher = f"[{h['matcher']}] " if h["matcher"] else ""
            print(f"  {h['agent']:<6} {h['event']:<18} {matcher}{h['type']}: {h['what']}")
    if "plugins" in out:
        print(f"\n[Claude 플러그인 {len(out['plugins'])}]")
        for p in out["plugins"]:
            print(f"  {p['id']:<44} {'on ' if p['enabled'] else 'off'} {p['version']:<8} 스킬 {len(p['skills'])}")
    if "desktop_plugins" in out:
        print(f"\n[데스크톱 앱 플러그인 {len(out['desktop_plugins'])} — 앱에서 관리]")
        for p in out["desktop_plugins"]:
            print(f"  {p['id']:<44} {p['origin']:<8} {p['version']:<8} 스킬 {len(p['skills'])}")
    if "mcp" in out:
        print(f"\n[MCP 서버 {len(out['mcp'])}]")
        for name, locs in sorted(out["mcp"].items()):
            print(f"  {name:<24} {', '.join(locs)}")
    print("\n상세: knack show <skill|rule|agent|hook|ref> <이름> [--toc | --section <번호|제목>]")


# ── show ─────────────────────────────────────
def resolve(kind, name):
    kind = {"skills": "skill", "rules": "rule", "agents": "agent", "hooks": "hook",
            "refs": "ref", "templates": "template"}.get(kind, kind)
    if kind == "usage":
        return KNACK / "skills" / "knack-help" / "USAGE.md"
    if not name:
        fail(f"이름이 필요합니다: knack show {kind} <이름>", 2)
    path = None
    if kind == "skill":
        path = KNACK / "skills" / name / "SKILL.md"
    elif kind == "rule":
        path = next((r["path"] for r in knack_rules() if name in (r["name"], r["path"].stem)), None)
    elif kind == "agent":
        path = next((g["path"] for g in knack_agents() if name in (g["name"], g["path"].stem)), None)
    elif kind == "hook":
        path = KNACK / "hooks" / name / "hook.json"
    elif kind in ("ref", "template"):
        sub = "references" if kind == "ref" else "templates"
        skill, _, base = name.rpartition("/")
        cands = sorted((KNACK / "skills").glob(f"{skill or '*'}/{sub}/**/{base}.md"))
        if len(cands) > 1:
            fail("같은 이름이 여러 개입니다. <스킬>/<이름> 으로 지정하세요:\n" +
                 "\n".join(f"  {c.parts[-len(c.relative_to(KNACK / 'skills').parts)]}/{base}  ({rel(c)})" for c in cands), 2)
        path = cands[0] if cands else None
    else:
        fail(f"알 수 없는 종류: {kind} (skill, rule, agent, hook, ref, template, usage)", 2)
    if not path or not Path(path).is_file():
        fail(f"{kind} '{name}' 을(를) 찾을 수 없습니다. 목록: knack list", 1)
    return Path(path)


def headings(lines):
    fence = None
    for i, line in enumerate(lines):
        m = re.match(r"^\s*(`{3,}|~{3,})", line)
        if m:
            tok = m.group(1)
            if fence is None:
                fence = tok
            elif tok[0] == fence[0] and len(tok) >= len(fence):
                fence = None
            continue
        if fence is None:
            h = re.match(r"^(#{1,6})\s+(.*?)\s*#*$", line)
            if h:
                yield i, len(h.group(1)), h.group(2)


def section_bounds(lines):
    hs = list(headings(lines))
    for idx, (i, lvl, text) in enumerate(hs):
        end = next((j for j, l2, _ in hs[idx + 1:] if l2 <= lvl), len(lines))
        yield i, end, lvl, text


def match_heading(text, key):
    if re.fullmatch(r"\d+(\.\d+)*", key):
        return re.match(re.escape(key) + r"(\.|\s|$)", text) is not None
    return key.lower() in text.lower()


def cmd_show(a):
    path = resolve(a.kind, a.name)
    if a.path:
        print(path)
        return
    text = path.read_text(encoding="utf-8")
    if a.raw or path.suffix != ".md":
        print(text.rstrip())
        if path.name == "hook.json":
            print("\n# 파일: " + ", ".join(sorted(p.name for p in path.parent.iterdir() if p.is_file())))
        return
    meta, body = read_md(path)
    lines = body.splitlines()
    if a.toc:
        print(f"# {rel(path)} — {len(lines)}줄" + (f" · {summary(meta.get('description', ''))}" if meta.get("description") else ""))
        for i, end, lvl, htext in section_bounds(lines):
            print(f"{'  ' * (lvl - 1)}{htext}  ({end - i}줄)")
        return
    if a.section:
        chunks = []
        for key in a.section:
            hit = next(((i, end) for i, end, _, htext in section_bounds(lines) if match_heading(htext, key)), None)
            if not hit:
                avail = ", ".join(h for _, _, lvl, h in section_bounds(lines) if lvl <= 2)
                fail(f"섹션 '{key}' 없음. 목차: knack show {a.kind} {a.name or ''} --toc\n  {avail}", 1)
            chunks.append("\n".join(lines[hit[0]:hit[1]]).rstrip())
        print("\n\n".join(chunks))
        return
    print(body.rstrip())


# ── search ───────────────────────────────────
def cmd_search(a):
    pat = re.compile(a.pattern if a.regex else re.escape(a.pattern), re.I)
    hits, per_file = [], {}
    for root in ("rules", "skills", "agents", "hooks"):
        base = KNACK / root
        for f in sorted(base.rglob("*")) if base.is_dir() else []:
            if not f.is_file() or f.suffix not in (".md", ".json", ".sh", ".py"):
                continue
            for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if pat.search(line):
                    hits.append(f"{rel(f)}:{n}: {line.strip()[:120]}")
                    per_file[rel(f)] = per_file.get(rel(f), 0) + 1
    if not hits:
        print("결과 없음")
        sys.exit(1)
    if a.files:
        for f, n in per_file.items():
            print(f"{n:>3} {f}")
        return
    for h in hits[: a.limit]:
        print(h)
    if len(hits) > a.limit:
        print(f"… 외 {len(hits) - a.limit}건 (--limit 로 조정, -l 로 파일별 개수)")


# ── doctor ───────────────────────────────────
def cmd_doctor(_a):
    counts = {"bad": 0, "warn": 0}

    def ok(m):
        print(f"  ✓ {m}")

    def warn(m):
        counts["warn"] += 1
        print(f"  ⚠ {m}")

    def bad(m):
        counts["bad"] += 1
        print(f"  ✗ {m}")

    skills, rules, agents, hooks = knack_skills(), knack_rules(), knack_agents(), knack_hooks()
    print("[하네스 구조]")
    before = counts["bad"]
    for s in skills:
        if s["meta"].get("name") != s["name"]:
            bad(f"skills/{s['name']}: frontmatter name 불일치 ({s['meta'].get('name')})")
        if not s["desc"]:
            bad(f"skills/{s['name']}: description 없음")
    for r in rules:
        if r["load"] not in ("always", "on-demand"):
            bad(f"{rel(r['path'])}: load 는 always|on-demand ({r['load']})")
        if not r["desc"]:
            bad(f"{rel(r['path'])}: description 없음")
    for g in agents:
        if not g["desc"]:
            bad(f"{rel(g['path'])}: description 없음")
    for h in hooks:
        script = h["dir"] / h.get("command", "")
        if not script.is_file() or not os.access(script, os.X_OK):
            bad(f"hooks/{h['name']}: 실행 파일 없음 또는 실행 권한 없음 ({h.get('command')})")
        for agent, t in h.get("targets", {}).items():
            if agent not in HOOK_FILES or t.get("event") not in HOOK_EVENTS:
                bad(f"hooks/{h['name']}: 잘못된 대상 {agent}/{t.get('event')}")
    if counts["bad"] == before:
        ok(f"스킬 {len(skills)} · 룰 {len(rules)} · 서브에이전트 {len(agents)} · 훅 {len(hooks)} 형식 이상 없음")

    print("[스킬 작성 기준]")
    before = counts["warn"]
    for s in skills:
        desc, body_lines = s["desc"], len(read_md(s["path"])[1].splitlines())
        if len(desc) > DESC_MAX:
            warn(f"{s['name']}: description {len(desc)}자 > {DESC_MAX} — 트리거를 좁히고 줄이기")
        broad = [b for b in BROAD_TRIGGERS if b in desc]
        if broad:
            warn(f"{s['name']}: 넓은 트리거 {', '.join(broad)} — 의도가 드러나는 문구로 바꾸기")
        # 외부에서 가져온 스킬은 본문을 우리가 고치면 업스트림과 어긋난다. description 은
        # 매 세션 로드되니 그대로 보고, 호출될 때만 읽는 본문은 원본에 맡긴다.
        if body_lines > BODY_MAX and not s["external"]:
            warn(f"{s['name']}: 본문 {body_lines}줄 > {BODY_MAX} — 세부 절차를 references/ 로 분리")
    if counts["warn"] == before:
        ok(f"스킬 작성 기준 충족 (description ≤ {DESC_MAX}자, 본문 ≤ {BODY_MAX}줄, 넓은 트리거 없음)")

    print("[모델 라우팅]")
    problems = models_problems()
    for p in problems:
        bad(p)
    cfg = load_models(safe=True) if not problems else None
    warns = model_warnings(cfg) if cfg else []
    for w in warns:
        warn(w)
    if cfg and not warns:
        delegated = sum(len(v) for v in task_agents().values())
        ok(f"models.json: 작업 {len(cfg['tasks'])}개 · 서브에이전트 위임 {delegated}개 · 모델 이름 확인됨")
    if cfg and CODEX_CONFIG.is_file() and knack_agents():
        if not re.search(r"^\[features\][^\[]*?^multi_agent\s*=\s*true", CODEX_CONFIG.read_text(encoding="utf-8"), re.M | re.S):
            warn("Codex 서브에이전트 역할을 쓰려면 ~/.codex/config.toml 에 [features] multi_agent = true 필요")

    print("[중복·충돌]")
    ext = external_skills()
    dups = sorted({s["name"] for s in skills} & set(ext))
    for d in dups:
        warn(f"스킬 '{d}' 가 하네스와 외부({', '.join(ext[d])})에 모두 있음 → 설치 시 SKIP (교체: knack install --force)")
    if not dups:
        ok(f"하네스 스킬과 같은 이름의 외부 스킬 없음 (외부 스킬 {len(ext)}개)")

    print("[페르소나]")
    P = __import__("persona")
    if not P.CORE.is_file():
        ok("페르소나 미설정 (선택. knack persona init)")
    else:
        issues = P.problems()
        for line in issues:
            warn(f"persona: {line}")
        if not issues:
            rows = sum(1 + max(0, len(v) - 1) for _, v in P.load())
            state = "" if P.enabled() else " · 주입 꺼짐"
            ok(f"persona core {rows}줄 (권장 {P.MAX_LINES}줄 이내) · 상세 {len(P.detail_topics())}개{state}")

    print("[설치 상태]")
    missing = [f"skill:{s['name']}" for s in skills if not all(skill_installed(s["name"]).values())]
    missing += [f"agent:{g['name']}" for g in agents if False in agent_installed(g).values()]
    missing += [f"rule:{r['name']}" for r in rules if False in rule_installed(r).values()]
    missing += [f"hook:{h['name']}" for h in hooks if False in hook_installed(h).values()]
    if missing:
        warn(f"미설치·갱신 필요 {len(missing)}건: {', '.join(missing[:8])} → knack install")
    else:
        ok("모든 항목 설치됨")
    broken = [pretty(p) for d in (*SKILL_DIRS.values(), AGENT_DIR, HOME / ".local" / "bin") if d.is_dir()
              for p in d.iterdir() if p.is_symlink() and os.readlink(p).startswith(str(KNACK)) and not p.exists()]
    for b in broken:
        warn(f"끊어진 링크 {b} → knack install 이 정리")

    print("[환경]")
    ok(f"python3 {sys.version.split()[0]}")
    if shutil.which("knack"):
        ok("knack 명령이 PATH에 있음")
    else:
        warn("knack 명령이 PATH에 없음 → ~/.local/bin 을 PATH에 추가")
    if any("codex" in h.get("targets", {}) and h.get("enabled", True) for h in hooks):
        toml = CODEX_HOME / "config.toml"
        text = toml.read_text(encoding="utf-8") if toml.is_file() else ""
        if re.search(r"^\[features\][^\[]*?^hooks\s*=\s*true", text, re.M | re.S):
            ok("Codex hooks 기능 켜짐 (새 훅은 Codex에서 처음 실행할 때 신뢰 확인)")
        else:
            warn("Codex 훅을 쓰려면 ~/.codex/config.toml 에 [features] hooks = true 필요")
    print(f"\n결과: 문제 {counts['bad']} · 경고 {counts['warn']}")
    sys.exit(1 if counts["bad"] else 0)


# ── add / adopt / new / hook ─────────────────
def set_frontmatter_name(f, name):
    text = f.read_text(encoding="utf-8")
    if re.search(r"^name:", text, re.M):
        text = re.sub(r"^name:.*$", f"name: {name}", text, count=1, flags=re.M)
    else:
        text = text.replace("---\n", f"---\nname: {name}\n", 1)
    f.write_text(text, encoding="utf-8")


def write_source(dest, info):
    info["added"] = date.today().isoformat()
    (dest / ".knack-source").write_text(json.dumps(info, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def cmd_add(a):
    tmp, commit = None, None
    try:
        if GIT_URL.search(a.source):
            tmp = tempfile.mkdtemp(prefix="knack-add-")
            r = subprocess.run(["git", "clone", "--depth", "1", "--quiet", a.source, tmp], capture_output=True, text=True)
            if r.returncode:
                fail("git clone 실패: " + r.stderr.strip())
            base = Path(tmp)
            commit = subprocess.run(["git", "-C", tmp, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        else:
            base = Path(a.source).expanduser().resolve()
            if base.is_file() and base.name == "SKILL.md":
                base = base.parent
        root = base / a.subdir if a.subdir else base
        if not root.exists():
            fail(f"경로 없음: {root}")
        cands = [root] if (root / "SKILL.md").is_file() else \
            sorted({p.parent for p in root.rglob("SKILL.md") if ".git" not in p.parts})
        if a.name and len(cands) > 1:
            cands = [c for c in cands if a.name in (c.name, read_md(c / "SKILL.md")[0].get("name"))] or cands
        if not cands:
            fail("SKILL.md 를 찾지 못했습니다.")
        if len(cands) > 1:
            fail("스킬이 여러 개입니다. --subdir 로 하나를 지정하세요:\n" + "\n".join(
                f"  --subdir {c.relative_to(base)}  ({read_md(c / 'SKILL.md')[0].get('name', c.name)})" for c in cands), 2)
        src = cands[0]
        meta, _ = read_md(src / "SKILL.md")
        name = a.name or meta.get("name") or src.name
        if not NAME_RE.fullmatch(name):
            fail(f"스킬 이름 형식 오류: '{name}' (소문자·숫자·-). --name 으로 지정하세요.", 2)
        if not meta.get("description"):
            fail("SKILL.md frontmatter 에 description 이 없습니다.", 2)
        dest = KNACK / "skills" / name
        if dest.exists() and not a.replace:
            fail(f"하네스에 이미 '{name}' 스킬이 있습니다. 원본으로 갱신하려면 --replace", 2)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest, symlinks=True, ignore=shutil.ignore_patterns(".git"))
        if meta.get("name") != name:
            set_frontmatter_name(dest / "SKILL.md", name)
        write_source(dest, {"source": a.source, "subdir": str(src.relative_to(base)) if src != base else "", "commit": commit})

        files = [p for p in dest.rglob("*") if p.is_file() and p.name not in (".knack-source", ".harness-source")]
        runnable = [rel(p) for p in files if os.access(p, os.X_OK) or p.suffix in (".sh", ".py", ".js", ".ts", ".rb")]
        print(f"추가: skills/{name} ({len(files)}개 파일)")
        if runnable:
            print("  ⚠ 실행 가능한 파일 — 내용을 검토하세요: " + ", ".join(runnable[:10]))
        ext = external_skills().get(name)
        if ext:
            print(f"  ⚠ 외부에 같은 이름: {', '.join(ext)} → 설치 시 SKIP. 교체: knack install --force")
        if a.install:
            subprocess.run([str(KNACK / "install.sh"), "--global"], check=False)
        else:
            print("다음: knack install --dry-run → knack install → 하네스 레포 커밋")
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def cmd_adopt(a):
    if a.src:
        locs = [Path(a.src).expanduser()]
    else:
        locs = [b / a.name for b in EXTERNAL_SKILL_DIRS if (b / a.name / "SKILL.md").is_file() and not in_knack(b / a.name)]
    if not locs:
        fail(f"외부 스킬 '{a.name}' 을(를) 찾지 못했습니다. (knack list skills --all)")
    src = locs[0]
    if src.is_symlink():
        fail(f"{pretty(src)} 는 {pretty(os.path.realpath(src))} 로의 링크입니다. "
             f"원본 위치에서 관리되므로 knack add skill {pretty(os.path.realpath(src))} 로 복사하세요.", 2)
    dest = KNACK / "skills" / a.name
    if dest.exists():
        fail(f"하네스에 이미 '{a.name}' 스킬이 있습니다.", 2)
    if not read_md(src / "SKILL.md")[0].get("description"):
        fail("SKILL.md frontmatter 에 description 이 없습니다.", 2)
    shutil.move(str(src), str(dest))
    write_source(dest, {"adopted_from": pretty(src)})
    print(f"이동: {pretty(src)} → skills/{a.name}")
    if len(locs) > 1:
        print("  ⚠ 같은 이름의 복사본이 남아 있습니다(삭제하지 않음): " + ", ".join(pretty(p) for p in locs[1:]))
    print("다음: knack install (원래 위치에 링크 생성) → 하네스 레포 커밋")


SKILL_TEMPLATE = """---
name: {name}
description: <무엇을 하는 스킬인지 한 문장>. "<트리거 요청 예시>", "<예시 2>" 같은 요청에 사용.
---

# {title}

경로는 모두 이 SKILL.md가 있는 디렉터리 기준 상대 경로다.

## 1. <단계>
-

## 산출물
-
"""

RULE_TEMPLATE = """---
name: {name}
description: <이 룰이 다루는 것 한 줄>
load: {load}
when: <on-demand 일 때 읽어야 하는 시점, 예: 커밋 전>
---
# {title}
-
"""

HOOK_TEMPLATE = """#!/usr/bin/env python3
\"\"\"{name} 훅. stdin 으로 이벤트 JSON 을 받는다 (tool_name, tool_input, cwd …).\"\"\"
import json
import sys


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return
    # 차단하려면:
    # print(json.dumps({{"hookSpecificOutput": {{"hookEventName": "PreToolUse",
    #     "permissionDecision": "deny", "permissionDecisionReason": "이유"}}}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
"""


def cmd_new(a):
    if not NAME_RE.fullmatch(a.name):
        fail(f"이름 형식 오류: '{a.name}' (소문자·숫자·-)", 2)
    title = a.name.replace("-", " ").title()
    if a.kind == "skill":
        d = KNACK / "skills" / a.name
        if d.exists():
            fail(f"이미 있음: {rel(d)}", 2)
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(SKILL_TEMPLATE.format(name=a.name, title=title), encoding="utf-8")
        created, nxt = [d / "SKILL.md"], "SKILL.md 작성 → skills/knack-help/USAGE.md 에 안내 추가 → knack test → knack install"
    elif a.kind == "rule":
        if any(r["name"] == a.name for r in knack_rules()):
            fail(f"이미 있는 룰: {a.name}", 2)
        nums = [int(m.group(1)) for f in (KNACK / "rules").glob("*.md") if (m := re.match(r"(\d+)-", f.name))]
        f = KNACK / "rules" / f"{(max(nums) if nums else 0) + 10:02d}-{a.name}.md"
        load = "always" if a.always else "on-demand"
        f.write_text(RULE_TEMPLATE.format(name=a.name, title=title, load=load), encoding="utf-8")
        created = [f]
        nxt = "내용 작성 → knack install" + (" (always 룰은 매 세션 컨텍스트에 로드되므로 짧게)" if a.always else "")
    else:
        d = KNACK / "hooks" / a.name
        if d.exists():
            fail(f"이미 있음: {rel(d)}", 2)
        d.mkdir(parents=True)
        spec = {"name": a.name, "description": "<훅이 하는 일 한 줄>", "enabled": False, "command": "hook.py",
                "targets": {"claude": {"event": "PreToolUse", "matcher": "Bash", "timeout": 10},
                            "codex": {"event": "PreToolUse", "timeout": 10}}}
        (d / "hook.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        script = d / "hook.py"
        script.write_text(HOOK_TEMPLATE.format(name=a.name), encoding="utf-8")
        script.chmod(0o755)
        created = [d / "hook.json", script]
        nxt = f"hook.py 작성 → hook.json targets 확인 → knack hook enable {a.name} → knack install"
    for c in created:
        print(f"생성: {rel(c)}")
    print(f"다음: {nxt}")


def cmd_hook(a):
    f = KNACK / "hooks" / a.name / "hook.json"
    if not f.is_file():
        fail(f"훅 없음: {a.name} (knack list hooks)")
    spec = json.loads(f.read_text(encoding="utf-8"))
    spec["enabled"] = a.action == "enable"
    f.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{a.name}: {'on' if spec['enabled'] else 'off'} → 적용: knack install")


# ── hooks-sync (install.sh 전용) ──────────────
def cmd_hooks_sync(a):
    f = Path(a.file)
    data = load_json(f) if f.exists() else {}
    if data is None or not isinstance(data, dict):
        print(f"  ERROR   {pretty(f)} JSON 을 읽을 수 없어 훅을 건드리지 않습니다")
        print("@@ changes=0")
        return
    wanted = {}
    if a.action != "uninstall":
        for h in knack_hooks():
            t = h.get("targets", {}).get(a.agent)
            if not t or not h.get("enabled", True):
                continue
            group = {"matcher": t["matcher"]} if t.get("matcher") else {}
            group["hooks"] = [{"type": "command", "timeout": t.get("timeout", 10),
                               "command": f'"{a.knack}/hooks/{h["name"]}/{h["command"]}" {HOOK_MARK} {h["name"]}'}]
            wanted[h["name"]] = (t["event"], group)
    current = {}
    for event, g in hook_groups(data):
        name = managed_name(g)
        if name:
            current[name] = (event, g)

    new = copy.deepcopy(data)
    hooks = new.get("hooks") or {}
    for ev in list(hooks):
        kept = [g for g in hooks[ev] if not (isinstance(g, dict) and managed_name(g))]
        if kept or not hooks[ev]:
            hooks[ev] = kept
        else:
            del hooks[ev]
    for name, (ev, g) in wanted.items():
        hooks.setdefault(ev, []).append(g)
    if hooks or "hooks" in data:
        new["hooks"] = hooks

    changes = 0
    for name, (ev, g) in wanted.items():
        same = current.get(name) == (ev, g)
        if a.action == "status":
            state = "OK" if same else ("STALE" if name in current else "MISSING")
        else:
            state = "OK" if same else ("UPDATE" if name in current else "HOOK")
            changes += 0 if same else 1
        print(f"  {state:<7} {pretty(f)} {ev} ← {name}")
    for name, (ev, _) in current.items():
        if name not in wanted:
            print(f"  {'EXTRA' if a.action == 'status' else 'UNHOOK':<7} {pretty(f)} {ev} ← {name}")
            changes += 0 if a.action == "status" else 1
    if a.action != "status" and new != data and not a.dry_run:
        backup(f, a.backup_dir)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(new, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if a.agent == "codex" and a.action == "install" and changes:
        print("  참고: Codex는 새 훅을 처음 실행할 때 신뢰 확인을 요청합니다.")
    print(f"@@ changes={changes}")


# ── 모델 라우팅 (models.json) ──────────────────
def load_models(safe=False):
    try:
        return json.loads(MODELS.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        if safe:
            return None
        fail(f"models.json 을 읽을 수 없습니다: {e}")


def resolve_model(cfg, task, agent):
    """(model, effort). task 는 tasks 의 키 또는 main(세션 기본)."""
    if task == "main":
        spec = (cfg.get("main") or {}).get(agent) or {}
    else:
        t = cfg["tasks"].get(task)
        if t is None:
            fail(f"알 수 없는 작업 유형: {task} (목록: knack model)", 2)
        spec = dict(cfg["tiers"][agent][t["tier"]])
        spec.update(t.get(agent) or {})
    return spec.get("model"), spec.get("effort")


def model_label(model, effort):
    return f"{model}/{effort}" if effort else (model or "-")


def env_var(name):
    """KNACK_<name> 을 읽고, 없으면 개명 전 HARNESS_<name> 도 받아 준다."""
    return os.environ.get(f"KNACK_{name}") or os.environ.get(f"HARNESS_{name}")


def agent_cmd(agent, override=None):
    """에이전트 실행 명령. override > KNACK_<AGENT>_CMD (예: 'headroom wrap claude --') > KNACK_<AGENT>_BIN > 이름.
    subprocess 로 실행하므로 셸 함수·별칭은 적용되지 않는다."""
    spec = override or env_var(f"{agent.upper()}_CMD")
    if spec:
        return shlex.split(spec)
    return [env_var(f"{agent.upper()}_BIN") or agent]


def model_flags(agent, model, effort):
    if agent == "claude":
        return ["--model", model]
    return ["-m", model] + (["-c", f"model_reasoning_effort={effort}"] if effort else [])


def keyword_hit(keyword, text):
    if re.fullmatch(r"[A-Za-z0-9 _-]+", keyword):
        return re.search(r"\b" + re.escape(keyword) + r"\b", text, re.I) is not None
    return keyword.lower() in text.lower()


def classify(cfg, text):
    """키워드 매칭 수가 많은 작업. 동점이면 높은 티어(품질 우선)."""
    best = None
    for i, (name, t) in enumerate(cfg["tasks"].items()):
        hits = sum(1 for k in t.get("keywords", []) if keyword_hit(k, text))
        if hits:
            key = (hits, TIER_RANK.get(t["tier"], 0), -i)
            if best is None or key > best[0]:
                best = (key, name)
    return best[1] if best else None


def task_agents():
    out = {}
    for g in knack_agents():
        if g["meta"].get("task"):
            out.setdefault(g["meta"]["task"], []).append(g["name"])
    return out


def models_problems():
    cfg = load_models(safe=True)
    if cfg is None:
        return ["models.json 없음 또는 JSON 오류"]
    out, tiers, tasks = [], cfg.get("tiers") or {}, cfg.get("tasks") or {}
    for agent in AGENTS_SUPPORTED:
        if agent not in tiers:
            out.append(f"models.json: tiers.{agent} 없음")
            continue
        if not ((cfg.get("main") or {}).get(agent) or {}).get("model"):
            out.append(f"models.json: main.{agent}.model 없음")
        for name, t in tasks.items():
            if t.get("tier") not in tiers[agent]:
                out.append(f"models.json: tasks.{name} 의 티어 '{t.get('tier')}' 가 tiers.{agent} 에 없음")
    for g in knack_agents():
        task = g["meta"].get("task")
        if task and task not in tasks:
            out.append(f"{rel(g['path'])}: task '{task}' 가 models.json 에 없음")
    return out


def codex_known_models():
    data = load_json(CODEX_HOME / "models_cache.json")
    models = data.get("models") if isinstance(data, dict) else data
    out = {}
    for m in models or []:
        if isinstance(m, dict) and (m.get("slug") or m.get("id")):
            levels = m.get("supported_reasoning_levels") or []
            out[m.get("slug") or m.get("id")] = [e.get("effort") if isinstance(e, dict) else e for e in levels]
    return out


def model_warnings(cfg):
    known, warns = codex_known_models(), set()
    for agent in AGENTS_SUPPORTED:
        for task in ["main", *cfg["tasks"]]:
            model, effort = resolve_model(cfg, task, agent)
            if not model:
                warns.add(f"{agent}/{task}: 모델이 비어 있음")
            elif agent == "claude" and model not in CLAUDE_MODELS and not model.startswith("claude-"):
                warns.add(f"claude/{task}: 알 수 없는 모델 '{model}'")
            elif agent == "codex" and known and model not in known:
                warns.add(f"codex/{task}: models_cache 에 없는 모델 '{model}'")
            elif agent == "codex" and effort and known.get(model) and effort not in known[model]:
                warns.add(f"codex/{task}: '{model}' 이 지원하지 않는 effort '{effort}'")
    return sorted(warns)


def tier_rank_of(cfg, agent, model):
    base = (model or "").replace("[1m]", "")
    for tier, spec in (cfg["tiers"].get(agent) or {}).items():
        if (spec.get("model") or "").replace("[1m]", "") == base:
            return TIER_RANK.get(tier, -1)
    return -1


def models_index(cfg, agent):
    """지시 파일 블록에 넣는 작업 유형별 모델 색인 (몇 줄로 짧게)."""
    delegates, main = task_agents(), resolve_model(cfg, "main", agent)
    main_rank = tier_rank_of(cfg, agent, main[0])
    lines, in_session, upgrade = ["작업 유형별 모델 (`knack model` 로 조회·변경):"], [], []
    for name, t in cfg["tasks"].items():
        label = model_label(*resolve_model(cfg, name, agent))
        if name in delegates:
            who = ", ".join(f"`{d}`" for d in delegates[name])
            how = "서브에이전트에 위임" if agent == "claude" else "역할로 위임 (spawn_agent)"
            lines.append(f"- {t['desc']} → {who} {how} · {label}")
        else:
            in_session.append(t["desc"])
            if main_rank >= 0 and TIER_RANK.get(t["tier"], 0) > main_rank:
                upgrade.append(f"{name}({label})")
    if in_session:
        lines.append(f"- {', '.join(in_session)} → 이 세션 · {model_label(*main)}")
    if upgrade:
        lines.append(f"- 이 세션보다 높은 모델을 권장하는 작업: {', '.join(upgrade)}. 규모가 크면 `knack run <작업>` 으로 새 세션을 제안한다.")
    return "\n".join(lines)


def render_claude_agent(g, cfg):
    raw = g["path"].read_text(encoding="utf-8")
    front = raw[4:raw.find("\n---", 4)].splitlines()
    _, body = read_md(g["path"])
    task = g["meta"].get("task")
    model = resolve_model(cfg, task, "claude")[0] if task else g["meta"].get("model")
    lines = [l for l in front if not l.startswith(("task:", "sandbox:", "model:"))]
    if model:
        lines.append(f"model: {model}")
    note = f"{GEN_MARK} from {rel(g['path'])}" + (f" · task: {task} → models.json" if task else "") + " · 직접 수정 금지 -->"
    return "---\n" + "\n".join(lines) + "\n---\n" + note + "\n\n" + body.rstrip() + "\n"


def render_codex_role(g, cfg):
    task = g["meta"].get("task")
    model, effort = resolve_model(cfg, task, "codex") if task else (None, None)
    _, body = read_md(g["path"])
    out = [f"# knack: {rel(g['path'])} 에서 생성 · 직접 수정 금지"]
    if model:
        out.append(f"model = {json.dumps(model)}")
    if effort:
        out.append(f"model_reasoning_effort = {json.dumps(effort)}")
    if g["meta"].get("sandbox"):
        out.append(f"sandbox_mode = {json.dumps(g['meta']['sandbox'])}")
    out.append(f"developer_instructions = {json.dumps(body.strip(), ensure_ascii=False)}")
    return "\n".join(out) + "\n"


def codex_roles_block():
    lines = ["# 하네스 서브에이전트 역할 (spawn_agent 의 agent_type). 이 블록 뒤에 최상위 키를 추가하지 마세요."]
    for g in knack_agents():
        lines += ["", f"[agents.{g['name']}]", f"description = {json.dumps(g['desc'], ensure_ascii=False)}",
                  f"config_file = {json.dumps(str(CODEX_ROLE_DIR / (g['name'] + '.toml')))}"]
    return "\n".join(lines)


def set_block(text, start, end, content):
    """마커 블록을 교체하거나 파일 끝에 붙인다. content 가 None 이면 제거.

    개명 전 마커(harness:start)로 쓰인 블록도 함께 걷어낸다.
    """
    def strip(src, s, e):
        pat = re.compile(r"\n*^" + re.escape(s) + r".*?^" + re.escape(e) + r"[^\n]*\n?", re.S | re.M)
        return pat.sub("\n", src)

    base = strip(text, start, end)
    for old_start, old_end in OLD_BLOCKS:
        base = strip(base, old_start, old_end)
    base = base.rstrip("\n")
    if content is None:
        return base + "\n" if base else ""
    block = f"{start} (managed by {pretty(KNACK)} — 직접 수정 금지)\n{content}\n{end}"
    return f"{base}\n\n{block}\n" if base else block + "\n"


def toml_top(text, key):
    for line in text.split("\n"):
        if re.match(r"\s*\[", line):
            break
        m = re.match(rf'\s*{re.escape(key)}\s*=\s*"([^"]*)"', line)
        if m:
            return m.group(1)
    return None


def toml_set_top(text, key, value):
    lines = text.split("\n")
    first_table = next((i for i, l in enumerate(lines) if re.match(r"\s*\[", l)), len(lines))
    new = f"{key} = {json.dumps(value)}"
    for i in range(first_table):
        if re.match(rf"\s*{re.escape(key)}\s*=", lines[i]):
            lines[i] = new
            return "\n".join(lines)
    # 최상위 키는 테이블·주석 앞에 와야 한다. 빈 파일에 블록만 있던 경우 set_block 과 같은
    # 간격(키 뒤 빈 줄)으로 맞춘다. 그러지 않으면 다음 실행이 같은 내용을 계속 STALE 로 본다.
    sep = [] if not lines or not lines[0].strip() or re.match(r'\s*[\w."\'-]+\s*=', lines[0]) else [""]
    return "\n".join([new] + sep + lines)


def agent_installed(g):
    cfg = load_models(safe=True)
    if cfg is None or models_problems():
        return {"claude": None, "codex": None}
    p = AGENT_DIR / g["path"].name
    claude = p.is_file() and not p.is_symlink() and p.read_text(encoding="utf-8") == render_claude_agent(g, cfg)
    role = CODEX_ROLE_DIR / f"{g['name']}.toml"
    toml = CODEX_CONFIG.read_text(encoding="utf-8") if CODEX_CONFIG.is_file() else ""
    codex = role.is_file() and role.read_text(encoding="utf-8") == render_codex_role(g, cfg) \
        and f"[agents.{g['name']}]" in toml
    return {"claude": claude, "codex": codex}


def cmd_model(a):
    cfg = load_models()
    action = a.action or "list"
    if action == "list":
        delegates = task_agents()
        print("작업 유형별 모델 (models.json)       claude         | codex")
        print(f"  {'main':<10} {'세션기본':<8} {model_label(*resolve_model(cfg, 'main', 'claude')):<14} | "
              f"{model_label(*resolve_model(cfg, 'main', 'codex')):<22}")
        for name, t in cfg["tasks"].items():
            claude = model_label(*resolve_model(cfg, name, "claude"))
            codex = model_label(*resolve_model(cfg, name, "codex"))
            via = ", ".join(delegates.get(name, [])) or "세션"
            print(f"  {name:<10} {t['tier']:<8} {claude:<14} | {codex:<22} → {via} · {t.get('desc', '')}")
        print("\n분류: knack model which \"<요청>\" · 조회: knack model get <작업> --agent claude|codex"
              " · 변경: knack model set <작업|main|tier:이름> <티어|모델> [--agent] [--effort]")
    elif action == "get":
        model, effort = resolve_model(cfg, a.task, a.agent)
        if a.format == "json":
            print(json.dumps({"task": a.task, "agent": a.agent, "model": model, "effort": effort}))
        elif a.format == "flags":
            print(" ".join(model_flags(a.agent, model, effort)))
        else:
            print(model)
    elif action == "which":
        task = classify(cfg, " ".join(a.text)) or "main"
        print(f"작업 유형: {task}" + (" (키워드 없음 → 세션 기본 모델)" if task == "main" else f" · {cfg['tasks'][task]['desc']}"))
        for agent in AGENTS_SUPPORTED:
            print(f"  {agent:<6} {model_label(*resolve_model(cfg, task, agent))}")
        if task_agents().get(task):
            print(f"  위임: {', '.join(task_agents()[task])}")
    else:
        cmd_model_set(cfg, a)


def cmd_model_set(cfg, a):
    target, value, tiers = a.target, a.value, cfg["tiers"]

    def spec(agent):
        if value in TIER_RANK and value in tiers.get(agent, {}):
            return dict(tiers[agent][value])
        return {"model": value, **({"effort": a.effort} if a.effort else {})}

    if target.startswith("tier:"):
        if not a.agent:
            fail("티어의 모델을 바꿀 때는 --agent 가 필요합니다.", 2)
        tiers.setdefault(a.agent, {})[target[5:]] = {"model": value, **({"effort": a.effort} if a.effort else {})}
    elif target == "main":
        if not a.agent and value not in TIER_RANK:
            fail("모델 이름으로 지정할 때는 --agent 가 필요합니다.", 2)
        for agent in [a.agent] if a.agent else AGENTS_SUPPORTED:
            cfg.setdefault("main", {})[agent] = spec(agent)
    elif target in cfg["tasks"]:
        t = cfg["tasks"][target]
        if value in TIER_RANK and not a.agent:
            t["tier"] = value
            for agent in AGENTS_SUPPORTED:
                t.pop(agent, None)
        elif a.agent:
            t[a.agent] = spec(a.agent)
        else:
            fail("모델 이름으로 지정할 때는 --agent 가 필요합니다.", 2)
    else:
        fail(f"알 수 없는 대상: {target} (작업 유형, main, tier:<이름>)", 2)
    MODELS.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"변경: {target} ← {value}{f' ({a.effort})' if a.effort else ''}" + (f" [{a.agent}]" if a.agent else ""))
    for w in model_warnings(cfg):
        print(f"  ⚠ {w}")
    print("적용: knack install")


def cmd_run(a):
    cfg = load_models()
    prompt = " ".join(a.prompt).strip()
    task = (classify(cfg, prompt) or "main") if a.task == "auto" else a.task
    agent = a.agent or ("claude" if shutil.which("claude") else "codex")
    model, effort = resolve_model(cfg, task, agent)
    if not model:
        fail(f"{agent}/{task} 모델이 models.json 에 없습니다.")
    if agent == "claude":
        cmd = [*agent_cmd(agent), *model_flags(agent, model, effort), *(["--print"] if a.print else [])]
    else:
        cmd = [*agent_cmd(agent), *(["exec"] if a.print else []), *model_flags(agent, model, effort)]
    if prompt:
        cmd.append(prompt)
    elif a.print:
        fail("--print 에는 프롬프트가 필요합니다.", 2)
    print(f"knack run: {task} → {agent} {model_label(model, effort)}", file=sys.stderr)
    if a.dry_run:
        print(shlex.join(cmd))
        return
    os.execvp(cmd[0], cmd)


def usage_weights():
    merged = {agent: dict(w) for agent, w in U.DEFAULT_WEIGHTS.items()}
    for agent, w in ((load_models(safe=True) or {}).get("usage_weights") or {}).items():
        merged.setdefault(agent, {}).update(w)
    return merged


def cmd_persona_block(_a):
    print(__import__("persona").render_block(), end="")


def cmd_models_index(a):
    cfg = load_models(safe=True)
    if cfg and not models_problems():
        print(models_index(cfg, a.agent))


def cmd_models_sync(a):
    """install.sh 전용: 서브에이전트(모델 포함)와 세션 기본 모델을 에이전트 설정에 반영한다."""
    cfg = load_models()
    status, removing = a.action == "status", a.action == "uninstall"
    counts = {"changes": 0, "skips": 0}

    def say(state, what):
        print(f"  {state:<7} {what}")
        if state in ("SKIP", "ERROR"):
            counts["skips"] += 1
        elif not status and state not in ("OK", "BACKUP"):
            counts["changes"] += 1

    if a.agent == "claude":
        adir = Path(a.agents_dir) if a.agents_dir else AGENT_DIR
        want = {} if removing else {g["path"].name: render_claude_agent(g, cfg) for g in knack_agents()}
        existing = {p.name: p for p in adir.glob("*.md")} if adir.is_dir() else {}

        def owned(p):
            if p.is_symlink():
                return os.readlink(p).startswith(a.knack) or in_knack(p)
            try:
                head = p.read_text(encoding="utf-8")[:4000]
            except OSError:
                return False
            return GEN_MARK in head or OLD_GEN_MARK in head  # 개명 전 생성물도 우리 것

        for name, content in want.items():
            p = adir / name
            present = p.exists() or p.is_symlink()
            model = re.search(r"^model: (.+)$", content, re.M)
            label = f"(model: {model.group(1)})" if model else ""
            if present and not owned(p):
                if status:
                    say("CONFLICT", f"{pretty(p)} (하네스가 아닌 파일)")
                    continue
                if not a.force:
                    say("SKIP", f"{pretty(p)} (기존 파일 존재. --force 로 백업 후 교체)")
                    continue
                say("BACKUP", pretty(p))
                if not a.dry_run:
                    backup(p, a.backup_dir)
            elif present and not p.is_symlink() and p.read_text(encoding="utf-8") == content:
                say("OK", f"{pretty(p)} {label}")
                continue
            if status:
                say("STALE" if present else "MISSING", pretty(p))
                continue
            say("UPDATE" if present else "AGENT", f"{pretty(p)} {label}")
            if not a.dry_run:
                adir.mkdir(parents=True, exist_ok=True)
                if p.is_symlink():
                    p.unlink()
                p.write_text(content, encoding="utf-8")
        for name, p in existing.items():
            if name not in want and owned(p):
                say("EXTRA" if status else "REMOVE", pretty(p))
                if not status and not a.dry_run:
                    p.unlink()

        if not a.no_main and not removing:  # 세션 기본 모델은 사용자 설정이므로 제거 시에도 그대로 둔다
            f = CLAUDE / "settings.json"
            data = load_json(f) if f.exists() else {}
            want_model = resolve_model(cfg, "main", "claude")[0]
            if not isinstance(data, dict):
                say("ERROR", f"{pretty(f)} JSON 을 읽을 수 없어 세션 모델을 건너뜀")
            elif data.get("model") == want_model:
                say("OK", f"{pretty(f)} 세션 모델 {want_model}")
            elif status:
                say("STALE", f"{pretty(f)} 세션 모델 {data.get('model')} (models.json: {want_model})")
            else:
                say("MODEL", f"{pretty(f)} 세션 모델 {data.get('model')} → {want_model}")
                if not a.dry_run:
                    backup(f, a.backup_dir)
                    data["model"] = want_model
                    f.parent.mkdir(parents=True, exist_ok=True)
                    f.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if a.agent == "codex":
        want = {} if removing else {f"{g['name']}.toml": render_codex_role(g, cfg) for g in knack_agents()}
        existing = {p.name: p for p in CODEX_ROLE_DIR.glob("*.toml")} if CODEX_ROLE_DIR.is_dir() else {}
        for name, content in want.items():
            p = CODEX_ROLE_DIR / name
            cur = p.read_text(encoding="utf-8") if p.is_file() else None
            m = re.search(r'^model = "([^"]+)"', content, re.M)
            e = re.search(r'^model_reasoning_effort = "([^"]+)"', content, re.M)
            label = model_label(m.group(1) if m else None, e.group(1) if e else None)
            if cur == content:
                say("OK", f"{pretty(p)} ({label})")
                continue
            if status:
                say("STALE" if cur else "MISSING", pretty(p))
                continue
            say("UPDATE" if cur else "ROLE", f"{pretty(p)} ({label})")
            if not a.dry_run:
                CODEX_ROLE_DIR.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
        for name, p in existing.items():
            if name not in want:
                say("EXTRA" if status else "REMOVE", pretty(p))
                if not status and not a.dry_run:
                    p.unlink()
        # 개명 전 역할 폴더가 남아 있으면 정리한다 (config.toml 은 새 경로를 가리킨다)
        if OLD_CODEX_ROLE_DIR.is_dir() and OLD_CODEX_ROLE_DIR != CODEX_ROLE_DIR:
            say("STALE" if status else "REMOVE", f"{pretty(OLD_CODEX_ROLE_DIR)} (개명 전 역할 폴더)")
            if not status and not a.dry_run:
                shutil.rmtree(OLD_CODEX_ROLE_DIR, ignore_errors=True)

        f = CODEX_CONFIG
        text = f.read_text(encoding="utf-8") if f.is_file() else ""
        has_block = TOML_START in text
        new = text if removing and not has_block else \
            set_block(text, TOML_START, TOML_END, None if removing else codex_roles_block())
        if new != text:
            if status:
                say("STALE" if has_block else "MISSING", f"{pretty(f)} (서브에이전트 역할 블록)")
            else:
                say("UNBLOCK" if removing else "BLOCK", f"{pretty(f)} (서브에이전트 역할 블록)")
        elif not removing:
            say("OK", f"{pretty(f)} (서브에이전트 역할 블록)")
        if not removing and not a.no_main:
            model, effort = resolve_model(cfg, "main", "codex")
            updated = new
            if model:
                updated = toml_set_top(updated, "model", model)
            if effort:
                updated = toml_set_top(updated, "model_reasoning_effort", effort)
            current = model_label(toml_top(new, "model"), toml_top(new, "model_reasoning_effort"))
            if updated == new:
                say("OK", f"{pretty(f)} 세션 모델 {current}")
            elif status:
                say("STALE", f"{pretty(f)} 세션 모델 {current} (models.json: {model_label(model, effort)})")
            else:
                say("MODEL", f"{pretty(f)} 세션 모델 {current} → {model_label(model, effort)}")
            new = updated
        if not status and new != text and not a.dry_run:
            backup(f, a.backup_dir)
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(new, encoding="utf-8")
    print(f"@@ changes={counts['changes']} skips={counts['skips']}")


def main():
    p = argparse.ArgumentParser(prog="knack")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("list", help="하네스·외부 항목과 설치 상태")
    s.add_argument("type", nargs="?", default="all", type=norm_type)
    s.add_argument("--all", action="store_true", help="외부(하네스 관리 아님) 항목 포함")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("show", help="항목 내용 (frontmatter 제외)")
    s.add_argument("kind")
    s.add_argument("name", nargs="?")
    g = s.add_mutually_exclusive_group()
    g.add_argument("--toc", action="store_true", help="목차와 섹션별 줄 수")
    g.add_argument("--section", action="append", help="번호(5, 5.2) 또는 제목 일부. 여러 번 지정 가능")
    g.add_argument("--path", action="store_true", help="파일 경로만")
    g.add_argument("--raw", action="store_true", help="파일 전체 (frontmatter 포함)")

    s = sub.add_parser("search", help="하네스 문서 검색")
    s.add_argument("pattern")
    s.add_argument("-E", "--regex", action="store_true")
    s.add_argument("-l", "--files", action="store_true", help="파일별 매칭 수만")
    s.add_argument("--limit", type=int, default=30)

    sub.add_parser("doctor", help="구조·중복·설치 상태 점검")

    s = sub.add_parser("add", help="외부 스킬을 하네스에 복사")
    s.add_argument("kind", choices=("skill",))
    s.add_argument("source", help="로컬 경로 또는 git URL")
    s.add_argument("--name")
    s.add_argument("--subdir")
    s.add_argument("--replace", action="store_true")
    s.add_argument("--install", action="store_true")

    s = sub.add_parser("adopt", help="에이전트 폴더의 외부 스킬을 하네스로 이동")
    s.add_argument("kind", choices=("skill",))
    s.add_argument("name")
    s.add_argument("--from", dest="src")

    s = sub.add_parser("new", help="스킬·룰·훅 뼈대 생성")
    s.add_argument("kind", choices=("skill", "rule", "hook"))
    s.add_argument("name")
    s.add_argument("--always", action="store_true", help="룰을 매 세션 로드(always)로 생성")

    s = sub.add_parser("hook", help="훅 켜기/끄기")
    s.add_argument("action", choices=("enable", "disable"))
    s.add_argument("name")

    s = sub.add_parser("hooks-sync")
    s.add_argument("--agent", required=True, choices=tuple(HOOK_FILES))
    s.add_argument("--file", required=True)
    s.add_argument("--action", required=True, choices=("install", "uninstall", "status"))
    s.add_argument("--knack", required=True)
    s.add_argument("--backup-dir", default=str(HOME / ".knack-backups" / "manual"))
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--force", action="store_true")

    s = sub.add_parser("model", help="작업 유형별 모델 조회·분류·변경")
    msub = s.add_subparsers(dest="action")
    msub.add_parser("list")
    m = msub.add_parser("get")
    m.add_argument("task")
    m.add_argument("--agent", choices=AGENTS_SUPPORTED, default="claude")
    m.add_argument("--format", choices=("name", "flags", "json"), default="name")
    m = msub.add_parser("which")
    m.add_argument("text", nargs="+")
    m = msub.add_parser("set")
    m.add_argument("target", help="작업 유형, main, tier:<이름>")
    m.add_argument("value", help="티어(deep|standard|fast) 또는 모델 이름")
    m.add_argument("--agent", choices=AGENTS_SUPPORTED)
    m.add_argument("--effort", choices=EFFORTS)

    s = sub.add_parser("run", help="작업 유형에 맞는 모델로 에이전트 실행")
    s.add_argument("task", help="작업 유형 또는 auto (프롬프트 키워드로 분류)")
    s.add_argument("prompt", nargs="*")
    s.add_argument("--agent", choices=AGENTS_SUPPORTED)
    s.add_argument("--print", action="store_true", help="비대화 실행 (claude -p / codex exec)")
    s.add_argument("--dry-run", action="store_true", help="실행할 명령만 출력")

    s = sub.add_parser("models-sync")
    s.add_argument("--agent", required=True, choices=AGENTS_SUPPORTED)
    s.add_argument("--action", required=True, choices=("install", "uninstall", "status"))
    s.add_argument("--knack", required=True)
    s.add_argument("--backup-dir", default=str(HOME / ".knack-backups" / "manual"))
    s.add_argument("--agents-dir")
    s.add_argument("--no-main", action="store_true")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--force", action="store_true")

    s = sub.add_parser("models-index")
    s.add_argument("--agent", required=True, choices=AGENTS_SUPPORTED)

    s = sub.add_parser("usage", help="세션 로그 기반 토큰 사용량")
    s.add_argument("--agent", choices=("all", *AGENTS_SUPPORTED), default="all")
    s.add_argument("--since", default="7d", help="7d, 12h, 2026-09-01")
    g = s.add_mutually_exclusive_group()
    g.add_argument("--cwd", help="이 경로 아래에서 실행된 세션만")
    g.add_argument("--here", action="store_true", help="현재 디렉터리 아래 세션만")
    s.add_argument("--session", help="세션 id (일부)")
    s.add_argument("--by", choices=("session", "model", "day", "skill", "cwd"), default="session")
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--json", action="store_true")

    s = sub.add_parser(
        "bench", help="작업 세트를 조건별로 실행·비교", formatter_class=argparse.RawDescriptionHelpFormatter,
        description="같은 작업 세트를 하네스 미적용(baseline)과 적용 조건으로 실행해 토큰·check 통과율·턴·시간을 비교한다.\n"
                    "baseline 은 전역 설정을 건드리지 않고 하네스만 뺀 HOME 미러로 실행한다.",
        epilog="예:\n  knack bench init                 # ~/.knack-bench/tasks.json 생성 후 repo·tasks 편집\n"
               "  knack bench ab --repeat 2 --dry-run\n  knack bench ab --repeat 2        # baseline → knack → 비교표\n"
               "  knack bench baseline             # baseline 에서 빠지는 항목 확인")
    bsub = s.add_subparsers(dest="action", required=True)
    b = bsub.add_parser("init", help="작업 파일 예시 생성")
    b.add_argument("path", nargs="?", help="기본: ~/.knack-bench/tasks.json")
    bsub.add_parser("baseline", help="하네스만 뺀 HOME 미러를 만들고 제외 항목 출력")

    def bench_run_options(b):
        b.add_argument("tasks", nargs="?", help="작업 파일 (기본: ~/.knack-bench/tasks.json)")
        b.add_argument("--agent", choices=AGENTS_SUPPORTED, help="기본: 작업 파일의 agent, 없으면 claude")
        b.add_argument("--repeat", type=int, default=1, help="작업별 반복 횟수")
        b.add_argument("--only", help="작업 id 쉼표 목록")
        b.add_argument("--keep", action="store_true", help="worktree 남기기")
        b.add_argument("--dry-run", action="store_true", help="실행할 명령만 출력")
        b.add_argument("--model", help="작업 유형 대신 고정 모델")
        b.add_argument("--effort", choices=EFFORTS)
        b.add_argument("--permission-mode", default="acceptEdits", help="Claude 권한 모드")
        b.add_argument("--sandbox", default="workspace-write", help="Codex 샌드박스")
        b.add_argument("--max-turns", type=int)
        b.add_argument("--timeout", type=int, default=1800, help="작업당 에이전트 실행 제한(초)")
        b.add_argument("--check-timeout", type=int, default=900)
        b.add_argument("--agent-args", help="에이전트 CLI 에 넘길 추가 인자 (예: --agent-args='--allowedTools Bash')")
        b.add_argument("--agent-cmd", help="에이전트 실행 명령 (예: --agent-cmd='headroom wrap claude --'). "
                                           "기본: KNACK_CLAUDE_CMD/KNACK_CODEX_CMD 또는 PATH 의 claude/codex")

    b = bsub.add_parser("run", help="한 조건 실행")
    bench_run_options(b)
    b.add_argument("--label", required=True, help="조건 이름 (예: baseline, knack)")
    b.add_argument("--baseline", action="store_true", help="하네스만 뺀 HOME 미러로 실행 (전역 설정은 그대로)")
    b = bsub.add_parser("ab", help="baseline(하네스 제외)과 knack(현재 설정)를 연달아 실행하고 비교")
    bench_run_options(b)
    b.add_argument("--prefix", help="결과 label 접두어 (기본: ab-<날짜시각>)")
    b = bsub.add_parser("compare", help="두 조건 비교")
    b.add_argument("a")
    b.add_argument("b")
    b.add_argument("--json", action="store_true")
    bsub.add_parser("list", help="저장된 조건 목록")

    s = sub.add_parser("persona", help="사용자 페르소나 (지시 블록에 주입되는 사실)",
                       epilog="예:\n  knack persona init            # 템플릿 생성 후 채우기\n"
                              "  knack persona set stack 'Spring Boot 3.2; MySQL 8'\n"
                              "  cat me.md | knack persona import -\n"
                              "  knack persona import --detail db schema.md\n"
                              "  knack persona check           # 형식·길이 점검",
                       formatter_class=argparse.RawDescriptionHelpFormatter)
    psub = s.add_subparsers(dest="action")
    x = psub.add_parser("show", help="주입되는 내용 (주제를 주면 상세)")
    x.add_argument("topic", nargs="?")
    x = psub.add_parser("init", help="템플릿으로 core.md 만들기")
    x.add_argument("--force", action="store_true")
    x = psub.add_parser("set", help="항목 하나 수정·추가 (값에 ; 를 쓰면 목록)")
    x.add_argument("key")
    x.add_argument("value")
    x = psub.add_parser("import", help="파일·표준입력으로 통째로 넣기 (스크립트 입력)")
    x.add_argument("file", nargs="?", help="경로 또는 - (표준입력)")
    x.add_argument("--detail", metavar="주제", help="core 대신 detail/<주제>.md 로 저장")
    psub.add_parser("check", help="형식·길이 점검 (문제가 있으면 1로 종료)")
    psub.add_parser("enable", help="주입 켜기")
    psub.add_parser("disable", help="주입 끄기 (bench 비교용)")
    psub.add_parser("path", help="파일 경로")

    sub.add_parser("persona-block")

    s = sub.add_parser("gate", help="GATES.md 완료 게이트 확인·실행·재검증",
                       epilog="예:\n  knack gate status .design/20260914-refund/GATES.md   # 실행 없이 상태·경고\n"
                              "  knack gate run <GATES.md>        # 미충족 자동 게이트만 실행\n"
                              "  knack gate reverify <GATES.md>   # 충족된 것까지 전부 다시 실행\n"
                              "종료 코드: 0 ALL MET · 1 미충족 또는 포기 · 2 형식 오류",
                       formatter_class=argparse.RawDescriptionHelpFormatter)
    s.add_argument("action", choices=("status", "run", "reverify"))
    s.add_argument("file", help="GATES.md 경로")
    s.add_argument("--timeout", type=int, default=600, help="게이트당 제한 시간(초)")

    a, extra = p.parse_known_args()
    extra = [x for x in extra if x != "--"]
    if a.cmd == "run":
        a.prompt = a.prompt + extra
    elif extra:
        p.error("알 수 없는 인자: " + " ".join(extra))
    {"list": cmd_list, "show": cmd_show, "search": cmd_search, "doctor": cmd_doctor, "add": cmd_add,
     "adopt": cmd_adopt, "new": cmd_new, "hook": cmd_hook, "hooks-sync": cmd_hooks_sync,
     "model": cmd_model, "run": cmd_run, "models-sync": cmd_models_sync, "models-index": cmd_models_index,
     "usage": lambda args: U.cmd_usage(args, usage_weights()),
     "bench": lambda args: __import__("bench").cmd_bench(args, sys.modules[__name__]),
     "persona": lambda args: __import__("persona").cmd_persona(args, sys.modules[__name__]),
     "gate": lambda args: __import__("gate").cmd_gate(args),
     "persona-block": lambda args: cmd_persona_block(args)}[a.cmd](a)


if __name__ == "__main__":
    main()
