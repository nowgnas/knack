#!/usr/bin/env python3
"""stack-verify: 레포의 Spring(Gradle·Maven)·.NET 빌드 단위를 찾아 검증 명령을 JSON 으로 낸다.

사용: python3 detect.py [레포 경로]   (기본: 현재 폴더)
명령은 실행하지 않는다. 근거 파일(evidence)이 없는 명령은 내지 않는다(null).
"""
import json
import os
import re
import shlex
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


def strip_comments(text, xml=False):
    """주석 속 단어(예: '// spotless')를 플러그인 근거로 쓰지 않도록 지운다."""
    if xml:
        return re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)(^|[^:])//[^\n]*", r"\1", text)


# Gradle: java 계열 플러그인이 적용돼야 testClasses·test 태스크가 생긴다.
# Spring Boot 플러그인은 java 플러그인에 반응할 뿐 스스로 이 태스크를 만들지 않으므로 근거가 아니다.
JVM_PLUGIN = re.compile(
    r"""id\s*\(?\s*["'](java|java-library|application|war|org\.jetbrains\.kotlin\.jvm)["']"""
    r"""|apply\s*\(?\s*plugin\s*[:=]\s*["'](java|java-library|application|war|kotlin|org\.jetbrains\.kotlin\.jvm)["']"""
    r"""|kotlin\s*\(\s*["']jvm["']\s*\)|`java(-library)?`|(?m:^\s*(java|`java-library`|application)\s*$)|\{\s*java\s*\}"""
    r"""|alias\s*\(\s*libs\.plugins\.kotlin[\w.]*jvm\s*\)""")


APPLY_FALSE = re.compile(
    r"""(id\s*\(?\s*["'][^"']+["']\s*\)?|alias\s*\([^)]*\)|kotlin\s*\([^)]*\)|`[\w-]+`)"""
    r"""(\s*\.?\s*version\s*\(?\s*["'][^"']*["']\s*\)?)?\s*\.?\s*apply\s*\(?\s*false\s*\)?""")


def plugin_re(plugin_id, alias, block):
    """플러그인 '적용'만 근거로 본다: plugins{} 의 id·alias, apply plugin, 설정 블록."""
    q = re.escape(plugin_id)
    return re.compile(rf"""id\s*\(?\s*["']{q}["']|apply\s*\(?\s*plugin\s*[:=]\s*["']{q}["']"""
                      rf"""|alias\s*\(\s*libs\.plugins\.{alias}\s*\)|(?m:^\s*{block}\s*\{{)""")


GRADLE_PLUGIN = {
    "spotless": plugin_re("com.diffplug.spotless", "spotless", "spotless"),
    "ktlint": plugin_re("org.jlleitschuh.gradle.ktlint", r"ktlint[\w.]*", "ktlint"),
    "checkstyle": re.compile(r"""id\s*\(?\s*["']checkstyle["']|plugin\s*[:=]\s*["']checkstyle["']"""
                             r"""|(?m:^\s*checkstyle\s*$)|(?m:^\s*checkstyle\s*\{)"""),
}
EF_PROVIDERS = {
    "npgsql.entityframeworkcore.postgresql": "postgresql",
    "microsoft.entityframeworkcore.sqlserver": "sqlserver",
    "microsoft.entityframeworkcore.sqlite": "sqlite",
    "pomelo.entityframeworkcore.mysql": "mysql",
    "mysql.entityframeworkcore": "mysql",
    "oracle.entityframeworkcore": "oracle",
}


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


def gradle_files(base):
    """하위 모듈 빌드 파일(루트 아래 3단계 폴더까지)과 buildSrc·build-logic 의 컨벤션 플러그인."""
    for b, dirs, fs in os.walk(base):
        r = os.path.relpath(b, base)
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS]
        conv = r.split(os.sep)[0] in ("buildSrc", "build-logic")
        if r.count(os.sep) >= (6 if conv else 2):
            dirs[:] = []
        for f in fs:
            if re.fullmatch(r"build\.gradle(\.kts)?", f) or \
                    (conv and f.endswith((".gradle", ".gradle.kts"))):
                yield os.path.join(b, f)


