import json
import os
import tempfile
from uuid import UUID

from django.utils.translation import gettext_lazy as _


class UUIDEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            # if the obj is uuid, we simply return the value of uuid
            return str(obj)
        return json.JSONEncoder.default(self, obj)


DATE_FORMAT_CHOICES = (
    ("yyyy-MM-dd HH:mm", _("Hour minute:second - (E.g 2023-01-01 00:00)")),
    ("yyyy-MM-dd", _("Day - (E.g 2023-01-01)")),
    ("yyyy-MM", _("Month number - (E.g 2023-01)")),
    ("MMMM yyyy", _("Month name - (E.g January 2023)")),
    ("pentadal", _("Pentadal - (E.g Jan 2023 - P1 1-5th)"))
)


class TmpFile:
    def __init__(self):
        self.f_name = None

    def target(self, ext):
        fd, self.f_name = tempfile.mkstemp(prefix="tile-server-", suffix=f".{ext}")
        os.close(fd)

        # Change output plot file permissions to something more reasonable, so
        # we are at least able to read the produced plots if directed outside
        # the docker environment (through the use of --volume).
        os.chmod(self.f_name, 0o644)
        return self.f_name

    def content(self):
        with open(self.f_name, "rb") as f:
            c = f.read()
            os.close(f)
        return c

    def cleanup(self):
        os.unlink(self.f_name)
