"""This module contains an implementation of the required orchestrator class."""
from __future__ import annotations

import logging
import os
import time
from re import match
from typing import Dict, List, Optional

import paramiko
from botocore.config import Config
from scp import SCPClient

from settings import (
    LOGGING_LEVEL,
    PERFORM_MEASUREMENTS_BASH_SCRIPT,
    RESULTS_FILENAME,
    SETUP_CRON_BASH_SCRIPT,
    InstanceOperationsMeasurements,
)
from utilities import EC2, AWSEC2FreeTierAMIs, DefaultAMIUsernames

logging.basicConfig(level=LOGGING_LEVEL)


class Orchestrator:
    """This class serves as the orchestrator for performing the filesystem operations."""

    DEFAULT_AMIS_TO_CREATE = [
        {
            "ami_id": AWSEC2FreeTierAMIs.AMAZON_LINUX_2,
            "username": DefaultAMIUsernames.AMAZON_LINUX,
        },
        {"ami_id": AWSEC2FreeTierAMIs.RHEL_8, "username": DefaultAMIUsernames.RHEL},
        {
            "ami_id": AWSEC2FreeTierAMIs.UBUNTU_SERVER_22_04,
            "username": DefaultAMIUsernames.UBUNTU,
        },
    ]
    # Used as a timeout for both the creation of the file and for the completion of all operations
    RESULTS_TIMEOUT_SEC = 600
    RESULTS_INTERVAL_SEC = 5

    def __init__(
        self,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_region_name: Optional[str] = None,
        config: Optional[Config] = None,
        amis_to_create: Optional[List[Dict]] = None,
    ):
        self.ec2: EC2 = EC2(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_region_name=aws_region_name,
            config=config,
        )
        self._amis_to_create = (
            amis_to_create if amis_to_create else type(self).DEFAULT_AMIS_TO_CREATE
        )
        # A list of dictionaries where each dict contains the created instance object together with
        # the username to log on the instance with
        self.created_instances: List[Dict] = []
        self.established_ssh_connections: Dict = {}

    def __enter__(self) -> Orchestrator:
        """Creates the VMs based on the AMIs provided in self._amis_to_create, establishes an SSH
        connection to each instance, and returns the class instance upon entering the class as a
        context manager."""
        for ami in self._amis_to_create:
            instance = self.ec2.create_instance(image_id=ami["ami_id"])
            logging.info(
                "Successfully established a SSH connection to instance: %s with public DNS of: %s.",
                instance.id,
                instance.public_dns_name,
            )
            self.created_instances.append({"instance": instance, "username": ami["username"].value})
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Closes all SSH sessions, terminates all created EC2 instances, deletes their security
        group and key pairs upon exiting the context manager."""
        for instance in self.created_instances:
            if instance["instance"].id in self.established_ssh_connections:
                self.established_ssh_connections[instance["instance"].id]["ssh_client"].close()
            logging.info(
                "Successfully closed the SSH section of instance: %s.",
                instance["instance"].id,
            )
            self.ec2.terminate_instance(instance_id=instance["instance"].id)
            self.ec2.delete_security_group(
                # Instances used by this class would only ever be part of one security group,
                # hence the access to the 0th index specifically
                group_id=instance["instance"].security_groups[0]["GroupId"]
            )
            self.ec2.delete_key_pair(key_name=instance["instance"].key_name)

    @staticmethod
    def _prepare_ssh_client_obj() -> paramiko.SSHClient:
        """Prepares and returns an SSH client with preloaded known hosts and a pre-configured
        missing host key policy.

        Returns
        -------
        paramiko.SSHClient
        """
        ssh_client = paramiko.SSHClient()
        ssh_client.load_system_host_keys()
        ssh_client.set_missing_host_key_policy(policy=paramiko.client.AutoAddPolicy)

        return ssh_client

    def connect_ssh(self, instance_obj, username: str) -> paramiko.SSHClient:
        """Establishes an SSH connection to a given instance and returns a SSHClient object.

        Parameters
        ----------
        instance_obj : ec2.Instance
            The instance to connect to as an ec2.Instance object.
        username : str
            The username to connect as.

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
            "Successfully connected via SSH to instance: %s with public DNS of: %s.",
            instance_obj.id,
            instance_obj.public_dns_name,
        )
        self.established_ssh_connections[instance_obj.id] = {
            "ssh_client": ssh_client,
            "username": username,
        }

        return ssh_client

    def transfer_bash_scripts_to_instance(
        self, instance_ssh_client: paramiko.SSHClient
    ) -> Orchestrator:
        """Transfers both bash scripts - the perform operations one and the setup cron one,
        to the instance related to the SSH session passed to instance_ssh_client."""
        scp = SCPClient(instance_ssh_client.get_transport())
        for bash_script in (PERFORM_MEASUREMENTS_BASH_SCRIPT, SETUP_CRON_BASH_SCRIPT):
            # Give the file full access by anyone to avoid any permission issues whatsoever
            os.chmod("bash_scripts/" + bash_script, 0o0777)
            # Transfer the script over to the instance at the home of the default user
            scp.put("bash_scripts/" + bash_script)

        return self

    def run_setup_cron_bash_script(self, instance_ssh_client: paramiko.SSHClient) -> Orchestrator:
        """Runs the setup cron bash script on the instance related to the SSH session passed to
        the parameter instance_ssh_client."""
        instance_ssh_client.exec_command(f"./{SETUP_CRON_BASH_SCRIPT}")
        return self

    def wait_for_results_file_to_be_created(
        self, instance_ssh_client: paramiko.SSHClient
    ) -> Orchestrator:
        """Waits for the results file to be created on an instance specified by its SSH client,
        which is passed to the parameter instance_ssh_client."""
        timeout = time.time() + type(self).RESULTS_TIMEOUT_SEC
        while (
            # stderr is at the last index of exec_command's returned 3-tuple
            instance_ssh_client.exec_command(f"cat {RESULTS_FILENAME}")[-1].readline()
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
        which is passed to the parameter instance_ssh_client."""
        self.wait_for_results_file_to_be_created(instance_ssh_client=instance_ssh_client)

        timeout = time.time() + type(self).RESULTS_TIMEOUT_SEC
        while (
            # The word DONE is always the last line of a results file when measurements are done
            "DONE"
            not in instance_ssh_client.exec_command(f"cat {RESULTS_FILENAME}")[
                1  # stdin
            ].readlines()[-1]
            and time.time() < timeout
        ):
            time.sleep(type(self).RESULTS_INTERVAL_SEC)

        if time.time() > timeout:
            raise UserWarning("Could not wait for all operations to be performed!")
        logging.info("Successfully waited for all filesystem operations to complete")

        return self

    @staticmethod
    def transfer_results_to_orchestrator_host(
        instance_ssh_client: paramiko.SSHClient,
    ) -> str:
        """Transfers the results.txt file from the instance to the orchestrator host in the
        same directory as this module.

        Returns
        -------
        str
            The name of the transferred results file.
        """
        scp = SCPClient(instance_ssh_client.get_transport())
        hostname = instance_ssh_client.exec_command("cat /etc/hostname")[1].readline().strip()
        target_filename = f"{hostname}-{RESULTS_FILENAME}"
        scp.get(RESULTS_FILENAME, target_filename)
        logging.info("Transferred the results file from the instance to the orchestrator host!")

        return target_filename

    @staticmethod
    def get_measurements_from_file(filename: str) -> InstanceOperationsMeasurements:
        """Parses the results file and returns a InstanceOperationsMeasurements object with the
        operations measurements."""
        measurements = {}
        with open(filename, "r") as f:
            results_file_content = f.readlines()
            # 0:-1 to exclude the last line, which is the DONE signal
            for line in results_file_content[0:-1]:
                operation, elapsed = match(r"([A-Z]+): ([0-9]+)ms", line).groups()
                measurements[operation] = elapsed
        # Delete the file after retrieving the results from it
        os.remove(filename)

        return InstanceOperationsMeasurements(
            create_elapsed_ms=int(measurements["CREATE"]),
            copy_elapsed_ms=int(measurements["COPY"]),
            delete_elapsed_ms=int(measurements["DELETE"]),
        )

    def run_e2e_flow(self, instance) -> Dict:
        """Runs the end to end flow, which goes through all steps to run the operations measurements
         on a given instance and retrieve the results from the instance to the orchestrator host.

        Parameters
        ----------
        instance : ec2.Instance
            The ec2.Instance object where the operations measurements are to be performed and
            retrieved from.

        Returns
        -------
        Dict
            A dictionary containing two key-value pairs: the parsed operations measurements and
            the instance information.
        """
        ssh = self.connect_ssh(instance_obj=instance["instance"], username=instance["username"])
        self.transfer_bash_scripts_to_instance(instance_ssh_client=ssh).run_setup_cron_bash_script(
            instance_ssh_client=ssh
        ).ec2.reboot_instance(
            instance_obj=instance["instance"],
            ssh_client=ssh,
            username=instance["username"],
        )

        ssh = self.connect_ssh(instance_obj=instance["instance"], username=instance["username"])
        results_filename = self.wait_for_all_operations_to_complete(
            instance_ssh_client=ssh
        ).transfer_results_to_orchestrator_host(instance_ssh_client=ssh)

        measurements = self.get_measurements_from_file(filename=results_filename)
        instance_info = self.ec2.get_instance_information(instance=instance["instance"])

        return {"measurements": measurements, "instance_info": instance_info}
