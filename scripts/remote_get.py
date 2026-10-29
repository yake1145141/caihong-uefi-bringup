#!/usr/bin/env python3
"""
Download a file from the remote build host over SFTP.

Companion to scripts/remote_exec.py / remote_put.py.  Credentials come from the
same environment variables and are never stored in the repo.

    REMOTE_HOST, REMOTE_PORT, REMOTE_USER, REMOTE_PASS (or REMOTE_KEY)

Usage:
    python scripts/remote_get.py <remote-path> <local-path>
"""

import os
import sys

try:
    import paramiko
except ImportError:
    print("error: paramiko is required:  python -m pip install paramiko",
          file=sys.stderr)
    sys.exit(2)


def env(name, default=None, required=False):
    v = os.environ.get(name, default)
    if required and not v:
        print("error: environment variable %s is required" % name, file=sys.stderr)
        sys.exit(2)
    return v


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 64
    remote, local = sys.argv[1], sys.argv[2]

    host = env("REMOTE_HOST", required=True)
    port = int(env("REMOTE_PORT", "22"))
    user = env("REMOTE_USER", "root")
    password = env("REMOTE_PASS")
    keyfile = env("REMOTE_KEY")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kw = dict(hostname=host, port=port, username=user, timeout=25,
              allow_agent=False, look_for_keys=False)
    if keyfile:
        kw["key_filename"] = keyfile
    if password:
        kw["password"] = password
    client.connect(**kw)
    try:
        d = os.path.dirname(local)
        if d:
            os.makedirs(d, exist_ok=True)
        sftp = client.open_sftp()
        sftp.get(remote, local)
        sftp.close()
        print("downloaded %s -> %s (%d bytes)"
              % (remote, local, os.path.getsize(local)))
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
