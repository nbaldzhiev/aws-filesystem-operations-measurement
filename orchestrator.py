"""This module contains the implementation of an orchestrator class."""
from __future__ import annotations

import logging
import os
import time
from typing import Dict, List, Optional, Tuple

import paramiko
from botocore.config import Config
from scp import SCPClient

from settings import LOGGING_LEVEL
from utilities import EC2, AWSEC2FreeTierAMIs, DefaultAMIUsernames

logging.basicConfig(level=LOGGING_LEVEL)


class Orchestrator:
    """This class serves as the orchestrator for performing the filesystem operations."""

    # The default AMIs to create. A tuple of tuples where each tuple element contains two elements:
    # the AMI ID as an AWSEC2FreeTierAMIs attribute and the default OS username as a
    # DefaultAMIUsernames attribute
    AMIS_TO_CREATE = (
        (AWSEC2FreeTierAMIs.AMAZON_LINUX_2, DefaultAMIUsernames.AMAZON_LINUX),
    )
    PERFORM_MEASUREMENTS_BASH_SCRIPT = "perform_measurements.sh"
    SETUP_CRON_BASH_SCRIPT = "setup_cron.sh"
    RESULTS_FILENAME = "results.txt"
    # Used as a timeout for both the creation of the file and for the completion of all operations
    RESULTS_TIMEOUT_SEC = 600
    RESULTS_INTERVAL_SEC = 5

    def __init__(
        self,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_region_name: Optional[str] = None,
        config: Optional[Config] = None,
        # A tuple of tuples where each tuple element contains two elements:
        # the AMI ID as an AWSEC2FreeTierAMIs attribute and the default OS username as a
        # DefaultAMIUsernames attribute
        amis_to_create: Tuple[
            Tuple[AWSEC2FreeTierAMIs, DefaultAMIUsernames]
        ] = AMIS_TO_CREATE,
    ):
        self.ec2: EC2 = EC2(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_region_name=aws_region_name,
            config=config,
        )
        self._amis_to_create = amis_to_create
        # A list of dictionaries where each dict contains the created instance object and the SSH
        # client object with an established SSH connection to that instance
        self.created_instances_with_ssh: List[Dict] = []

    def __enter__(self) -> Orchestrator:
        """Creates the VMs based on the AMIs provided in self.amis_to_create, establishes a SSH
        connection to each instance, and returns the class instance upon entering the class as a
        context manager"""
        for ami in self._amis_to_create:
            instance_ = self.ec2.create_instance(image_id=ami[0])
            ssh_client = Orchestrator._prepare_ssh_client_obj()
            ssh_client.connect(
                hostname=instance_.public_dns_name,
                username=ami[1].value,
                key_filename=instance_.key_name + ".pem",
            )
            logging.info(
                "Successfully established a SSH connection to instance: %s with public DNS of: %s.",
                instance_.id,
                instance_.public_dns_name,
            )
            self.created_instances_with_ssh.append(
                {
                    "instance": instance_,
                    "ssh_client": ssh_client,
                    "username": ami[1].value,
                }
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Closes all SSH sessions, terminates all created EC2 instances, deletes their security
        group and key pairs upon exiting the context manager."""
        if self.created_instances_with_ssh:
            for instance_ in self.created_instances_with_ssh:
                instance_["ssh_client"].close()
                logging.info(
                    "Successfully closed the SSH section of instance: %s.",
                    instance_["instance"].id,
                )
                self.ec2.terminate_instance(instance_id=instance_["instance"].id)
                self.ec2.delete_security_group(
                    # Instances used by this class would only ever be part of one security group,
                    # hence the access to the 0th index specifically
                    group_id=instance_["instance"].security_groups[0]["GroupId"]
                )
                self.ec2.delete_key_pair(key_name=instance_["instance"].key_name)

    @staticmethod
    def _prepare_ssh_client_obj() -> paramiko.SSHClient:
        """Prepares and returns a SSH client with preloaded known hosts and a pre-configured
        missing host key policy.

        Returns
        -------
        paramiko.SSHClient
            An object of type SSHClient.
        """
        ssh_client = paramiko.SSHClient()
        ssh_client.load_system_host_keys()
        # AutoAddPolicy
        ssh_client.set_missing_host_key_policy(policy=paramiko.client.AutoAddPolicy)
        return ssh_client

    @staticmethod
    def reconnect_ssh(instance_obj, username: str) -> paramiko.SSHClient:
        """Re-establishes a SSH connection to a given instance. Typical use case is after an
        instance has been rebooted.

        Parameters
        ----------
        instance_obj : ec2.Instance
            The instance to reconnect to as an ec2.Instance object.
        username : str
            The username to reconnect as.

        Returns
        -------
        paramiko.SSHClient
        """
        ssh_client = Orchestrator._prepare_ssh_client_obj()
        ssh_client.connect(
            hostname=instance_obj.public_dns_name,
            username=username,
            key_filename=instance_obj.key_name + ".pem",
        )
        logging.info(
            "Successfully reconnected via SSH to instance: %s with public DNS of: %s.",
            instance_obj.id,
            instance_obj.public_dns_name,
        )
        return ssh_client

    def transfer_bash_scripts_to_instance(
        self, instance_ssh_client: paramiko.SSHClient
    ) -> Orchestrator:
        """Transfers both bash scripts - the perform operations one and the setup cron one,
        to the instance related to the SSH session passed as a value to the parameter
        instance_ssh_client."""
        scp = SCPClient(instance_ssh_client.get_transport())
        for bash_script in (
            type(self).PERFORM_MEASUREMENTS_BASH_SCRIPT,
            type(self).SETUP_CRON_BASH_SCRIPT,
        ):
            # Give the file full access by anyone to avoid any permission issues whatsoever
            os.chmod("bash_scripts/" + bash_script, 0o0777)
            # Transfer the bash script over to the instance filesystem
            scp.put("bash_scripts/" + bash_script)
        return self

    def run_setup_cron_bash(
        self, instance_ssh_client: paramiko.SSHClient
    ) -> Orchestrator:
        """Runs the setup cron bash script on the instance related to the SSH session passed as a
        value to the parameter instance_ssh_client."""
        instance_ssh_client.exec_command(f"./{type(self).SETUP_CRON_BASH_SCRIPT}")
        return self

    def wait_for_results_file_to_be_created(
        self, instance_ssh_client: paramiko.SSHClient
    ) -> Orchestrator:
        """Waits for the results file to be created on an instance specified by its SSH client,
        which is passed as the value to the parameter instance_ssh_client."""
        timeout = time.time() + type(self).RESULTS_TIMEOUT_SEC
        while (
            instance_ssh_client.exec_command(f"cat {type(self).RESULTS_FILENAME}")[
                2
            ].readline()
            and time.time() < timeout
        ):
            time.sleep(type(self).RESULTS_INTERVAL_SEC)

        if time.time() > timeout:
            raise UserWarning("Could not wait for the results file to be created!")
        logging.info("Successfully waited for the results file to be created!")
        return self

    def wait_for_all_operations_to_complete(
        self, instance_ssh_client: paramiko.SSHClient
    ) -> Orchestrator:
        """Waits for all operations to complete on an instance specified by its SSH client,
        which is passed as the value to the parameter instance_ssh_client."""
        self.wait_for_results_file_to_be_created(
            instance_ssh_client=instance_ssh_client
        )
        timeout = time.time() + type(self).RESULTS_TIMEOUT_SEC
        while (
            "DONE!"
            not in instance_ssh_client.exec_command(
                f"cat {type(self).RESULTS_FILENAME}"
            )[1].readlines()[-1]
            and time.time() < timeout
        ):
            time.sleep(type(self).RESULTS_INTERVAL_SEC)

        if time.time() > timeout:
            raise UserWarning("Could not wait for all operations to be performed!")
        logging.info("Successfully waited for all filesystem operations to complete")
        return self

    def transfer_results_to_orchestrator_host(
        self, instance_ssh_client: paramiko.SSHClient
    ) -> Orchestrator:
        """Transfers the results.txt file from the instance to the orchestrator host in the
        same directory as this module for simplicity."""
        scp = SCPClient(instance_ssh_client.get_transport())
        hostname = ssh.exec_command("cat /etc/hostname")[1].readline().strip()
        target_filename = f"{hostname}-{type(self).RESULTS_FILENAME}"
        # Transfer the bash script over to the instance filesystem
        scp.get(type(self).RESULTS_FILENAME, target_filename)
        logging.info(
            "Transferred the results file from the instance to this orhestrator host!"
        )
        return self


with Orchestrator() as orchestrator:
    for instance in orchestrator.created_instances_with_ssh:
        orchestrator.transfer_bash_scripts_to_instance(
            instance_ssh_client=instance["ssh_client"]
        )
        orchestrator.run_setup_cron_bash(instance_ssh_client=instance["ssh_client"])
        orchestrator.ec2.reboot_instance(instance["instance"].id)
        time.sleep(30)
        ssh = orchestrator.reconnect_ssh(
            instance_obj=instance["instance"], username=instance["username"]
        )
        orchestrator.wait_for_all_operations_to_complete(instance_ssh_client=ssh)
        orchestrator.transfer_results_to_orchestrator_host(instance_ssh_client=ssh)
