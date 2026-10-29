#!/usr/bin/env python3
"""stack-verify: 레포의 Spring(Gradle·Maven)·.NET 빌드 단위를 찾아 검증 명령을 JSON 으로 낸다.

사용: python3 detect.py [레포 경로]   (기본: 현재 폴더)
명령은 실행하지 않는다. 근거 파일(evidence)이 없는 명령은 내지 않는다(null).
"""
import json
import os
import re
import sys

SCHEMA_VERSION = 1
MAX_DEPTH = 4
SKIP_DIRS = {"build", "out", "bin", "obj", "target", "node_modules", "dist", "vendor", "packages"}


def read(path, limit=512 * 1024):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(limit)
    except OSError:
        return ""


def walk(root):
    """root 아래 MAX_DEPTH 단계까지 (상대 폴더, 파일 목록)."""
    for base, dirs, files in os.walk(root):
        rel = os.path.relpath(base, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS)
        if depth >= MAX_DEPTH:
            dirs[:] = []
        yield ("." if rel == "." else rel), sorted(files)


def under(rel, roots):
    """rel 이 이미 찾은 빌드 루트 안이면 True (Gradle 하위 모듈, Maven 자식 pom)."""
    return any(r == "." or rel == r or rel.startswith(r + os.sep) for r in roots)


def migrations(root, rel, text):
    """빌드 파일·리소스 폴더로 마이그레이션 도구와 Testcontainers 사용을 본다."""
    base = os.path.join(root, rel)
    low = text.lower()
    tool, ev = None, []
    for name in ("flyway", "liquibase"):
        if name in low:
            tool = name
            ev.append(f"빌드 파일에 '{name}'")
            break
    for b, dirs, _ in os.walk(base):  # 하위 모듈의 src/main/resources/db/{migration,changelog}
        r = os.path.relpath(b, base)
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS]
        if r.count(os.sep) >= 6:
            dirs[:] = []
        if r.replace(os.sep, "/").endswith(("src/main/resources/db/migration", "src/main/resources/db/changelog")):
            ev.append(os.path.normpath(os.path.join(rel, r)))
            tool = tool or ("flyway" if r.endswith("migration") else "liquibase")
    return tool, ev, "testcontainers" in low


def gradle_unit(root, rel, files):
    base = os.path.join(root, rel)
    ev = [f for f in files if re.fullmatch(r"(build|settings)\.gradle(\.kts)?|gradlew", f)]
    text = ""
    for b, _, fs in os.walk(base):  # 하위 모듈 빌드 파일까지 (플러그인·의존성 확인용)
        if os.path.relpath(b, base).count(os.sep) >= 2 or any(p in SKIP_DIRS for p in b.split(os.sep)):
            continue
        for f in fs:
            if re.fullmatch(r"build\.gradle(\.kts)?|libs\.versions\.toml", f):
                text += read(os.path.join(b, f))
    w = "./gradlew" if "gradlew" in files else None
    g = w or "gradle"
    low = text.lower()
    fmt = None
    if "spotless" in low:
        fmt = {"check": f"{g} spotlessCheck", "apply": f"{g} spotlessApply", "evidence": "spotless 플러그인"}
    elif "ktlint" in low:
        fmt = {"check": f"{g} ktlintCheck", "apply": f"{g} ktlintFormat", "evidence": "ktlint 플러그인"}
    lint = f"{g} checkstyleMain" if "checkstyle" in low else None
    tool, mev, tc = migrations(root, rel, text)
    return {
        "kind": "gradle", "dir": rel, "evidence": ev, "wrapper": w,
        "commands": {
            "compile": f"{g} testClasses",
            "test": f"{g} test",
            "single_test": f"{g} test --tests '<패키지.클래스명>'",
            "format": fmt, "lint": lint, "full": f"{g} build",
        },
        "migration": {"tool": tool, "evidence": mev, "testcontainers": tc},
    }


def maven_unit(root, rel, files):
    base = os.path.join(root, rel)
    text = read(os.path.join(base, "pom.xml"))
    for b, _, fs in os.walk(base):  # 자식 모듈 pom 까지
        if b != base and "pom.xml" in fs and os.path.relpath(b, base).count(os.sep) < 2 \
                and not any(p in SKIP_DIRS for p in b.split(os.sep)):
            text += read(os.path.join(b, "pom.xml"))
    w = "./mvnw" if "mvnw" in files else None
    m = w or "mvn"
    low = text.lower()
    fmt = None
    if "spotless-maven-plugin" in low:
        fmt = {"check": f"{m} -B spotless:check", "apply": f"{m} -B spotless:apply", "evidence": "spotless-maven-plugin"}
    lint = f"{m} -B checkstyle:check" if "maven-checkstyle-plugin" in low else None
    tool, mev, tc = migrations(root, rel, text)
    return {
        "kind": "maven", "dir": rel, "evidence": [f for f in files if f in ("pom.xml", "mvnw")], "wrapper": w,
        "commands": {
            "compile": f"{m} -B -q test-compile",
            "test": f"{m} -B test",
            "single_test": f"{m} -B test -Dtest='<클래스명>' -Dsurefire.failIfNoSpecifiedTests=false",
            "format": fmt, "lint": lint, "full": f"{m} -B verify",
        },
        "migration": {"tool": tool, "evidence": mev, "testcontainers": tc},
    }


