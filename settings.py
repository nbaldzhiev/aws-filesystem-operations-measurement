"""This module contains common settings across the project"""
import os
from logging import INFO

LOGGING_LEVEL = INFO


class DefaultAWSEC2Credentials:
    """This class contains default credentials for establishing a connection to AWS EC2. If the
    appropriate environment variables exist, they are used instead.

    Note: A valid IAM user is required.
    """

    DEFAULT_AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "AKIAVCUCA6ZN6TZFZPTW")
    DEFAULT_AWS_SECRET_ACCESS_KEY = os.getenv(
        "AWS_SECRET_ACCESS_KEY", "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"
    )
    DEFAULT_AWS_REGION = os.getenv("AWS_REGION", "eu-central-1")
