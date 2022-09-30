"""This module contains an implementation of a click-based function to allow for executing it as a
CLI command."""
import click

from orchestrator import Orchestrator


@click.command()
@click.option(
    "--human-readable",
    is_flag=True,
    default=False,
    help="Controls whether the results would be in a human readable format. If not, JSON is used."
    " Defaults to False.",
)
def run_orchestrator(human_readable: bool):
    """This function is wrapped as a click command to allow for running the script as a command
    with command-line arguments."""
    instance_results = {}
    with Orchestrator() as orchestrator:
        for instance in orchestrator.created_instances:
            ssh = orchestrator.connect_ssh(
                instance_obj=instance["instance"], username=instance["username"]
            )
            orchestrator.transfer_bash_scripts_to_instance(instance_ssh_client=ssh)
            orchestrator.run_setup_cron_bash(instance_ssh_client=ssh)
            orchestrator.ec2.reboot_instance(
                instance_obj=instance["instance"],
                ssh_client=ssh,
                username=instance["username"],
            )
            ssh = orchestrator.connect_ssh(
                instance_obj=instance["instance"], username=instance["username"]
            )
            orchestrator.wait_for_all_operations_to_complete(instance_ssh_client=ssh)
            instance_results[
                instance["instance"].id
            ] = orchestrator.transfer_results_to_orchestrator_host(
                instance_ssh_client=ssh, instance=instance["instance"]
            )


run_orchestrator()
