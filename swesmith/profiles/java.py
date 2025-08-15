import re

from dataclasses import dataclass, field
from swesmith.profiles.base import RepoProfile, registry


import docker
import re
from dataclasses import dataclass, field
from pathlib import Path

from swebench.harness.constants import (
    FAIL_TO_PASS,
    PASS_TO_PASS,
    KEY_INSTANCE_ID,
    TestStatus,
)
from swebench.harness.docker_build import build_image as build_image_sweb
from swebench.harness.dockerfiles import get_dockerfile_env
from swesmith.constants import LOG_DIR_ENV, ENV_NAME


@dataclass
class JavaProfile(RepoProfile):
    """
    Profile for Java repositories.

    This class provides Java-specific defaults and functionality for
    repository profiles, including Java/Gradle build steps.
    """

    java_version: str = "8"
    build_cmds: list[str] = field(
        default_factory=lambda: [
            "gradle build"
        ]
    )
    test_cmd: str = (
        "gradle test --info --no-daemon"
    )
    exts: list[str] = field(default_factory=lambda: [".java"])

    def get_test_files(self, instance: dict) -> tuple[list[str], list[str]]:
        assert FAIL_TO_PASS in instance and PASS_TO_PASS in instance, (
            f"Instance {instance[KEY_INSTANCE_ID]} missing required keys {FAIL_TO_PASS} or {PASS_TO_PASS}"
        )
        # For Java, test identifiers might be package.ClassName#method
        _helper = lambda tests: sorted(list(set([x.split("#", 1)[0] for x in tests])))
        return _helper(instance[FAIL_TO_PASS]), _helper(instance[PASS_TO_PASS])

    def build_image(self):
        BASE_IMAGE_KEY = "anirudhkhatry/revamp_image"  # replace with your built Java image tag
        HEREDOC_DELIMITER = "EOF_59812759871"

        client = docker.from_env()
        with open(self._env_yml) as f:
            reqs = f.read()

        setup_commands = [
            "#!/bin/bash",
            "set -euxo pipefail",
            f"git clone -o origin https://github.com/{self.mirror_name} /{ENV_NAME}",
            f"cd /{ENV_NAME}",
            # optional: environment file for Java-specific dependencies
            f"cat <<'{HEREDOC_DELIMITER}' > java_env_info.txt\n{reqs}\n{HEREDOC_DELIMITER}",
            "echo \"Java version: $(java -version)\"",
            "echo \"Gradle version: $(gradle --version)\"",
            "echo \"JBMC version: $(jbmc --version)\""
        ] + self.build_cmds
        dockerfile = get_dockerfile_env(
            self.pltf, self.arch, "java", base_image_key=BASE_IMAGE_KEY
        )

        build_image_sweb(
            image_name=self.image_name,
            setup_scripts={"setup_env.sh": "\n".join(setup_commands) + "\n"},
            dockerfile=dockerfile,
            platform=self.pltf,
            client=client,
            build_dir=LOG_DIR_ENV / self.repo_name,
        )

    def log_parser(self, log: str) -> dict[str, str]:
        """
        Parser for JBMC output.

        Captures lines like:
        [function Main.func] SUCCESS
        [function Main.func] FAILURE
        [Main.func.assertion.1] SUCCESS
        [Main.func.assertion.2] FAILURE
        """
        test_status_map = {}
        # Matches "[something] SUCCESS" or "[something] FAILURE"
        pattern = re.compile(r"\[(.+?)\]\s+(SUCCESS|FAILURE)")

        for line in log.splitlines():
            match = pattern.search(line)
            if match:
                test_name, status = match.groups()
                test_status_map[test_name] = status

        return test_status_map

    @property
    def _env_yml(self) -> Path:
        return LOG_DIR_ENV / self.repo_name / f"javaenv_{self.repo_name}.yml"
@dataclass
class Gsondd2fe59c(JavaProfile):
    owner: str = "google"
    repo: str = "gson"
    commit: str = "dd2fe59c0d3390b2ad3dd365ed6938a5c15844cb"
    test_cmd: str = "mvn test -B -T 1C -Dsurefire.useFile=false -Dsurefire.printSummary=true -Dsurefire.reportFormat=plain"
    eval_sets: set[str] = field(
        default_factory=lambda: {"SWE-bench/SWE-bench_Multilingual"}
    )

    @property
    def dockerfile(self):
        return f"""FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
RUN apt-get update && apt-get install -y git openjdk-11-jdk
RUN apt-get install -y maven
RUN git clone https://github.com/{self.mirror_name} /testbed
WORKDIR /testbed
RUN mvn clean install -B -pl gson -DskipTests -am
"""

    def log_parser(self, log: str) -> dict[str, str]:
        test_status_map = {}
        pattern = r"^\[(INFO|ERROR)\]\s+(.*?)\s+--\s+Time elapsed:\s+([\d.]+)\s"
        for line in log.split("\n"):
            if line.endswith("<<< FAILURE!") and line.startswith("[ERROR]"):
                test_name = re.match(pattern, line)
                if test_name is None:
                    continue
                test_status_map[test_name.group(2)] = TestStatus.FAILED.value
            elif (
                any([line.startswith(s) for s in ["[INFO]", "[ERROR]"]])
                and "Time elapsed:" in line
            ):
                test_name = re.match(pattern, line)
                if test_name is None:
                    continue
                test_status_map[test_name.group(2)] = TestStatus.PASSED.value
        return test_status_map


# Register all Java profiles with the global registry
for name, obj in list(globals().items()):
    if (
        isinstance(obj, type)
        and issubclass(obj, JavaProfile)
        and obj.__name__ != "JavaProfile"
    ):
        registry.register_profile(obj)
