#!/usr/bin/env python3
"""PreToolUse 훅: 운영 DB 마이그레이션과 운영 환경·프로파일 실행을 막는다 (fail-closed).

대상
- DB 마이그레이션: dotnet ef database update|drop, flyway migrate|clean|repair|undo|baseline,
  liquibase update*|rollback*|dropAll|changelogSync*…, Gradle·Maven 의 flyway·liquibase 태스크,
  docker/podman run 으로 띄운 flyway·liquibase 이미지.
  → 명령에 적힌 대상 DB(--connection, -url=, --url, -D/-P…url=, 인라인 env)가 전부 로컬일 때만 허용한다.
- 운영 환경: ASPNETCORE_ENVIRONMENT·DOTNET_ENVIRONMENT=Production, SPRING_PROFILES_ACTIVE=prod,
  --spring.profiles.active=prod, --environment Production, -Pprod … → 명령 종류와 상관없이 차단.

fail-closed 범위
- 잘못된 JSON, 셸 도구인데 명령이 없거나 형식이 틀린 입력, 파서 예외(위험 키워드가 있을 때),
  대상 미명시·해석 불가 대상, 위험 키워드와 함께 쓴 동적 구문(eval, | sh, $VAR 실행),
  검사할 수 없는 셸 스크립트(256KB 초과, 읽기 실패, 중첩 2단계 초과)는 차단한다.
- 실행 명령이 아닌 도구(apply_patch, 파일 편집, MCP)는 통과한다.

한계: 셸이 아닌 실행 파일·Makefile·npm script·alias 안쪽, appsettings·flyway.conf 에만 적힌 대상,
ssh 터널로 localhost 가 운영을 가리키는 경우는 보지 못한다. 실수 방지 장치이지 보안 경계가 아니다.
해제: 훅 프로세스 환경의 KNACK_GUARD_PROD=off (명령 안에 적은 값은 무시).
pstack(MIT) 의 아이디어와 무관한 knack 자체 훅이다.
"""
import json
import os
import re
import sys

try:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "_shared"))
    from shellparse import SHELLS, segments, split_heredocs, split_prefix, words  # noqa: E402
except Exception:  # 파서를 못 읽으면 판단할 수 없다 — 막는다
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                      "permissionDecisionReason": "guard-prod-ops: hooks/_shared/shellparse.py 를 읽지 못해 판단할 수 없습니다. knack doctor 로 설치를 확인하세요."}},
                     ensure_ascii=False))
    sys.exit(0)

SHELL_TOOLS = {"bash", "shell", "exec_command", "local_shell", "unified_exec", "container.exec"}
# 이 단어가 있을 때만 파서 예외·동적 구문을 막는다(없으면 이 훅이 막을 명령이 아니다)
STRONG = re.compile(r"(?i)database\s+(update|drop)|dotnet-ef|flyway|liquibase|_ENVIRONMENT|profiles[._]active"
          r"|run\.profiles|--environment|-P(prod|production|prd|live)\b")
PROD_VARS = {"ASPNETCORE_ENVIRONMENT", "DOTNET_ENVIRONMENT", "SPRING_PROFILES_ACTIVE"}
PROD_VALUES = {"prod", "production", "prd", "live"}
TARGET_VARS = ("FLYWAY_URL", "SPRING_DATASOURCE_URL", "SPRING_FLYWAY_URL", "SPRING_LIQUIBASE_URL",
               "LIQUIBASE_COMMAND_URL", "LIQUIBASE_URL")
# 인자로 문자열을 받아 기록·검색만 하는 명령. 인자에 prod 가 적혀 있어도 실행이 아니다
DATA_CMDS = {"echo", "printf", "grep", "egrep", "fgrep", "rg", "ag", "cat", "less", "head", "tail", "git", "gh",
             "sed", "awk", "jq", "yq", "find", "ls", "wc", "diff", "knack", "apply_patch", "test", "[", "true",
             "false", "read", "export", "unset", "type", "which", "man"}
