"""This module contains common Enum classes used within the project."""
from enum import Enum


class AWSServices(Enum):
    """Contains constants for services by AWS."""

    EC2 = "ec2"


class AWSEC2FreeTierAMIs(Enum):
    """Contains constants for IDs of free tier AMIs."""

    AMAZON_LINUX_2 = "ami-05ff5eaef6149df49"
    UBUNTU_SERVER_22_04 = "ami-0caef02b518350c8b"
    RHEL_8 = "ami-0e7e134863fac4946"


class AWSEC2FreeTierInstanceTypes(Enum):
    """Contains constants for free tier instance types."""

    T2_MICRO = "t2.micro"
