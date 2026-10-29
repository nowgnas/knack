#!/usr/bin/env python3
"""stack-verify detect.py 회귀 테스트. 임시 폴더에 Gradle·Maven·.NET 픽스처를 만들어 판정을 본다."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DETECT = os.path.join(ROOT, "skills", "stack-verify", "scripts", "detect.py")


def write(base, rel, text=""):
    p = os.path.join(base, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


def detect(path):
    out = subprocess.run([sys.executable, DETECT, path], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


class StackDetect(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_gradle_multimodule(self):
        write(self.d, "gradlew")
        write(self.d, "settings.gradle.kts", 'include("api")')
        write(self.d, "build.gradle.kts", 'plugins { id("com.diffplug.spotless") }')
        write(self.d, "api/build.gradle.kts", 'dependencies { implementation("org.flywaydb:flyway-core")\n'
                                              ' testImplementation("org.testcontainers:postgresql") }')
        write(self.d, "api/src/main/resources/db/migration/V1__init.sql", "create table t(id int);")
        r = detect(self.d)
        self.assertEqual(r["schema_version"], 1)
        self.assertEqual(len(r["units"]), 1, "하위 모듈은 별도 단위가 아니다")
        u = r["units"][0]
        self.assertEqual((u["kind"], u["run_dir"], u["wrapper"]), ("gradle", ".", "./gradlew"))
        self.assertEqual(u["commands"]["test"], "./gradlew test")
        self.assertIn("--tests", u["commands"]["single_test"])
        self.assertEqual(u["commands"]["format"]["check"], "./gradlew spotlessCheck")
        self.assertEqual(u["migration"]["tool"], "flyway")
        self.assertTrue(u["migration"]["testcontainers"])
        self.assertIn(os.path.join("api", "src", "main", "resources", "db", "migration"), u["migration"]["evidence"])

    def test_maven_without_wrapper_or_formatter(self):
        write(self.d, "pom.xml", "<project><modules><module>child</module></modules></project>")
        write(self.d, "child/pom.xml", "<project><artifactId>liquibase-core</artifactId></project>")
        u, = detect(self.d)["units"]
        self.assertEqual((u["kind"], u["wrapper"]), ("maven", None))
        self.assertTrue(u["commands"]["test"].startswith("mvn "), "래퍼가 없으면 mvn")
        self.assertIn("-Dtest=", u["commands"]["single_test"])
        self.assertIsNone(u["commands"]["format"], "근거 없는 포맷터 명령은 만들지 않는다")
        self.assertEqual(u["migration"]["tool"], "liquibase")

    def test_dotnet_solution_with_ef(self):
        write(self.d, "App.sln", 'Project("{x}") = "Api", "src\\Api\\Api.csproj", "{1}"\n'
                                 'Project("{x}") = "Api.Tests", "tests\\Api.Tests\\Api.Tests.csproj", "{2}"\n')
        write(self.d, "src/Api/Api.csproj", '<PackageReference Include="Microsoft.EntityFrameworkCore.Design"/>')
        write(self.d, "src/Api/Migrations/20260101_Init.cs")
        write(self.d, "tests/Api.Tests/Api.Tests.csproj", '<PackageReference Include="Microsoft.NET.Test.Sdk"/>'
                                                          '<PackageReference Include="Testcontainers.PostgreSql"/>')
        write(self.d, ".config/dotnet-tools.json", '{"tools":{"dotnet-ef":{}}}')
        u, = detect(self.d)["units"]
        self.assertEqual(u["commands"]["test"], "dotnet test App.sln")
        self.assertIn("FullyQualifiedName~", u["commands"]["single_test"])
        self.assertEqual(u["commands"]["format"]["check"], "dotnet format App.sln --verify-no-changes")
        m = u["migration"]
        self.assertEqual(m["tool"], "ef-core")
        self.assertTrue(m["testcontainers"] and m["dotnet_ef_local_tool"])

    def test_dotnet_without_tests_has_no_test_command(self):
        write(self.d, "Lib/Lib.csproj", "<Project/>")
        u, = detect(self.d)["units"]
        self.assertEqual(u["commands"]["compile"], "dotnet build Lib.csproj")
        self.assertEqual(u["run_dir"], "Lib")
        self.assertIsNone(u["commands"]["test"])

    def test_mixed_and_empty(self):
        self.assertEqual(detect(self.d)["units"], [])
        self.assertTrue(detect(self.d)["notes"])
        write(self.d, "backend/pom.xml", "<project/>")
        write(self.d, "gateway/Gateway.csproj", "<Project/>")
        write(self.d, "backend/build/pom.xml", "<project/>")  # 빌드 산출물 폴더는 건너뛴다
        kinds = sorted((u["kind"], u["run_dir"]) for u in detect(self.d)["units"])
        self.assertEqual(kinds, [("dotnet", "gateway"), ("maven", "backend")])

    def test_not_a_directory(self):
        p = subprocess.run([sys.executable, DETECT, os.path.join(self.d, "none")], capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)
        self.assertIn("error", json.loads(p.stdout))


if __name__ == "__main__":
    unittest.main(verbosity=1)
