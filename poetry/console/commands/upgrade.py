from clikit.io.null_io import NullIO

from poetry.core.semver import parse_constraint
from poetry.puzzle.provider import Provider
from poetry.version.version_selector import VersionSelector
from PyInquirer import Separator
from PyInquirer import prompt

from .env_command import EnvCommand
from .init import InitCommand


# * STRATEGY
# current => pretty_constraints, min_version, max_version
# latest => version
# upgradable? => latest.version > current.constraint.max
# new constraint => ^latest


class UpgradeCommand(EnvCommand, InitCommand):

    name = "upgrade"
    description = "Upgrade the packages in <comment>pyproject.toml</> interactively."

    arguments = []
    options = []

    loggers = ["poetry.repositories.pypi_repository"]

    def handle(self):
        content = self.poetry.file.read()

        # TODO: handle this kind of constraint
        # keyring = [
        #     { version = "^18.0.1", python = "~2.7 || ~3.4" },
        #     { version = "^20.0.1", python = "^3.5" }
        # ]
        # ? maybe these complex constraint should not be selected
        current_deps = self.poetry.package.requires
        current_dev_deps = self.poetry.package.dev_requires

        latest_packages = [self.find_latest(dep) for dep in current_deps]
        latest_dev_packages = [self.find_latest(dep) for dep in current_dev_deps]
        upgradable = filter(
            lambda s: s[1].version > s[0].constraint.max,
            zip(current_deps, latest_packages),
        )
        upgradable_dev = filter(
            lambda s: s[1].version > s[0].constraint.max,
            zip(current_dev_deps, latest_dev_packages),
        )

        choices = [Separator("dependencies")]
        choices += [
            {
                "name": src.pretty_name
                + " "
                + src.pretty_constraint
                + " ❯ "
                + target.pretty_version,
                "value": [target, "dependencies"],
            }
            for src, target in upgradable
        ]

        choices.append(Separator("devDependencies"))
        choices += [
            {
                "name": src.pretty_name
                + " "
                + src.pretty_constraint
                + " ❯ "
                + target.pretty_version,
                "value": [target, "devDependencies"],
            }
            for src, target in upgradable_dev
        ]

        answers = prompt(
            [
                {
                    "type": "checkbox",
                    "message": "Choose packages to upgrade",
                    "name": "pkgsToUpgrade",
                    "choices": choices,
                }
            ]
        )

        for pkg, scope in answers["pkgsToUpgrade"]:
            # ? always caret version. or should be tilde?
            content["tool"]["poetry"][scope][pkg.name] = "^" + pkg.version.text

        # Write back
        self.poetry.file.write(content)

        # TODO: print nice message

    def find_latest(self, dep):
        provider = Provider(self.poetry.package, self.poetry.pool, NullIO())

        if dep.is_vcs():
            return provider.search_for_vcs(dep)[0]
        if dep.is_file():
            return provider.search_for_file(dep)[0]
        if dep.is_directory():
            return provider.search_for_directory(dep)[0]

        constraints = parse_constraint(dep.pretty_constraint)

        name = dep.name
        selector = VersionSelector(self.poetry.pool)
        return selector.find_best_candidate(name, ">=" + constraints.min.text)


def find(f, arr):
    for i in arr:
        if f(i):
            return i
