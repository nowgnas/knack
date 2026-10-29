"""guard-prod-ops 훅: 운영 DB 마이그레이션·운영 프로파일 차단(fail-closed) 회귀 테스트.

같은 명령을 Claude(Bash, 문자열)와 Codex(shell, ["bash","-lc",…]) 형식으로 모두 돌린다.
실행: python3 tests/test_guard_prod.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "hooks", "guard-prod-ops", "guard_prod.py")

DENY = [
    # dotnet ef
    'dotnet ef database update',
    'dotnet ef database update --connection "Server=prod-sql.corp;Database=app;User Id=sa;Password=x"',
    'dotnet ef database update --connection "Database=app;Server=tcp:app.database.windows.net,1433"',
    'dotnet ef database drop -f --connection "Host=10.0.3.4;Database=app"',
    'dotnet ef database update --connection "$CS"',
    'dotnet ef database update --connection "$(cat cs.txt)"',
    'ConnectionStrings__Default="Server=prod;Database=x" dotnet ef database update',
    'cd src/Api && dotnet ef database update 0',
    'ASPNETCORE_ENVIRONMENT=Production dotnet ef database update --connection "Server=localhost;Database=x"',
    # flyway / liquibase
    'flyway migrate',
    'flyway -url=jdbc:postgresql://prod-db.internal:5432/app migrate',
    'flyway clean -url=jdbc:sqlserver://db.corp:1433;databaseName=app',
    'FLYWAY_URL=jdbc:mysql://rds.amazonaws.com/app flyway repair',
    'liquibase --url=jdbc:oracle:thin:@prod-ora:1521/APP update',
    'liquibase update --url jdbc:postgresql://10.1.1.1/app',
    'liquibase rollback-count 1',
    'docker run --rm flyway/flyway -url=jdbc:postgresql://prod/app migrate',
    'docker run --rm -e FLYWAY_URL=jdbc:postgresql://prod/app flyway/flyway:10 migrate',
    # gradle / maven
    './gradlew flywayMigrate',
    './gradlew :db:flywayClean -Pflyway.url=jdbc:postgresql://prod/app',
    'mvn flyway:migrate -Dflyway.url=jdbc:postgresql://shared-db/app',
    './mvnw liquibase:update',
    'mvn org.flywaydb:flyway-maven-plugin:10.0.0:migrate',
    # prod profile / environment
    'SPRING_PROFILES_ACTIVE=prod ./gradlew bootRun',
    'SPRING_PROFILES_ACTIVE=dev,prod java -jar build/libs/app.jar',
    'java -jar app.jar --spring.profiles.active=prod',
    'java -Dspring.profiles.active=production -jar app.jar',
    "./gradlew bootRun --args='--spring.profiles.active=prod'",
    'mvn spring-boot:run -Dspring-boot.run.profiles=prod-kr',
    'mvn -Pprod package',
    'ASPNETCORE_ENVIRONMENT=Production dotnet run',
    'export DOTNET_ENVIRONMENT=Production && dotnet run',
    'dotnet run --environment Production',
    'dotnet run -e ASPNETCORE_ENVIRONMENT=Production',
    'env SPRING_PROFILES_ACTIVE=prod java -jar app.jar',
    'docker run -e ASPNETCORE_ENVIRONMENT=Production myapi:latest',
    # 우회·동적
    'eval "dotnet ef database update"',
    'X="flyway migrate"; $X',
    'echo "flyway migrate" | sh',
    'sh -c "$MIGRATE flyway"',
    "bash -c 'dotnet ef database update'",
    "bash <<'EOF'\nflyway migrate\nEOF",
]

ALLOW = [
    'dotnet test',
    'dotnet build && dotnet test --filter "FullyQualifiedName~OrderTests"',
    'dotnet ef migrations add AddOrderIndex',
    'dotnet ef migrations script --idempotent -o out.sql',
    'dotnet ef database update --connection "Server=localhost,1433;Database=app;User Id=sa;Password=x"',
    'dotnet ef database update --connection "Server=(localdb)\\\\mssqllocaldb;Database=app"',
    'dotnet ef database update --connection "Host=127.0.0.1;Port=5432;Database=app"',
    'dotnet ef database update --connection "Data Source=app.db"',
    'ConnectionStrings__Default="Server=localhost;Database=x" dotnet ef database update',
    'flyway info',
    'flyway validate',
    'flyway -url=jdbc:postgresql://localhost:5432/app migrate',
    'flyway -url=jdbc:tc:postgresql:16:///app migrate',
    'liquibase --url=jdbc:h2:mem:test update',
    'liquibase update-sql --url=jdbc:postgresql://prod/app',
    'liquibase status',
    'docker run --rm flyway/flyway -url=jdbc:postgresql://host.docker.internal:5432/app migrate',
    './gradlew test --tests "*OrderServiceTest*"',
    './gradlew spotlessCheck',
    './gradlew updateDependencies',
    'mvn -Dtest=OrderServiceTest test',
    './mvnw flyway:info',
    'SPRING_PROFILES_ACTIVE=local ./gradlew bootRun',
    'java -jar app.jar --spring.profiles.active=dev',
    'ASPNETCORE_ENVIRONMENT=Development dotnet run',
    'grep -rn "SPRING_PROFILES_ACTIVE=prod" .',
    'echo "dotnet ef database update 는 운영에서 금지"',
    'git commit -m "flyway migrate 안내 추가"',
    "cat > docs/run.md <<'EOF'\nSPRING_PROFILES_ACTIVE=prod java -jar app.jar\nEOF",
    'ls -la && cat README.md',
    'apt-get update',
    'npm run build',
]


def run(payload, env=None):
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    r = subprocess.run([sys.executable, HOOK], input=raw, capture_output=True, text=True,
                       env=dict(os.environ, **(env or {})), timeout=20)
    assert r.returncode == 0, r.stderr
    if not r.stdout.strip():
        return "allow"
    out = json.loads(r.stdout)["hookSpecificOutput"]
    assert out["hookEventName"] == "PreToolUse"
    return out["permissionDecision"] + ": " + out["permissionDecisionReason"]


class GuardProd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(cls.tmp, ".git"))
        os.makedirs(os.path.join(cls.tmp, "src", "Api"))

    def both(self, cmd, cwd=None):
        cwd = cwd or self.tmp
        claude = run({"tool_name": "Bash", "tool_input": {"command": cmd, "description": "x"}, "cwd": cwd})
        codex = run({"tool_name": "shell", "tool_input": {"command": ["bash", "-lc", cmd]}, "cwd": cwd})
        return claude, codex

    def test_deny(self):
        for cmd in DENY:
            for fmt, res in zip(("claude", "codex"), self.both(cmd)):
                with self.subTest(cmd=cmd, fmt=fmt):
                    self.assertTrue(res.startswith("deny"), res)

    def test_allow(self):
        for cmd in ALLOW:
            for fmt, res in zip(("claude", "codex"), self.both(cmd)):
                with self.subTest(cmd=cmd, fmt=fmt):
                    self.assertEqual(res, "allow")

    def test_secret_not_echoed(self):
        res = run({"tool_name": "Bash", "tool_input": {"command":
                   'dotnet ef database update --connection "Server=prod;Password=Sup3rS3cret"'}, "cwd": self.tmp})
        self.assertIn("'prod'", res)
        self.assertNotIn("Sup3rS3cret", res)

    def test_codex_argv_without_shell(self):
        res = run({"tool_name": "shell", "tool_input": {"command": [
            "dotnet", "ef", "database", "update", "--connection", "Server=prod;Database=x"]}, "cwd": self.tmp})
        self.assertTrue(res.startswith("deny"), res)
        res = run({"tool_name": "shell", "tool_input": {"command": [
            "dotnet", "ef", "database", "update", "--connection", "Server=localhost;Database=x"]}, "cwd": self.tmp})
        self.assertEqual(res, "allow")

    def test_fail_closed_inputs(self):
        self.assertTrue(run("not json").startswith("deny"))
        self.assertTrue(run("[1,2]").startswith("deny"))
        self.assertTrue(run({"tool_name": "Bash", "tool_input": {}}).startswith("deny"))
        self.assertTrue(run({"tool_name": "shell", "tool_input": {"command": 3}}).startswith("deny"))
        self.assertTrue(run({"tool_name": "exec_command", "tool_input": "flyway migrate"}).startswith("deny"))

    def test_non_exec_tools_pass(self):
        patch = "*** Begin Patch\n*** Add File: run.sh\n+SPRING_PROFILES_ACTIVE=prod java -jar app.jar\n*** End Patch"
        self.assertEqual(run({"tool_name": "apply_patch", "tool_input": {"input": patch}}), "allow")
        self.assertEqual(run({"tool_name": "Write", "tool_input": {"file_path": "a.sh",
                                                                    "content": "flyway migrate"}}), "allow")
        self.assertEqual(run({"tool_name": "mcp__db__query", "tool_input": {"sql": "select 1"}}), "allow")

    def test_off_switch_only_from_hook_env(self):
        self.assertEqual(run({"tool_name": "Bash", "tool_input": {"command": "flyway migrate"}},
                             env={"KNACK_GUARD_PROD": "off"}), "allow")
        res = run({"tool_name": "Bash", "tool_input": {"command": "KNACK_GUARD_PROD=off flyway migrate"}})
        self.assertTrue(res.startswith("deny"), res)

    def test_safe_hosts_exact_match(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, ".git"))
        os.makedirs(os.path.join(d, ".knack"))
        with open(os.path.join(d, ".knack", "safe-db-hosts"), "w") as f:
            f.write("# docker compose 서비스\nmssql\n*.corp\n")
        ok = 'dotnet ef database update --connection "Server=mssql,1433;Database=x"'
        self.assertEqual(self.both(ok, d), ("allow", "allow"))
        res = self.both('flyway -url=jdbc:postgresql://db.corp/app migrate', d)
        self.assertTrue(all(r.startswith("deny") for r in res), res)

    def test_scripts(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, ".git"))
        with open(os.path.join(d, "migrate.sh"), "w") as f:
            f.write("#!/bin/bash\nset -e\nflyway -url=jdbc:postgresql://prod/app migrate\n")
        with open(os.path.join(d, "local.sh"), "w") as f:
            f.write("#!/bin/bash\nflyway -url=jdbc:postgresql://localhost/app migrate\n")
        with open(os.path.join(d, "nested.sh"), "w") as f:
            f.write("#!/bin/sh\n./migrate.sh\n")
        with open(os.path.join(d, "big.sh"), "w") as f:
            f.write("#!/bin/bash\n" + "# x\n" * 70000 + "flyway migrate\n")
        for cmd in ("./migrate.sh", "bash migrate.sh", "source ./migrate.sh", "./nested.sh", "./big.sh"):
            with self.subTest(cmd=cmd):
                self.assertTrue(all(r.startswith("deny") for r in self.both(cmd, d)), cmd)
        self.assertEqual(self.both("./local.sh", d), ("allow", "allow"))
        self.assertEqual(self.both("./missing.sh", d), ("allow", "allow"))

    def test_gradle_generic_liquibase_tasks(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, ".git"))
        self.assertTrue(all(r.startswith("deny") for r in self.both("./gradlew update", d)))  # 빌드 파일 없음
        with open(os.path.join(d, "build.gradle.kts"), "w") as f:
            f.write('plugins { java }\n')
        self.assertEqual(self.both("./gradlew update", d), ("allow", "allow"))
        with open(os.path.join(d, "build.gradle.kts"), "w") as f:
            f.write('plugins { id("org.liquibase.gradle") version "2.2.0" }\n')
        self.assertTrue(all(r.startswith("deny") for r in self.both("./gradlew update", d)))
        self.assertEqual(self.both("./gradlew updateSQL", d), ("allow", "allow"))
        self.assertEqual(self.both("./gradlew update -Dliquibase.url=jdbc:postgresql://localhost/app", d),
                         ("allow", "allow"))

    def test_parser_missing_fails_closed(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "guard-prod-ops"))
        dst = os.path.join(d, "guard-prod-ops", "guard_prod.py")
        with open(HOOK) as src, open(dst, "w") as f:
            f.write(src.read())
        r = subprocess.run([sys.executable, dst], input="{}", capture_output=True, text=True, timeout=20)
        self.assertIn('"deny"', r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
