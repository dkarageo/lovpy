from pathlib import Path
from typing import Tuple, Optional

import click

from lovpy.runner import run
from lovpy.config import VERSION


@click.group()
def cli() -> None:
    pass


@cli.command()
@click.argument("script",
                required=True,
                type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("args", nargs=-1)
def verify(script: Path, args: Tuple[str]) -> None:
    """Executes a script under lovpy's verification."""
    print("-" * 80)
    print(f"Running {str(script)} under lovpy's verification.")
    print("-" * 80)
    run(script, args)


@cli.command()
@click.option("-a", "--arch",
              type=click.Choice(["simple", "gnn"]),
              help="Select a specific model to be trained.")
def train(arch: Optional[str]) -> None:
    """Trains the available neural architectures.

    By default, all the available neural models are trained. Providing the -a|--arch
    parameter will limit the training procedure on that specific model.
    """
    from .models.train_model import train_models

    if arch:
        train_models(arch)
    else:
        train_models()


@cli.group()
def evaluate() -> None:
    """Evaluates the installed proving systems."""
    pass


@evaluate.command("examples")
def evaluate_examples() -> None:
    """Evaluates the installed proving systems on code snippets."""
    from .evaluation.evaluate_on_examples import evaluate_proving_methods as eval_on_examples
    eval_on_examples()


@evaluate.command("synthetics")
def evaluate_synthetics() -> None:
    """Evaluates the installed proving systems on synthetic samples."""
    from .evaluation.evaluate_on_synthetics import evaluate as eval_on_synthetics
    eval_on_synthetics()


@cli.command()
def version() -> None:
    """Displays lovpy's version."""
    print(f"Lovpy version: {VERSION}")


if __name__ == "__main__":
    cli()
