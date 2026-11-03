"""knack gate — GATES.md 완료 게이트를 확인·실행·재검증한다.

unlazy(https://github.com/Leonxlnx/unlazy, MIT)의 게이트 형식 중 단일 기능·버그 작업에 필요한 부분만 구현했다.
승인 기록·stop 훅·병렬 분배는 없다. 실행될 명령은 설계 게이트에서 사용자가 승인한다.
"""
import datetime
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

GATE_RE = re.compile(r"^- \[([ xX])\] ([A-Za-z0-9][A-Za-z0-9._:-]*): (.+?)\s*$")
ATTR_RE = re.compile(r"^([ \t]*)(CHECK|EXPECT|CWD|EVIDENCE):[ \t]?(.*)$")
ABANDON_RE = re.compile(r"^ABANDON:[ \t]*(\S+)[ \t]+(.+?)\s*$")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
FIXED_OUTPUT_RE = re.compile(r"^\s*(?:(?:echo|printf)\b[^|;&<>`$]*|true|:)\s*$")
FAILURE_WORDS_RE = re.compile(r"\b(?:fail(?:ed|ure)?|error|exception)\b", re.I)
OUTPUT_LIMIT = 1024 * 1024
FAILED_DETAIL = ("exit=", "expect=", "timeout=", "output=", "cwd=", "shell=")