FLYWAY_RISK = {"migrate", "clean", "repair", "undo", "baseline"}
# Liquibase CLI 명령·Gradle 플러그인 태스크 중 DB 를 바꾸는 것 (소문자, - 제거). *SQL 은 SQL 만 만든다
LIQUIBASE_RISK = {"update", "updatecount", "updatetotag", "updatetodate", "updatetestingrollback", "rollback",
                  "rollbackcount", "rollbacktodate", "rollbackonechangeset", "rollbackoneupdate", "dropall",
                  "changelogsync", "changelogsynctotag", "changelogsynccount", "releaselocks", "tag",
                  "marknextchangesetran", "clearchecksums"}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]", "host.docker.internal", ".", "(local)", "0.0.0.0"}
MAX_SCRIPT = 256 * 1024
MAX_DEPTH = 2

GUIDE = ("guard-prod-ops: {why}\n"
         "운영·공유 DB 변경과 운영 환경 실행은 에이전트가 하지 않습니다(30-backend-safety). 명령만 사용자에게 제안하세요.\n"
         "- 로컬 DB라면 대상을 명령에 명시: --connection \"Server=localhost,1433;…\" · -url=jdbc:postgresql://localhost:5432/app · "
         "Testcontainers(jdbc:tc:)\n"
         "- 로컬 docker 서비스 호스트는 사용자가 프로젝트 .knack/safe-db-hosts 에 한 줄씩(정확한 이름) 추가\n"
         "- 사용자가 의도한 실행이면 사용자가 직접 실행하거나, 훅 프로세스 환경에 KNACK_GUARD_PROD=off 를 두고 세션을 시작")


class Deny(Exception):
    pass


def deny(why):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": GUIDE.format(why=why)}}, ensure_ascii=False))
    sys.exit(0)


# ── 대상 DB 해석 ─────────────────────────────
def project_root(cwd):
    d = os.path.abspath(cwd or os.getcwd())
    while True:
        if os.path.exists(os.path.join(d, ".git")) or os.path.dirname(d) == d:
            return d
        d = os.path.dirname(d)


def safe_hosts(cwd):
    root, out, d = project_root(cwd), set(), os.path.abspath(cwd or os.getcwd())
    while True:
        f = os.path.join(d, ".knack", "safe-db-hosts")
        try:
            for line in open(f, encoding="utf-8"):
                line = line.split("#", 1)[0].strip().lower()
                if line and "*" not in line and "?" not in line:
                    out.add(line)
        except OSError:
            pass
        if d == root or os.path.dirname(d) == d:
            return out
        d = os.path.dirname(d)


def norm_host(h):
    h = h.strip().strip("'\"").lower()
    if h.startswith("tcp:"):
        h = h[4:]
    if h.startswith("[") and "]" in h:
        return h[1:h.index("]")]
    if h.startswith("(localdb)"):
        return "(localdb)"
    h = h.split("\\", 1)[0].split(",", 1)[0]
    if h.count(":") == 1:
        h = h.split(":", 1)[0]
    return h


def is_local(host, cwd, safe):
    if host in LOCAL_HOSTS or host == "(localdb)" or host.startswith("127.") or host.endswith(".localhost"):
        return True
    return host in safe


def sqlite_local(path, cwd):
    if path in (":memory:",) or path.startswith("file::memory:"):
        return True
    root = os.path.realpath(project_root(cwd))
    full = os.path.realpath(os.path.join(cwd or os.getcwd(), os.path.expanduser(path)))
    return full == root or full.startswith(root + os.sep)


