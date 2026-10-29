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
        write(self.d, "api/build.gradle.kts", 'plugins {\n    java\n    id("org.springframework.boot")\n}\n'
                                              'dependencies { implementation("org.flywaydb:flyway-core")\n'
                                              ' testImplementation("org.testcontainers:postgresql") }')
        write(self.d, "api/src/main/resources/db/migration/V1__init.sql", "create table t(id int);")
        r = detect(self.d)
        self.assertEqual(r["schema_version"], 1)
        self.assertEqual(len(r["units"]), 1, "하위 모듈은 별도 단위가 아니다")
        u = r["units"][0]
        self.assertEqual((u["kind"], u["run_dir"], u["wrapper"]), ("gradle", ".", "./gradlew"))
        self.assertEqual(u["commands"]["test"], "./gradlew test")
        self.assertEqual(u["commands"]["single_test"], "./gradlew <모듈>:test --tests '<패키지.클래스명>'")
        self.assertEqual(u["modules"], [":api"])
        self.assertEqual(u["commands"]["format"]["check"], "./gradlew spotlessCheck")
        self.assertEqual(u["migration"]["tool"], "flyway")
        self.assertTrue(u["migration"]["testcontainers_dependency"])
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
        self.assertTrue(m["testcontainers_dependency"] and m["dotnet_ef_local_tool"])
        self.assertEqual(m["tests_call"], {"migrate": False, "ensure_created": False})

    def test_gradle_comment_is_not_plugin_evidence(self):
        write(self.d, "build.gradle", "plugins { id 'base' }\n// spotless checkstyle flyway\n/* id 'java' */")
        u, = detect(self.d)["units"]
        c = u["commands"]
        self.assertEqual((c["compile"], c["test"], c["single_test"], c["full"], c["format"], c["lint"]),
                         (None,) * 6, "주석·java 플러그인 없는 빌드에서 태스크를 지어내지 않는다")
        self.assertIsNone(u["migration"]["tool"])
        self.assertIn("note", u)

    def test_gradle_declared_but_not_applied_is_not_evidence(self):
        write(self.d, "build.gradle", "plugins {\n  id 'org.springframework.boot' version '3.3.0'\n"
                                      "  id 'java' apply false\n  id 'com.diffplug.spotless' version '6' apply false\n}\n"
                                      "def hint = 'com.diffplug.spotless'")
        c = detect(self.d)["units"][0]["commands"]
        self.assertEqual((c["test"], c["format"]), (None, None), "Boot 단독·apply false·문자열은 근거가 아니다")

    def test_gradle_kotlin_android_is_not_jvm_evidence(self):
        write(self.d, "build.gradle.kts", 'plugins { id("org.jetbrains.kotlin.android")\n'
                                          ' id("org.jetbrains.kotlin.plugin.spring") }')
        u, = detect(self.d)["units"]
        self.assertIsNone(u["commands"]["test"])
        self.assertIn("Android", u["note"])

    def test_gradle_comment_does_not_eat_next_file(self):
        write(self.d, "settings.gradle", "include 'a'")
        write(self.d, "build.gradle", "// root, no newline at end")
        write(self.d, "a/build.gradle", "plugins { id 'java' }")
        self.assertEqual(detect(self.d)["units"][0]["commands"]["test"], "gradle test")

    def test_gradle_multiline_include(self):
        write(self.d, "settings.gradle.kts", 'include(\n    "api",\n    "empty"\n)')
        write(self.d, "build.gradle.kts", "plugins { java }")
        u, = detect(self.d)["units"]
        self.assertEqual(u["modules"], [":api", ":empty"])
        self.assertIn("<모듈>:test", u["commands"]["single_test"])

    def test_gradle_convention_plugin_in_buildsrc(self):
        write(self.d, "settings.gradle.kts", 'include("app")')
        write(self.d, "app/build.gradle.kts", 'plugins { id("my.java-conventions") }')
        write(self.d, "buildSrc/src/main/kotlin/my.java-conventions.gradle.kts", "plugins {\n    java\n    checkstyle\n}")
        c = detect(self.d)["units"][0]["commands"]
        self.assertEqual((c["test"], c["lint"]), ("gradle test", "gradle checkstyleMain"))

    def test_maven_xml_comment_is_not_evidence(self):
        write(self.d, "pom.xml", "<project><!-- spotless-maven-plugin flyway --></project>")
        u, = detect(self.d)["units"]
        self.assertIsNone(u["commands"]["format"])
        self.assertIsNone(u["migration"]["tool"])

    def test_dotnet_path_with_space_is_quoted(self):
        write(self.d, "My App.sln", 'Project("{x}") = "Api", "Api\\Api.csproj", "{1}"\n')
        write(self.d, "Api/Api.csproj", "<Project/>")
        u, = detect(self.d)["units"]
        self.assertEqual(u["commands"]["compile"], "dotnet build 'My App.sln'")

    def test_dotnet_ef_sqlite_and_ensure_created(self):
        write(self.d, "Api/Api.csproj", '<PackageReference Include="Microsoft.EntityFrameworkCore.Sqlite"/>'
                                        '<PackageReference Include="Microsoft.EntityFrameworkCore.Design"/>')
        write(self.d, "Api.Tests/Api.Tests.csproj", '<PackageReference Include="Microsoft.NET.Test.Sdk"/>'
                                                    '<ProjectReference Include="..\\Api\\Api.csproj"/>')
        write(self.d, "Api.Tests/DbFixture.cs", "db.Database.EnsureCreated();")
        api = [u for u in detect(self.d)["units"] if u["run_dir"] == "Api"][0]
        self.assertEqual(api["migration"]["ef_providers"], ["sqlite"])
        both = os.path.join(self.d, "Both.sln")
        write(self.d, "Both.sln", 'Project("{x}") = "Api", "Api\\Api.csproj", "{1}"\n'
                                  'Project("{x}") = "T", "Api.Tests\\Api.Tests.csproj", "{2}"\n')
        u, = detect(self.d)["units"]
        self.assertEqual(u["migration"]["tests_call"], {"migrate": False, "ensure_created": True})
        self.assertTrue(os.path.isfile(both))

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
        write(self.d, "build/pom.xml", "<project/>")  # 빌드 산출물 폴더는 건너뛴다(JVM 루트 밖)
        write(self.d, "backend/target/x/pom.xml", "<project><artifactId>flyway-core</artifactId></project>")
        write(self.d, "gateway/obj/Gen.csproj", "<Project/>")
        kinds = sorted((u["kind"], u["run_dir"]) for u in detect(self.d)["units"])
        self.assertEqual(kinds, [("dotnet", "gateway"), ("maven", "backend")])
        mvn = [u for u in detect(self.d)["units"] if u["kind"] == "maven"][0]
        self.assertIsNone(mvn["migration"]["tool"], "Maven 단위 안의 target/ 은 읽지 않는다")

    def test_checkout_path_with_skip_dir_name(self):
        repo = os.path.join(self.d, "build", "packages", "repo")
        write(repo, "pom.xml", "<project><modules><module>child</module></modules></project>")
        write(repo, "child/pom.xml", "<project><artifactId>spotless-maven-plugin</artifactId>"
                                     "<artifactId>liquibase-core</artifactId></project>")
        u, = detect(repo)["units"]
        self.assertEqual(u["commands"]["format"]["check"], "mvn -B spotless:check", "체크아웃 경로와 무관해야 한다")
        self.assertEqual(u["migration"]["tool"], "liquibase")

    def test_gradle_include_build_is_not_module_and_toml_is_not_evidence(self):
        write(self.d, "settings.gradle", "includeBuild('tools')")
        write(self.d, "build.gradle", "plugins { id 'java' }")
        write(self.d, "gradle/libs.versions.toml", 'spotless = { id = "com.diffplug.spotless" }')
        u, = detect(self.d)["units"]
        self.assertEqual(u["modules"], [])
        self.assertEqual(u["commands"]["single_test"], "gradle test --tests '<패키지.클래스명>'")
        self.assertIsNone(u["commands"]["format"], "버전 카탈로그 선언만으로는 플러그인 적용이 아니다")

    def test_dotnet_test_project_name_boundary(self):
        write(self.d, "Contest/Contest.csproj", "<Project/>")
        u, = detect(self.d)["units"]
        self.assertEqual(u["test_projects"], [])

    def test_not_a_directory(self):
        p = subprocess.run([sys.executable, DETECT, os.path.join(self.d, "none")], capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)
        self.assertIn("error", json.loads(p.stdout))


if __name__ == "__main__":
    unittest.main(verbosity=1)
