#!/usr/bin/env python3
"""
Upload a file to the remote build host over SFTP.

Companion to scripts/remote_exec.py.  Credentials come from the same
environment variables and are never stored in the repo.

    REMOTE_HOST, REMOTE_PORT, REMOTE_USER, REMOTE_PASS (or REMOTE_KEY)

Usage:
    python scripts/remote_put.py <local-file> <remote-path>
    python scripts/remote_put.py patch.patch /root/data/muqcom/x.patch
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
    local, remote = sys.argv[1], sys.argv[2]
    if not os.path.isfile(local):
        print("error: no such local file: %s" % local, file=sys.stderr)
        return 2

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
        sftp = client.open_sftp()
        sftp.put(local, remote)
        st = sftp.stat(remote)
        sftp.close()
        print("uploaded %s -> %s (%d bytes)" % (local, remote, st.st_size))
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
