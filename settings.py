"""This module contains common settings across the project"""
import os
from logging import INFO

LOGGING_LEVEL = INFO
PERFORM_MEASUREMENTS_BASH_SCRIPT = "perform_measurements.sh"
SETUP_CRON_BASH_SCRIPT = "setup_cron.sh"
RESULTS_FILENAME = "results.txt"


class DefaultAWSEC2Credentials:
    """This class contains default credentials for establishing a connection to AWS EC2. If the
    appropriate environment variables exist, they are used instead.

    Note: A valid IAM user is required in order to have an eligible access key ID and secret
    access key.
    """

    DEFAULT_AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "AKIAVCUCA6ZN6TZFZPTW")
    DEFAULT_AWS_SECRET_ACCESS_KEY = os.getenv(
        "AWS_SECRET_ACCESS_KEY", "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"
    )
    DEFAULT_AWS_REGION = os.getenv("AWS_REGION", "eu-central-1")