def target_hosts(t, cwd):
    """대상 문자열 하나 → 호스트 목록. 로컬 전용 형식이면 ['localhost']. 해석 못 하면 None."""
    t = t.strip().strip("'\"")
    low = t.lower()
    if not t or "$" in t or "`" in t:
        return None
    if low.startswith("jdbc:tc:") or re.match(r"jdbc:(h2:mem|hsqldb:mem|derby:memory)", low):
        return ["localhost"]
    m = re.match(r"jdbc:(sqlite|h2(:file)?|hsqldb:file|derby):(.*)", low)
    if m and "//" not in m.group(3)[:2] and not m.group(3).startswith("tcp:"):
        return ["localhost"] if sqlite_local(t.split(":", 2)[-1].split(";")[0], cwd) else None
    m = re.match(r"jdbc:oracle:thin:[^@]*@(//)?([^:/;?]+)", low)
    if m:
        return [m.group(2)] if "(" not in m.group(2) else None
    m = re.match(r"(?:jdbc:)?[a-z0-9+.:-]*?//([^/;?]*)", low)
    if m:
        auth = m.group(1).rsplit("@", 1)[-1]
        hosts = [norm_host(h) for h in re.split(r",(?![0-9]+(?:[,/;]|$))", auth) if h]
        return hosts or None
    if "=" in t:
        kv = {}
        for part in t.split(";"):
            if "=" in part:
                k, v = part.split("=", 1)
                kv[re.sub(r"\s+", "", k).lower()] = v.strip()
        for k in ("server", "host", "address", "addr", "networkaddress"):
            if kv.get(k):
                return [norm_host(h) for h in kv[k].split(",") if h.strip() and not h.strip().isdigit()] or None
        ds = kv.get("datasource") or kv.get("filename")
        if ds:
            if re.search(r"\.(db|sqlite|sqlite3|db3)$", ds.lower()) or ds == ":memory:":
                return ["localhost"] if sqlite_local(ds, cwd) else None
            if "//" in ds:  # Oracle: Data Source=//host:1521/svc
                return target_hosts("x:" + ds[ds.index("//"):], cwd)
            return [norm_host(ds)]
        return None
    return None


def check_targets(tool, targets, cwd, safe):
    if not targets:
        raise Deny(f"{tool}: 대상 DB가 명령에 없습니다(설정 파일·환경 의존은 판단하지 않음)")
    for t in targets:
        hosts = target_hosts(t, cwd)
        if not hosts:
            raise Deny(f"{tool}: 대상 DB를 해석할 수 없습니다(변수·명령 치환이나 지원하지 않는 형식)")
        for h in hosts:
            if not is_local(h, cwd, safe):
                raise Deny(f"{tool}: 로컬이 아닌 DB 호스트 '{h}'")


# ── 명령 판정 ────────────────────────────────
def opt_values(args, names):
    """--name=값, --name 값, -name=값 형태의 값들."""
    out = []
    for n, a in enumerate(args):
        for name in names:
            if a == name and n + 1 < len(args):
                out.append(args[n + 1])
            elif a.startswith(name + "="):
                out.append(a[len(name) + 1:])
    return out


def env_targets(env, extra=()):
    keys = TARGET_VARS + tuple(extra)
    return [v for k, v in env.items() if k in keys or k.startswith("ConnectionStrings__")]


def prod_value(v):
    """쉼표 목록의 프로파일 중 하나라도 prod·production·prd·live 이거나 그 조각(prod-kr, kr_prod)이면 True."""
    for p in re.split(r"[,\s]+", v.strip().strip("'\"")):
        if p and any(part in PROD_VALUES for part in re.split(r"[-_.]", p.lower())):
            return True
    return False