def dotnet_unit(root, rel, target, projects):
    """target: .sln/.slnx 또는 단일 .csproj. projects: 이 단위에 속한 csproj 상대 경로."""
    text = "".join(read(os.path.join(root, p)) for p in projects)
    low = text.lower()
    t = f" {target}" if target else ""
    ef = "microsoft.entityframeworkcore" in low
    mig_dirs = []
    for p in projects:
        d = os.path.join(os.path.dirname(p), "Migrations")
        if os.path.isdir(os.path.join(root, d)):
            mig_dirs.append(d)
    tools = read(os.path.join(root, ".config", "dotnet-tools.json")).lower()
    tests = [p for p in projects if re.search(r"(test|tests|spec)s?\.csproj$", p.lower())
             or "microsoft.net.test.sdk" in read(os.path.join(root, p)).lower()]
    ev = [target] if target else []
    if os.path.isfile(os.path.join(root, "global.json")):
        ev.append("global.json")
    return {
        "kind": "dotnet", "dir": rel, "evidence": ev + projects[:20], "wrapper": None,
        "commands": {
            "compile": f"dotnet build{t}",
            "test": f"dotnet test{t}" if tests else None,
            "single_test": f'dotnet test{t} --filter "FullyQualifiedName~<클래스명>"' if tests else None,
            "format": {"check": f"dotnet format{t} --verify-no-changes", "apply": f"dotnet format{t}",
                       "evidence": "dotnet SDK 기본 포함(6 이상)"},
            "lint": None, "full": f"dotnet build{t} && dotnet test{t}" if tests else f"dotnet build{t}",
        },
        "test_projects": tests,
        "migration": {
            "tool": "ef-core" if ef and (mig_dirs or "entityframeworkcore.design" in low) else None,
            "evidence": mig_dirs + (["Microsoft.EntityFrameworkCore.Design"] if "entityframeworkcore.design" in low else []),
            "testcontainers": "testcontainers" in low,
            "dotnet_ef_local_tool": "dotnet-ef" in tools,
        },
    }


def detect(root):
    root = os.path.abspath(root)
    units, jvm_roots, slns, csprojs = [], [], [], []
    for rel, files in walk(root):
        if not under(rel, jvm_roots):
            if any(re.fullmatch(r"(build|settings)\.gradle(\.kts)?", f) for f in files):
                units.append(gradle_unit(root, rel, files))
                jvm_roots.append(rel)
            elif "pom.xml" in files:
                units.append(maven_unit(root, rel, files))
                jvm_roots.append(rel)
        for f in files:
            p = os.path.normpath(os.path.join(rel, f))
            if f.endswith((".sln", ".slnx")):
                slns.append(p)
            elif f.endswith(".csproj"):
                csprojs.append(p)
    claimed = set()
    for sln in sorted(slns, key=lambda p: (p.count(os.sep), p)):
        text = read(os.path.join(root, sln))
        base = os.path.dirname(sln)
        if sln.endswith(".slnx"):
            refs = re.findall(r'Path="([^"]+\.csproj)"', text)
        else:
            refs = re.findall(r'"([^"]+\.csproj)"', text)
        projs = sorted({os.path.normpath(os.path.join(base, r.replace("\\", "/"))) for r in refs})
        projs = [p for p in projs if p in csprojs and p not in claimed]
        if not projs and claimed:
            continue  # 이미 상위 솔루션이 가진 프로젝트뿐
        claimed.update(projs)
        units.append(dotnet_unit(root, base or ".", os.path.basename(sln), projs))
    for p in csprojs:  # 솔루션에 없는 프로젝트
        if p not in claimed:
            units.append(dotnet_unit(root, os.path.dirname(p) or ".", os.path.basename(p), [p]))
    for u in units:
        u["run_dir"] = u.pop("dir")
    notes = []
    if not units:
        notes.append("Gradle·Maven·.NET 빌드 파일을 찾지 못했습니다. README·CI 설정에서 명령을 찾으세요.")
    if len(units) > 1:
        notes.append("빌드 단위가 여럿입니다. 바꾼 파일이 속한 단위(run_dir)만 돌리세요.")
    ci = [os.path.join(d, f) for d in (".github/workflows",) if os.path.isdir(os.path.join(root, d))
          for f in sorted(os.listdir(os.path.join(root, d))) if f.endswith((".yml", ".yaml"))]
    return {"schema_version": SCHEMA_VERSION, "root": root, "units": units, "ci_files": ci, "notes": notes}


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    if not os.path.isdir(root):
        print(json.dumps({"schema_version": SCHEMA_VERSION, "error": f"폴더가 아닙니다: {root}"}, ensure_ascii=False))
        return 2
    print(json.dumps(detect(root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