def gradle_unit(root, rel, files):
    base = os.path.join(root, rel)
    ev = [f for f in files if re.fullmatch(r"(build|settings)\.gradle(\.kts)?|gradlew", f)]
    text = "\n".join(strip_comments(read(p)) for p in gradle_files(base))
    # `id 'java' apply false` 처럼 선언만 하고 적용하지 않은 플러그인은 근거에서 뺀다(그 선언만, 줄바꿈 포함)
    text = APPLY_FALSE.sub("", text)
    w = "./gradlew" if "gradlew" in files else None
    g = w or "gradle"
    jvm = bool(JVM_PLUGIN.search(text))
    fmt = None
    if GRADLE_PLUGIN["spotless"].search(text):
        fmt = {"check": f"{g} spotlessCheck", "apply": f"{g} spotlessApply", "evidence": "spotless 플러그인"}
    elif GRADLE_PLUGIN["ktlint"].search(text):
        fmt = {"check": f"{g} ktlintCheck", "apply": f"{g} ktlintFormat", "evidence": "ktlint 플러그인"}
    lint = f"{g} checkstyleMain" if jvm and GRADLE_PLUGIN["checkstyle"].search(text) else None
    tool, mev, tc = migrations(root, rel, text)
    settings = strip_comments("".join(read(os.path.join(base, f)) for f in ("settings.gradle", "settings.gradle.kts")))
    modules = sorted({m if m.startswith(":") else ":" + m
                      for inc in re.findall(r"""\binclude\b\s*\(?((?:\s*["'][^"']+["']\s*,?)+)""", settings)
                      for m in re.findall(r"""["']([^"']+)["']""", inc)})
    # include 가 하나라도 있으면(반복문 등으로 못 읽은 경우 포함) 루트 필터 명령을 내지 않는다
    multi = bool(re.search(r"\binclude\b", settings))
    single = f"{g} <모듈>:test --tests '<패키지.클래스명>'" if multi else f"{g} test --tests '<패키지.클래스명>'"
    unit = {
        "kind": "gradle", "dir": rel, "evidence": ev, "wrapper": w,
        "commands": {
            "compile": f"{g} testClasses" if jvm else None,
            "test": f"{g} test" if jvm else None,
            "single_test": single if jvm else None,
            "format": fmt, "lint": lint, "full": f"{g} build" if jvm else None,
        },
        "migration": {"tool": tool, "evidence": mev, "testcontainers_dependency": tc},
        "modules": modules,
    }
    if not jvm:
        unit["note"] = f"java·kotlin(jvm) 플러그인 적용 근거를 못 찾았습니다. `{g} tasks --all`로 태스크를 확인하세요."
        if re.search(r"org\.jetbrains\.kotlin\.(android|multiplatform)|kotlin\s*\(\s*[\"'](android|multiplatform)", text):
            unit["note"] += " Android·KMP 는 test·testClasses 대신 변형별 태스크(예: jvmTest, testDebugUnitTest)를 씁니다."
    return unit


def maven_unit(root, rel, files):
    base = os.path.join(root, rel)
    text = read(os.path.join(base, "pom.xml"))
    for b, dirs, fs in os.walk(base):  # 자식 모듈 pom 까지 (2단계)
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS]
        if os.path.relpath(b, base).count(os.sep) >= 1:
            dirs[:] = []
        if b != base and "pom.xml" in fs:
            text += read(os.path.join(b, "pom.xml"))
    text = strip_comments(text, xml=True)
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
        "migration": {"tool": tool, "evidence": mev, "testcontainers_dependency": tc},
    }


def test_code_calls(root, test_projects):
    """테스트 코드가 EF 마이그레이션을 실제로 적용하는지(Migrate) 아니면 건너뛰는지(EnsureCreated)."""
    found = {"migrate": False, "ensure_created": False}
    for p in test_projects:
        for b, dirs, fs in os.walk(os.path.join(root, os.path.dirname(p))):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS]
            for f in fs:
                if f.endswith(".cs"):
                    t = read(os.path.join(b, f))
                    found["migrate"] |= bool(re.search(r"\.Migrate(Async)?\s*\(", t))
                    found["ensure_created"] |= bool(re.search(r"\.EnsureCreated(Async)?\s*\(", t))
    return found


def dotnet_unit(root, rel, target, projects):
    """target: .sln/.slnx 또는 단일 .csproj. projects: 이 단위에 속한 csproj 상대 경로."""
    text = "".join(read(os.path.join(root, p)) for p in projects)
    low = text.lower()
    t = f" {shlex.quote(target)}" if target else ""
    ef = "microsoft.entityframeworkcore" in low
    mig_dirs = []
    for p in projects:
        d = os.path.join(os.path.dirname(p), "Migrations")
        if os.path.isdir(os.path.join(root, d)):
            mig_dirs.append(d)
    tools = read(os.path.join(root, ".config", "dotnet-tools.json")).lower()
    tests = [p for p in projects if re.search(r"(^|[./\\_-])(tests?|specs?|integrationtests?)\.csproj$", p.lower())
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
                       "evidence": "dotnet SDK 6 이상 기본 포함(SDK 버전 확인 필요)"},
            "lint": None, "full": f"dotnet build{t} && dotnet test{t}" if tests else f"dotnet build{t}",
        },
        "test_projects": tests,
        "migration": {
            "tool": "ef-core" if ef and (mig_dirs or "entityframeworkcore.design" in low) else None,
            "evidence": mig_dirs + (["Microsoft.EntityFrameworkCore.Design"] if "entityframeworkcore.design" in low else []),
            "testcontainers_dependency": "testcontainers" in low,
            "dotnet_ef_local_tool": "dotnet-ef" in tools,
            "ef_providers": sorted({v for k, v in EF_PROVIDERS.items() if re.search(re.escape(k) + r"(\.core)?[\"';]", low)}),
            "tests_call": test_code_calls(root, tests) if ef else None,
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
    else:
        notes.append("single_test 는 이름이 틀려도 0건으로 통과할 수 있습니다. 출력에서 실행된 테스트 수가 1 이상인지 확인하세요.")
    if len(units) > 1:
        notes.append("빌드 단위가 여럿입니다. 바꾼 파일이 속한 단위(run_dir)만 돌리세요.")
    ci = [os.path.join(d, f) for d in (".github/workflows",) if os.path.isdir(os.path.join(root, d))
          for f in sorted(os.listdir(os.path.join(root, d))) if f.endswith((".yml", ".yaml"))]
    ci += [f for f in (".gitlab-ci.yml", "azure-pipelines.yml", "Jenkinsfile", "bitbucket-pipelines.yml")
           if os.path.isfile(os.path.join(root, f))]
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