def check_prod(env, args, name):
    for k, v in env.items():
        if k in PROD_VARS and prod_value(v):
            raise Deny(f"운영 환경 지정 {k}={v}")
    if name in DATA_CMDS:
        return
    for n, a in enumerate(args):
        for m in re.finditer(r"(ASPNETCORE_ENVIRONMENT|DOTNET_ENVIRONMENT|SPRING_PROFILES_ACTIVE)=([\w,.-]+)", a):
            if prod_value(m.group(2)):
                raise Deny(f"운영 환경 지정 {m.group(1)}={m.group(2)}")
        for m in re.finditer(r"(?:spring\.profiles\.active|spring-boot\.run\.profiles)[=\s]+([\w,.-]+)", a):
            if prod_value(m.group(1)):
                raise Deny(f"운영 프로파일 spring.profiles.active={m.group(1)}")
        if a in ("--spring.profiles.active", "-Dspring.profiles.active") and n + 1 < len(args) and prod_value(args[n + 1]):
            raise Deny(f"운영 프로파일 {a} {args[n + 1]}")
        if a == "--environment" and n + 1 < len(args) and prod_value(args[n + 1]):
            raise Deny(f"운영 환경 --environment {args[n + 1]}")
        if a.startswith("--environment=") and prod_value(a.split("=", 1)[1]):
            raise Deny(f"운영 환경 {a}")
        if re.fullmatch(r"-P(prod|production|prd|live)", a, re.I):
            raise Deny(f"운영 프로파일 {a}")


def liquibase_risky(cmd):
    return cmd.lower().replace("-", "") in LIQUIBASE_RISK


def build_has_liquibase(cwd):
    """cwd → 레포 루트의 Gradle 빌드 파일에 liquibase 가 보이면 True, 없으면 False, 빌드 파일이 없으면 None."""
    root, d, seen = project_root(cwd), os.path.abspath(cwd or os.getcwd()), False
    names = ("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts",
             os.path.join("gradle", "libs.versions.toml"))
    while True:
        for n in names:
            f = os.path.join(d, n)
            if os.path.isfile(f):
                seen = True
                try:
                    if "liquibase" in open(f, encoding="utf-8", errors="replace").read().lower():
                        return True
                except OSError:
                    return None
        if os.path.isdir(os.path.join(d, "buildSrc")):
            seen = True
            for base, _, files in os.walk(os.path.join(d, "buildSrc")):
                for fn in files:
                    if fn.endswith((".gradle", ".kts", ".toml")):
                        try:
                            if "liquibase" in open(os.path.join(base, fn), encoding="utf-8", errors="replace").read().lower():
                                return True
                        except OSError:
                            return None
        if d == root or os.path.dirname(d) == d:
            return False if seen else None
        d = os.path.dirname(d)


def check_migration(name, args, env, cwd, safe):
    low = [a.lower() for a in args]
    # dotnet ef database update|drop
    ef = None
    if name == "dotnet" and low[:1] == ["ef"]:
        ef = args[1:]
    elif name in ("dotnet-ef",):
        ef = args
    if ef is not None:
        pos = [a.lower() for a in ef if not a.startswith("-")]
        if pos[:1] == ["database"] and len(pos) > 1 and pos[1] in ("update", "drop"):
            check_targets("dotnet ef database " + pos[1], opt_values(ef, ["--connection"]) + env_targets(env), cwd, safe)
        return
    if name == "flyway":
        if any(a in FLYWAY_RISK for a in low):
            verb = next(a for a in low if a in FLYWAY_RISK)
            check_targets("flyway " + verb, opt_values(args, ["-url", "--url"]) + env_targets(env), cwd, safe)
        return
    if name == "liquibase":
        verb = next((a for a in args if not a.startswith("-") and liquibase_risky(a)), None)
        if verb:
            check_targets("liquibase " + verb, opt_values(args, ["--url", "-url"]) + env_targets(env), cwd, safe)
        return
    if name in ("gradle", "gradlew", "gradlew.bat"):
        tasks = [a.rsplit(":", 1)[-1] for a in args if not a.startswith("-")]
        risky = [t for t in tasks if re.fullmatch(r"flyway(Migrate|Clean|Repair|Undo|Baseline)", t)]
        generic = [t for t in tasks if not t.startswith("flyway") and liquibase_risky(t)]
        if generic:
            has = build_has_liquibase(cwd)
            if has is None:
                raise Deny(f"gradle {generic[0]}: 빌드 파일을 찾지 못해 liquibase 태스크인지 판단할 수 없습니다")
            if has:
                risky += generic
        if risky:
            check_targets("gradle " + risky[0], url_props(args) + env_targets(env), cwd, safe)
        return
    if name in ("mvn", "mvnw", "mvnw.cmd"):
        risky = []
        for a in args:
            if a.startswith("-") or ":" not in a:
                continue
            plugin, goal = a.rsplit(":", 1)
            if "flyway" in plugin.lower() and goal.lower() in FLYWAY_RISK:
                risky.append(a)
            elif "liquibase" in plugin.lower() and liquibase_risky(goal):
                risky.append(a)
        if risky:
            check_targets("mvn " + risky[0], url_props(args) + env_targets(env), cwd, safe)
        return
    if name in ("docker", "podman") and "run" in low:
        # docker run [옵션] <이미지> [이미지 인자]: flyway/liquibase 이미지만 본다
        for n, a in enumerate(args):
            m = re.search(r"(?:^|/)(flyway|liquibase)(?::[\w.-]+)?$", a.lower())
            if m and not a.startswith("-"):
                denv = dict(env)
                for v in opt_values(args[:n], ["-e", "--env"]):
                    if "=" in v:
                        k, val = v.split("=", 1)
                        denv[k] = val
                check_prod(denv, [], m.group(1))
                check_migration(m.group(1), args[n + 1:], denv, cwd, safe)
                return


