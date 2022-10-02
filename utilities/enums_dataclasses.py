"""This module contains common Enum classes used within the project."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AWSServices(Enum):
    """Contains constants for services by AWS."""

    EC2 = "ec2"


class AWSEC2FreeTierAMIs(Enum):
    """Contains constants for IDs of free tier AMIs."""

    AMAZON_LINUX_2 = "ami-05ff5eaef6149df49"
    UBUNTU_SERVER_22_04 = "ami-0caef02b518350c8b"
    RHEL_8 = "ami-0e7e134863fac4946"


class DefaultAMIUsernames(Enum):
    """Contains constants for the default AMI usernames."""

    AMAZON_LINUX = "ec2-user"
    RHEL = "ec2-user"
    UBUNTU = "ubuntu"


class AWSEC2FreeTierInstanceTypes(Enum):
    """Contains constants for free tier instance types."""

    T2_MICRO = "t2.micro"


@dataclass
class InstanceInformation:
    """Contains relevant information regarding a given EC2 instance."""

    id: str
    platform: str
    image_id: str
    architecture: str


@dataclass
class InstanceOperationsMeasurements:
    """Contains the operations measurement results."""

    create_elapsed_ms: int
    copy_elapsed_ms: int
    delete_elapsed_ms: int


@dataclass
class InstanceToCreate:
    """Contains information about a given instance to be created."""

    ami_id: AWSEC2FreeTierAMIs
    username: DefaultAMIUsernames
    key_pair_name: Optional[str] = None
    security_group_name: Optional[str] = None
