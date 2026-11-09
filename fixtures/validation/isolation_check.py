"""Integration fixture: fail if the promised filesystem/network boundary leaks."""
import errno
import os
from pathlib import Path
import socket
import sys

assert os.getuid() == 65534
assert not Path(sys.argv[1]).exists(), "host-only sentinel must not be visible"
for path in ("/source/untrusted-write", "/untrusted-write"):
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_WRONLY, 0o600)
    except OSError as error:
        assert error.errno in (errno.EROFS, errno.EACCES)
    else:
        os.close(descriptor)
        raise AssertionError("unexpected writable source/root mount")
Path("/work/scratch").write_text("allowed temporary data")
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
    connection.settimeout(0.5)
    try:
        connection.connect(("1.1.1.1", 53))
    except OSError:
        pass
    else:
        raise AssertionError("unexpected external network access")
print("isolated")