def url_props(args):
    return [a.split("=", 1)[1] for a in args if re.match(r"-[DP][\w.]*url=", a, re.I)]


def check_command(cmd, cwd, env, depth=0, seen=None):
    """명령 문자열 하나. env 는 export·대입으로 바뀌는 셸 환경(대입만 추적)."""
    if depth > MAX_DEPTH:
        raise Deny("셸 스크립트·bash -c 중첩이 너무 깊어 검사할 수 없습니다")
    safe = safe_hosts(cwd)
    body, docs = split_heredocs(cmd)
    for start, text in docs:  # bash <<EOF 처럼 셸에 먹이는 히어독만 명령으로 본다
        sw, _ = words(start.split("<<", 1)[0])
        _, sw = split_prefix(sw)
        if sw and os.path.basename(sw[0]) in SHELLS:
            check_command(text, cwd, dict(env), depth + 1, seen)
    for seg, sep in segments(body):
        toks, _ = words(seg)
        assigns, rest = split_prefix(toks)
        local = dict(env)
        for a in assigns:
            k, v = a.split("=", 1)
            local[k] = v
        if not rest:
            env.update(local)  # A=B 만 있는 조각은 이후 조각의 환경을 바꾼다
            check_prod(local, [], "")
            continue
        name, args = os.path.basename(rest[0]), rest[1:]
        if name == "export":
            for a in args:
                if "=" in a:
                    k, v = a.split("=", 1)
                    env[k] = v
                    local[k] = v
            check_prod(local, [], "")
            continue
        if name == "cd" and args:
            cwd = os.path.normpath(os.path.join(cwd or os.getcwd(), os.path.expanduser(args[0])))
            safe = safe_hosts(cwd)
            continue
        dynamic = (name == "eval" or rest[0].startswith("$") or "$(" in seg or "`" in seg
                   or (name in SHELLS and sep == "|" and not any(a.startswith("-c") or not a.startswith("-") for a in args)))
        check_prod(local, args, name)
        if dynamic and STRONG.search(cmd) and (name == "eval" or rest[0].startswith("$") or name in SHELLS
                                               or STRONG.search(seg)):
            raise Deny("위험 명령과 함께 쓴 동적 구문(eval, $( ), 백틱, | sh)은 판단할 수 없습니다")
        if name in SHELLS or name == "source" or name == ".":
            inner = None
            for n, w in enumerate(args):
                if w.startswith("-") and "c" in w.lstrip("-") and n + 1 < len(args):
                    inner = args[n + 1]
                    break
            if inner is not None:
                if "$" in inner and STRONG.search(cmd):
                    raise Deny("위험 명령과 함께 쓴 sh -c \"$변수\" 는 판단할 수 없습니다")
                check_command(inner, cwd, dict(local), depth + 1, seen)
                continue
            script = next((w for w in args if not w.startswith("-")), None)
            if script:
                check_script(script, cwd, local, depth, seen)
            continue
        if rest[0].endswith((".sh", ".bash")) or ("/" in rest[0] and is_shell_script(rest[0], cwd)):
            check_script(rest[0], cwd, local, depth, seen)
            continue
        check_migration(name, args, local, cwd, safe)


