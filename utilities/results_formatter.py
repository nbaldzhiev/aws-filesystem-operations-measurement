"""This module contains an implementation of a formatter of results, which receives instance and
operations measurements info and prints the formatted results."""
import json
import logging

from settings import LOGGING_LEVEL
from utilities.enums_dataclasses import InstanceInformation, InstanceOperationsMeasurements

logging.basicConfig(level=LOGGING_LEVEL)


class ResultsFormatter:
    """This class implements a formatter of results, which receives instance and operations
    measurements info and prints the formatted results."""

    def __init__(
        self,
        instance_information: InstanceInformation,
        operations_measurements: InstanceOperationsMeasurements,
        human_readable: bool,
    ):
        self.instance_info = instance_information
        self.operations_measurements = operations_measurements
        self.human_readable = human_readable

    def format_results(self) -> str:
        """Formats the results and returns them as either a JSON formatted string or a free-form
        string, depending on the value of the attribute human_readable.
        """
        if self.human_readable:
            results = ResultsFormatter.get_human_friendly_results_template().format(
                self.instance_info.id,
                self.instance_info.image_id,
                self.operations_measurements.create_elapsed_ms,
                self.operations_measurements.copy_elapsed_ms,
                self.operations_measurements.delete_elapsed_ms,
                self.instance_info.platform,
                self.instance_info.architecture,
            )
        else:
            results = json.dumps(
                {
                    self.instance_info.id: {
                        "instance_information": {
                            "image_id": self.instance_info.image_id,
                            "platform": self.instance_info.platform,
                            "architecture": self.instance_info.architecture,
                        },
                        "operations_measurements_milliseconds": {
                            "create": self.operations_measurements.create_elapsed_ms,
                            "copy": self.operations_measurements.copy_elapsed_ms,
                            "delete": self.operations_measurements.delete_elapsed_ms,
                        },
                    }
                }
            )

        logging.info("Formatted the following results: %s", results)
        return results

    @staticmethod
    def get_human_friendly_results_template() -> str:
        """Returns a template string for outputting the measurements results in a human friendly
        format, which in this case is just free-form text."""
        return (
            "The following operations were performed on a set of 1000 files, each 1MB "
            "in size, on an instance with ID {} and image ID {}: 1) Creating the files took "
            "{} milliseconds; 2) Copying the files from one directory to another took {} "
            "milliseconds; 3) Deleting the files took {} milliseconds. The platform of the "
            "instance is {} and its architecture is {}."
        )
