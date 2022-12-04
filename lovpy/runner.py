from pathlib import Path

from lovpy.importer.gherkin_importer import GherkinImporter
from lovpy.logic.next_theorem_selectors import default_theorem_selector
from lovpy.logic.properties import RuleSet
from lovpy.monitor.program import VerificationConfiguration, Program


def run(script: Path, *args, gherkin_path: Path = Path.cwd()) -> None:
    """Runs a script under verification.

    :param script: Entry point script for the python program to be verified.
    :type script: Path
    :param gherkin_path: Root of the directory tree to be searched for gherkin files.
       Default value is set to current working directory.
    :type gherkin_path: Path
    """
    config: VerificationConfiguration = VerificationConfiguration(default_theorem_selector)
    rules: list[RuleSet] = GherkinImporter().discover(gherkin_path).import_rules()
    program: Program = Program(script, config)
    for group in rules:
        program.add_monitored_rules(group)
    program(args)
