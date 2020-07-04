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

        current_deps = self.poetry.package.requires
        current_dev_deps = self.poetry.package.dev_requires

        upgradable = self.find_upgradable(current_deps)
        upgradable_dev = self.find_upgradable(current_dev_deps)

        def makeChoices(pairs, section):
            return [Separator(section)] + [
                {
                    "name": src.pretty_name
                    + " "
                    + src.pretty_constraint
                    + " ❯ "
                    + target.pretty_version
                    + " ("
                    + src.python_versions
                    + ")",
                    "value": [
                        src.name,
                        target.version.text,
                        src.python_versions,
                        section,
                    ],
                }
                for src, target in upgradable
            ]

        choices = makeChoices(upgradable, "dependencies") + makeChoices(
            upgradable_dev, "devDependencies"
        )

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

        if not answers or len(answers["pkgsToUpgrade"]) == 0:
            return

        poetry = content["tool"]["poetry"]
        for package_name, new_version, python_version, scope in answers[
            "pkgsToUpgrade"
        ]:
            # ? always caret version. or should be tilde?
            scoped = poetry[scope]
            for k in scoped:
                if k == "python" or k != package_name:
                    continue
                val = scoped[k]
                if isinstance(val, str):
                    scoped[k] = "^" + new_version
                elif isinstance(val, list):
                    for item in val:
                        if "python" in item and item["python"] != python_version:
                            continue
                        item["version"] = "^" + new_version

        # Write back
        self.poetry.file.write(content)

        # TODO: print nice message

    def find_upgradable(self, deps):
        pkgs = [self.find_latest(dep) for dep in deps]
        return filter(lambda s: s[1].version > s[0].constraint.max, zip(deps, pkgs),)

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