class Gate:
    def __init__(self, gid, title, checked, line):
        self.id, self.title, self.checked, self.line = gid, title, checked, line
        self.attrs, self.attr_lines = {}, {}

    @property
    def runnable(self):
        return "CHECK" in self.attrs

    @property
    def evidence(self):
        return self.attrs.get("EVIDENCE", "").strip()

    def digest(self):
        raw = "\0".join(self.attrs.get(k, "") for k in ("CHECK", "EXPECT", "CWD"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def state(self):
        """met · unmet · failed · stale(증거 이후 게이트 정의가 바뀜)"""
        if not self.runnable:
            return "met" if self.checked and self.evidence not in ("", "pending") else "unmet"
        tokens = self.evidence.split()
        if not tokens or tokens[0] != "auto-v1":
            return "unmet"
        if f"def={self.digest()}" not in tokens:
            return "stale"
        if self.checked and "result=pass" in tokens:
            return "met"
        return "failed" if "result=fail" in tokens else "unmet"


def matcher(expect):
    m = re.fullmatch(r"/(.+)/([imsx]*)", expect)
    if not m:
        return lambda out: expect in out
    flags = 0
    for f in m.group(2):
        flags |= {"i": re.I, "m": re.M, "s": re.S, "x": re.X}[f]
    rx = re.compile(m.group(1), flags)
    return lambda out: rx.search(out) is not None


def parse(text):
    lines = text.splitlines(keepends=True)
    gates, abandons, abandon_lines, errors = [], {}, {}, []
    cur, fence = None, None
    for i, raw in enumerate(lines):
        line, n = raw.rstrip("\n"), i + 1
        if fence:
            if re.match(rf"^ {{0,3}}{re.escape(fence[0])}{{{len(fence)},}}\s*$", line):
                fence = None
            continue
        m = FENCE_RE.match(line)
        if m:
            fence, cur = m.group(1), None
            continue
        m = GATE_RE.match(line)
        if m:
            cur = Gate(m.group(2), m.group(3), m.group(1) != " ", i)
            if any(g.id == cur.id for g in gates):
                errors.append(f"{n}행: 게이트 id 중복 — {cur.id}")
            gates.append(cur)
            continue
        m = ABANDON_RE.match(line)
        if m:
            abandons[m.group(1)], abandon_lines[m.group(1)] = m.group(2), n
            cur = None
            continue
        if line.startswith("ABANDON:"):
            errors.append(f"{n}행: ABANDON: <id> <이유와 인계 대상> 형식으로 씁니다")
            continue
        if re.match(r"^[ \t]+ABANDON:", line):
            errors.append(f"{n}행: ABANDON: 은 들여쓰지 않고 맨 앞 열에 씁니다")
            continue
        m = ATTR_RE.match(line)
        if m:
            indent, key, val = m.groups()
            if not indent:
                errors.append(f"{n}행: {key}: 는 게이트 아래에 들여써서 씁니다")
            elif cur is None:
                errors.append(f"{n}행: 게이트 밖의 {key}:")
            elif key in cur.attrs:
                errors.append(f"{n}행: {cur.id} 의 {key}: 가 두 번 있습니다")
            else:
                cur.attrs[key], cur.attr_lines[key] = val.strip(), i
            continue
        if line.strip() and not line[:1].isspace():
            cur = None

    for g in gates:
        n = g.line + 1
        if ("CHECK" in g.attrs) != ("EXPECT" in g.attrs):
            errors.append(f"{n}행: {g.id} — CHECK: 와 EXPECT: 는 둘 다 쓰거나(자동) 둘 다 뺍니다(수동)")
            continue
        if not g.runnable:
            if "CWD" in g.attrs:
                errors.append(f"{n}행: {g.id} — 수동 게이트에는 CWD: 를 쓰지 않습니다")
            continue
        if not g.attrs["CHECK"] or not g.attrs["EXPECT"]:
            errors.append(f"{n}행: {g.id} — CHECK: 와 EXPECT: 는 비워 둘 수 없습니다")
            continue
        cwd = g.attrs.get("CWD", "")
        if cwd and (os.path.isabs(cwd) or ".." in Path(cwd).parts):
            errors.append(f"{n}행: {g.id} — CWD: 는 레포 루트 기준 상대 경로만 씁니다")
        try:
            matcher(g.attrs["EXPECT"])
        except re.error as e:
            errors.append(f"{n}행: {g.id} — EXPECT 정규식 오류: {e}")
    known = {g.id for g in gates}
    for gid, n in abandon_lines.items():
        if gid not in known:
            errors.append(f"{n}행: ABANDON 대상 {gid} 가 없습니다")
    if not gates:
        errors.append("게이트가 없습니다 — '- [ ] G1: <결과>' 형식으로 씁니다")
    return lines, gates, abandons, errors


def find_root(path):
    try:
        p = subprocess.run(["git", "-C", str(path.resolve().parent), "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True)
        if p.returncode == 0:
            return Path(p.stdout.strip())
    except OSError:
        pass
    return Path.cwd()


def run_gate(gate, root, timeout):
    cwd = root / gate.attrs["CWD"] if gate.attrs.get("CWD") else root
    if not cwd.is_dir():
        return False, "cwd=missing", ""
    shell = os.environ.get("KNACK_GATE_SHELL", "/bin/sh")
    try:
        p = subprocess.run([shell, "-c", gate.attrs["CHECK"]], cwd=cwd, stdin=subprocess.DEVNULL,
                           capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"timeout={timeout}s", ""
    except OSError as e:
        return False, "shell=error", str(e)
    if len(p.stdout) + len(p.stderr) > OUTPUT_LIMIT:
        return False, f"exit={p.returncode} output=over-1MiB", ""
    out, err = p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    combined = out + ("\n" if out and err else "") + err
    matched = matcher(gate.attrs["EXPECT"])(combined)
    return p.returncode == 0 and matched, f"exit={p.returncode} expect={'matched' if matched else 'missing'}", combined


def evidence_line(gate, ok, detail, output):
    now = datetime.datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
    out = hashlib.sha256(output.encode("utf-8")).hexdigest()[:12]
    return f"auto-v1 def={gate.digest()} result={'pass' if ok else 'fail'} {detail} out={out} at={now}"


def apply(lines, gate, ok, evidence):
    lines[gate.line] = re.sub(r"^- \[[ xX]\]", "- [x]" if ok else "- [ ]", lines[gate.line], count=1)
    if "EVIDENCE" in gate.attr_lines:
        i = gate.attr_lines["EVIDENCE"]
        indent = re.match(r"[ \t]*", lines[i]).group(0)
        lines[i] = f"{indent}EVIDENCE: {evidence}\n"
        return
    last = max(gate.attr_lines.values())
    indent = re.match(r"[ \t]*", lines[last]).group(0)
    if not lines[last].endswith("\n"):
        lines[last] += "\n"
    lines.insert(last + 1, f"{indent}EVIDENCE: {evidence}\n")


def lint(gates):
    warns = []
    for g in gates:
        if not g.runnable:
            continue
        if FIXED_OUTPUT_RE.match(g.attrs["CHECK"]):
            warns.append(f"{g.id}: CHECK 가 코드와 상관없이 같은 출력을 냅니다 — 동작을 검증하지 않는 게이트")
        if FAILURE_WORDS_RE.search(g.attrs["EXPECT"]):
            warns.append(f"{g.id}: EXPECT 에 실패 문구가 있습니다 — 실패 출력에도 맞지 않는지 확인")
    manual = sum(not g.runnable for g in gates)
    if gates and manual * 2 > len(gates):
        warns.append(f"수동 게이트가 {manual}/{len(gates)}개 — 명령으로 판정할 수 있는 결과인지 다시 확인")
    return warns


def report(path, gates, abandons):
    auto = sum(g.runnable for g in gates)
    print(f"GATES {path} — {len(gates)}개 (자동 {auto} · 수동 {len(gates) - auto})")
    unmet = 0
    for g in gates:
        kind = "자동" if g.runnable else "수동"
        if g.id in abandons:
            print(f"  ⊘ {g.id} [{kind}] {g.title} — 포기: {abandons[g.id]}")
            continue
        st = g.state()
        if st == "met":
            print(f"  ✓ {g.id} [{kind}] {g.title}")
            continue
        unmet += 1
        if not g.runnable:
            why = "체크와 EVIDENCE(확인한 사실 한 줄) 필요"
        elif st == "stale":
            why = "게이트 정의가 바뀜 — 다시 실행 필요"
        elif st == "failed":
            why = "실패 (" + " ".join(t for t in g.evidence.split() if t.startswith(FAILED_DETAIL)) + ")"
        else:
            why = "증거 없음"
        print(f"  ✗ {g.id} [{kind}] {g.title} — {why}")
    for w in lint(gates):
        print(f"  ! {w}")
    parts = []
    if unmet:
        parts.append(f"UNMET {unmet}")
    if abandons:
        parts.append(f"HANDOFF REQUIRED (포기 {len(abandons)}) — 완료가 아니라 인계로 보고")
    print("결과: " + (" · ".join(parts) if parts else "ALL MET"))
    return 1 if parts else 0


def cmd_gate(a):
    path = Path(a.file)
    if not path.is_file():
        print(f"파일 없음: {path}", file=sys.stderr)
        sys.exit(2)
    lines, gates, abandons, errors = parse(path.read_text(encoding="utf-8"))
    if errors:
        print(f"GATES 형식 오류 — {path}")
        for e in errors:
            print(f"  ✗ {e}")
        print("형식: knack show ref high-risk-gates --section 2")
        sys.exit(2)
    if a.action != "status":
        root = find_root(path)
        results = []
        for g in gates:
            if g.id in abandons or not g.runnable:
                continue
            if a.action == "run" and g.state() == "met":
                continue
            print(f"▶ {g.id}: {g.attrs['CHECK']}", flush=True)
            ok, detail, output = run_gate(g, root, a.timeout)
            if not ok:
                for t in output.rstrip().splitlines()[-15:]:
                    print(f"    │ {t}")
            results.append((g, ok, evidence_line(g, ok, detail, output)))
        for g, ok, ev in sorted(results, key=lambda r: r[0].line, reverse=True):
            apply(lines, g, ok, ev)
        if results:
            path.write_text("".join(lines), encoding="utf-8")
            lines, gates, abandons, errors = parse(path.read_text(encoding="utf-8"))
    sys.exit(report(path, gates, abandons))
