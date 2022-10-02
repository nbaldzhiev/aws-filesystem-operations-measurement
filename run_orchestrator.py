"""This module contains an implementation of a Click-based function to allow for executing it as a
CLI command."""
import click

from orchestrator import Orchestrator
from utilities import ResultsFormatter


@click.command()
@click.option(
    "--human-readable",
    is_flag=True,
    default=False,
    help="Controls whether the results would be in a human readable format. If not, JSON is used."
    " Defaults to False.",
)
def run_orchestrator(human_readable: bool):
    """This function is wrapped as a Click command to allow for running the script as a command
    with command-line arguments.

    Examples
    --------
        $ python run_orchestrator.py - prints the results in a JSON format
        $ python run_orchestrator.py --human-readable - prints the results in a human-readable fmt

    """
    with Orchestrator() as orchestrator:
        for instance in orchestrator.created_instances:
            data = orchestrator.run_e2e_flow(instance=instance)
            print(
                ResultsFormatter(
                    instance_information=data["instance_info"],
                    operations_measurements=data["measurements"],
                    human_readable=human_readable,
                ).format_results()
            )


run_orchestrator()
