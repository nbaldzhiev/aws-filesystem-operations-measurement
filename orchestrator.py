"""This module contains the implementation of an orchestrator class."""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import paramiko
from botocore.config import Config

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
        (AWSEC2FreeTierAMIs.RHEL_8, DefaultAMIUsernames.RHEL),
        (AWSEC2FreeTierAMIs.UBUNTU_SERVER_22_04, DefaultAMIUsernames.UBUNTU),
    )

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
        self.amis_to_create = amis_to_create
        # A list of dictionaries where each dict contains the created instance object and the SSH
        # client object with an established SSH connection to that instance
        self.created_instances_with_ssh_conns: List[Dict] = []

    def __enter__(self) -> Orchestrator:
        """Creates the VMs based on the AMIs provided in self.amis_to_create, establishes a SSH
        connection to each instance, and returns the class instance upon entering the class as a
        context manager"""
        for ami in self.amis_to_create:
            instance = self.ec2.create_instance(image_id=ami[0])
            ssh_client = Orchestrator._prepare_ssh_client_obj()
            ssh_client.connect(
                hostname=instance.public_dns_name,
                username=ami[1].value,
                key_filename=instance.key_name + ".pem",
            )
            logging.info(
                "Successfully established a SSH connection to instance: %s with public DNS of: %s.",
                instance.id,
                instance.public_dns_name,
            )
            self.created_instances_with_ssh_conns.append(
                {"instance": instance, "ssh_client": ssh_client}
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Closes all SSH sessions, terminates all created EC2 instances, deletes their security
        group and key pairs upon exiting the context manager."""
        if self.created_instances_with_ssh_conns:
            for instance in self.created_instances_with_ssh_conns:
                instance["ssh_client"].close()
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