def is_shell_script(path, cwd):
    full = os.path.join(cwd or os.getcwd(), os.path.expanduser(path))
    try:
        with open(full, "rb") as f:
            head = f.readline(200)
    except OSError:
        return False
    return head.startswith(b"#!") and any(s.encode() in head for s in SHELLS) and b"gradle" not in head.lower()


def check_script(path, cwd, env, depth, seen):
    full = os.path.realpath(os.path.join(cwd or os.getcwd(), os.path.expanduser(path)))
    if not os.path.exists(full):
        return  # 없는 파일은 실행되지 않는다
    if os.path.basename(full) in ("gradlew", "mvnw"):
        return
    seen = set(seen or ())
    if full in seen:
        return
    seen.add(full)
    try:
        if os.path.getsize(full) > MAX_SCRIPT:
            raise Deny(f"스크립트가 너무 커서 검사할 수 없습니다: {path}")
        text = open(full, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError):
        raise Deny(f"스크립트를 읽을 수 없어 검사할 수 없습니다: {path}")
    check_command(text, os.path.dirname(full), dict(env), depth + 1, seen)


def commands(payload):
    """검사할 명령 목록. 실행 도구가 아니면 빈 목록. 셸 도구인데 명령이 없으면 Deny."""
    tool = str(payload.get("tool_name") or "").lower()
    ti = payload.get("tool_input")
    if not isinstance(ti, dict):
        if tool in SHELL_TOOLS:
            raise Deny("셸 도구 입력 형식을 해석할 수 없습니다")
        return []
    out = []
    for key in ("command", "cmd"):
        v = ti.get(key)
        if v is None:
            continue
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, list) and v and all(isinstance(x, str) for x in v):
            out.append(argv_to_cmd(v))
        else:
            raise Deny("셸 명령 형식을 해석할 수 없습니다")
    if not out and tool in SHELL_TOOLS:
        raise Deny("셸 도구인데 명령이 없습니다")
    return out


def argv_to_cmd(argv):
    """Codex 의 ["bash","-lc","..."] 는 안쪽 문자열, 나머지 argv 는 따옴표로 묶어 한 줄로."""
    if len(argv) >= 3 and os.path.basename(argv[0]) in SHELLS and argv[1].startswith("-") and "c" in argv[1]:
        return argv[2]
    return " ".join("'" + a.replace("'", "'\\''") + "'" if (not a or re.search(r"[\s;&|<>$`'\"]", a)) else a
                    for a in argv)


def main():
    if os.environ.get("KNACK_GUARD_PROD", "").lower() == "off":
        return
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError
    except ValueError:
        deny("훅 입력(JSON)을 해석할 수 없습니다")
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else ""
    try:
        for cmd in commands(payload):
            check_command(cmd, cwd, {})
    except Deny as e:
        deny(str(e))
    except Exception as e:  # 파서 예외: 위험 키워드가 있으면 막는다
        if STRONG.search(raw):
            deny(f"검사 중 오류로 판단할 수 없습니다 ({type(e).__name__})")


if __name__ == "__main__":
    main()
