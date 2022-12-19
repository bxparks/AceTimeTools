# Copyright 2020 Brian T. Park
#
# MIT License

from typing import Any
from typing import List
import os
import logging
import json

from acetimetools.data_types.at_types import ZoneInfoDatabase


# Serializer for Set(). See
# https://researchdatapod.com/how-to-solve-python-typeerror-object-of-type-set-is-not-json-serializable/
def serialize_sets(obj: Any) -> List[Any]:
    if isinstance(obj, set):
        return list(obj)
    raise TypeError("Type %s is not serializable" % type(obj))


class JsonGenerator:
    """Generate the JSON representation of the ZoneInfoDatabase to the given
    'json_file'.
    """
    def __init__(
        self,
        zidb: ZoneInfoDatabase,
        json_file: str
    ):
        self.zidb = zidb
        self.json_file = json_file

    def generate_files(self, output_dir: str) -> None:
        """Serialize ZoneInfoDatabase to the specified file."""
        full_filename = os.path.join(output_dir, self.json_file)
        with open(full_filename, 'w', encoding='utf-8') as output_file:
            json.dump(self.zidb, output_file, indent=2, default=serialize_sets)
            print(file=output_file)  # add terminating newline
        logging.info("Created %s", full_filename)
