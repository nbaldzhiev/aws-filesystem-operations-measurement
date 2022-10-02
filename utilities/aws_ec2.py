"""This module contains utility functions for operating with AWS EC2."""
import logging
import os
import stat
import time
from typing import Optional, Tuple

import boto3
import paramiko
from botocore.config import Config
from botocore.exceptions import ClientError

from settings import LOGGING_LEVEL, DefaultAWSEC2Credentials
from utilities.enums_dataclasses import (
    AWSEC2FreeTierAMIs,
    AWSEC2FreeTierInstanceTypes,
    AWSServices,
    InstanceInformation,
)

logging.basicConfig(level=LOGGING_LEVEL)


class EC2:
    """The class serves as a utility class for AWS EC2 operations needed throughout this project."""

    def __init__(
        self,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_region_name: Optional[str] = None,
        config: Optional[Config] = None,
    ):
        self.aws_access_key_id = (
            aws_access_key_id
            if aws_access_key_id
            else DefaultAWSEC2Credentials.DEFAULT_AWS_ACCESS_KEY_ID
        )
        self.aws_secret_access_key = (
            aws_secret_access_key
            if aws_secret_access_key
            else DefaultAWSEC2Credentials.DEFAULT_AWS_SECRET_ACCESS_KEY
        )
        self.aws_region_name = (
            aws_region_name if aws_region_name else DefaultAWSEC2Credentials.DEFAULT_AWS_REGION
        )
        self.config = config if config else Config(region_name=self.aws_region_name)

        self.resource = boto3.resource(
            AWSServices.EC2.value,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            config=self.config,
        )
        self.client = boto3.client(
            AWSServices.EC2.value,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            config=self.config,
        )

    def create_key_pair(
        self, key_name: Optional[str] = None, key_file_name: Optional[str] = None
    ) -> Tuple:
        """Creates an AWS EC2 key pair. The key file is created in the same directory as this
        module for simplicity.

        Parameters
        ----------
        key_name : Optional[str]
            The name of the key pair. Optional, so the function would generate a unique name if not
            specified.
        key_file_name : Optional[str]
            The filename where the key content would be stored. Optional, so the function would
            generate a unique name if not specified.

        Returns
        -------
        Tuple
            A tuple containing two elements: the KeyPair object at index 0 and the key name at
            index 1.
        """
        if not key_name:
            key_name = f"key-pair-{hash(time.time())}"
        if not key_file_name:
            key_file_name = key_name + ".pem"

        try:
            key_pair = self.resource.create_key_pair(KeyName=key_name)
            logging.info("Created key: %s.", key_pair.name)
            with open(key_file_name, "w") as f:
                f.write(key_pair.key_material)
                # Change the permissions of the key file to read by owner only to adjust to the
                # security requirements of SSHing to an EC2 VM
                os.chmod(key_file_name, stat.S_IRUSR)
                logging.info("Wrote private key to file: %s.", key_file_name)
        except ClientError as exc:
            logging.exception("Couldn't create key: %s!", key_name)
            raise exc
        else:
            return key_pair, key_name

    def create_security_group_with_ssh(self, group_name: Optional[str] = None) -> Tuple:
        """Creates a security group in the default virtual private cloud (VPC) of the
        current account, then adds a rule to the security group to allow SSH access.

        Parameters
        ----------
        group_name : Optional[str]
            The name of the security group to create. Optional, if omitted - a unique name is
            created.

        Returns
        -------
        Tuple
            A tuple containing two elements: the security group object at index 0 and its name at 1.
        """
        if not group_name:
            group_name = f"security-group-{hash(time.time())}"
        group_description = group_name + "-description"

        default_vpc = list(
            self.resource.vpcs.filter(Filters=[{"Name": "isDefault", "Values": ["true"]}])
        )[0]

        try:
            security_group = default_vpc.create_security_group(
                GroupName=group_name, Description=group_description
            )
            logging.info("Created security group %s in the default VPC.", group_name)
        except ClientError as exc:
            logging.exception("Couldn't create security group: %s!", group_name)
            raise exc

        security_group.authorize_ingress(
            IpPermissions=[
                # SSH ingress open to anyone
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                }
            ]
        )
        logging.info("Allowed all inbound SSH traffic for %s.", security_group.id)

        return security_group, group_name

    def create_instance(
        self,
        image_id: AWSEC2FreeTierAMIs,
        key_name: Optional[str] = None,
        security_group_name: Optional[str] = None,
        wait_for_status_ok: bool = True,
    ):
        """Creates a new Amazon EC2 instance. The instance automatically starts immediately after
        it is created.

        Parameters
        ----------
        image_id: AWSEC2FreeTierAMIs
            The ID of the AMI.
        key_name : Optional[str]
            The name of the key pair. Optional, so the function creates a unique key pair if none is
            provided.
        security_group_name : Optional[str]
            The name of the security group to use. Optional, so the function creates a security
            group part of the default VPC with SSH ingress traffic allowed if none is provided.
        wait_for_status_ok : bool
            Controls whether the function would wait for the instance to pass its status checks
            before returning. The wait and poll interval times are the default ones for boto3 -
            40 attempts each polled at 15s. Defaults To true.

        Returns
        -------
        ec2.Instance
        """

        key_name = key_name if key_name else self.create_key_pair()[1]
        groups = (
            security_group_name
            if security_group_name
            else [self.create_security_group_with_ssh()[1]]
        )

        try:
            instance_params = {
                "ImageId": image_id.value,
                "InstanceType": AWSEC2FreeTierInstanceTypes.T2_MICRO.value,
                "KeyName": key_name,
                "SecurityGroups": groups,
            }
            instance = self.resource.create_instances(**instance_params, MinCount=1, MaxCount=1)[0]
            logging.info("Created instance: %s.", instance.id)
        except ClientError as exc:
            logging.exception(
                "Couldn't create instance with image %s, instance type %s, and key %s!",
                image_id,
                image_id.value,
                key_name,
            )
            raise exc
        else:
            if wait_for_status_ok:
                logging.info(
                    "Starting to wait for instance with ID: %s, to pass its status checks...",
                    instance.id,
                )
                self.client.get_waiter("instance_status_ok").wait(InstanceIds=[instance.id])
                logging.info("Instance with ID: %s, has passed its status checks!", instance.id)

            return self.resource.Instance(id=instance.id)

    def reboot_instance(
        self,
        instance_obj,
        ssh_client: paramiko.SSHClient,
        username: str,
        start_rebooting_timeout_sec: int = 45,
        finish_rebooting_timeout_sec: int = 300,
        poll_interval_sec: int = 2,
    ):
        """Reboots an instance. The mechanism for verifying that the instance has reboot used in
        this method is necessary, because AWS EC2 instances actually don't have any status which
        indicates if an instance is rebooting - it always stays in a running state and with all
        checks passed. As a result, the wait mechanism in this method becomes necessary:
        1) wait for the SSH session to become closed, which indicates that the instance has
        started rebooting; 2) wait for a successful establishment of a new SSH session, which
        indicates that the instance has finished rebooting.

        Parameters
        ----------
        instance_obj : ec2.Instance
            The Instance object of the instance to reboot.
        ssh_client : paramiko.SSHClient
            The SSHClient object with an active session to the instance.
        username : str
            The username to log in the instance with.
        start_rebooting_timeout_sec : int
            The timeout, in seconds, to wait for the instance to start rebooting. The mechanism for
            this is to have the SSH session closed.
        finish_rebooting_timeout_sec : int
            The timeout, in seconds, to wait for the instance to finish rebooting. The mechanism for
            this is to be able to establish a new SSH session after rebooting.
        poll_interval_sec : int
            The interval, in seconds, to poll for started/finished rebooting.
        """
        logging.info("Rebooting the instance: %s...", instance_obj.id)
        self.client.reboot_instances(InstanceIds=[instance_obj.id])

        logging.info(
            "Starting to wait for instance with ID: %s, to start rebooting...",
            instance_obj.id,
        )
        timeout = time.time() + start_rebooting_timeout_sec
        while time.time() < timeout:
            try:
                ssh_client.exec_command("pwd")
            # pylint: disable=broad-except
            except Exception:
                break
            else:
                time.sleep(poll_interval_sec)
        else:
            raise UserWarning("Could not wait for the instance to start rebooting!")

        logging.info(
            "Starting to wait for instance with ID: %s, to finish rebooting...",
            instance_obj.id,
        )
        timeout = time.time() + finish_rebooting_timeout_sec
        while time.time() < timeout:
            try:
                ssh_client.connect(
                    hostname=instance_obj.public_dns_name,
                    username=username,
                    key_filename=instance_obj.key_name + ".pem",
                )
            # pylint: disable=broad-except
            except Exception:
                time.sleep(poll_interval_sec)
            else:
                break
        else:
            raise UserWarning("Could not wait for the instance to finish rebooting!")

    def delete_key_pair(self, key_name: str, key_file_name: Optional[str] = None):
        """Deletes a key pair and the specified private key file.

        Parameters
        ----------
        key_name : str
            The name of the key pair to delete.
        key_file_name : Optional[str]
            The local file name of the private key file. Optional, the key_name + '.pem' is deleted
            if not provided.
        """
        self.resource.KeyPair(key_name).delete()
        if not key_file_name:
            key_file_name = key_name + ".pem"
        os.remove(key_file_name)
        logging.info("Deleted key %s and private key file %s.", key_name, key_file_name)

    def delete_security_group(self, group_id: str):
        """Deletes a security group.

        Parameters
        ----------
        group_id : str
            The ID of the security group to delete.
        """
        self.resource.SecurityGroup(group_id).delete()
        logging.info("Deleted security group %s.", group_id)

    def terminate_instance(self, instance_id: str, wait_for_termination: bool = True):
        """Terminates an instance. The request returns immediately. To wait for the
        instance to terminate, use Instance.wait_until_terminated().

        Parameters
        ----------
        instance_id : str
            The ID of the instance to terminate.
        wait_for_termination : bool
            Controls whether the method waits for the termination of the instance or not. Defaults
            to True
        """
        logging.info("Terminating instance: %s...", instance_id)
        instance = self.resource.Instance(instance_id)
        instance.terminate()
        if wait_for_termination:
            logging.info(
                "Starting to wait for instance with ID: %s, to be Terminated...",
                instance.id,
            )
            instance.wait_until_terminated()
        logging.info("Instance with ID: %s, has been terminated!", instance.id)

    @staticmethod
    def get_instance_information(instance) -> InstanceInformation:
        """Gathers information about a given instance and returns it as a dictionary. The method
        gathers the following information: ID, image ID, platform details, and architecture of the
        instance.

        Returns
        -------
        InstanceInformation
            A dataclass containing the instance information.
        """
        return InstanceInformation(
            id=instance.id,
            image_id=instance.image_id,
            architecture=instance.architecture,
            platform=instance.platform_details,
        )
