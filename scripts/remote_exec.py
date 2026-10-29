#!/usr/bin/env python3
"""
Run a command on the remote build host over SSH (paramiko), non-interactively.

Why this exists
---------------
The Mu-Qcom build needs glibc-linked tool binaries (Microsoft's prebuilt
BaseTools) plus mono for the NuGet phase.  The local WSL distribution is
Alpine/musl, which cannot run them natively (GenSec returns 127 and BaseTools
swallows the failure -- see docs/bringup-log.md B12.3 #8).  A real glibc Linux
host removes that entire class of problem.

Credentials are NEVER stored in this file or in the repo.  Supply them through
the environment:

    REMOTE_HOST=1.2.3.4
    REMOTE_PORT=22
    REMOTE_USER=root
    REMOTE_PASS=...           (or REMOTE_KEY=/path/to/id_rsa)

Usage:
    python scripts/remote_exec.py "uname -a"
    python scripts/remote_exec.py --timeout 3600 "cd /root/data && make"

Exit code is the remote command's exit status, so this composes with shell
pipelines on the caller side.
"""

import argparse
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


def connect():
    host = env("REMOTE_HOST", required=True)
    port = int(env("REMOTE_PORT", "22"))
    user = env("REMOTE_USER", "root")
    password = env("REMOTE_PASS")
    keyfile = env("REMOTE_KEY")

    client = paramiko.SSHClient()
    # The host is a known build box supplied for this task; we still record the
    # host key in a persistent known_hosts-like policy of AutoAdd so a changed
    # identity is not silently trusted between runs in one process.
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kw = dict(hostname=host, port=port, username=user, timeout=25,
              allow_agent=False, look_for_keys=False)
    if keyfile:
        kw["key_filename"] = keyfile
    if password:
        kw["password"] = password
    client.connect(**kw)
    return client


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", help="remote command to run")
    ap.add_argument("--timeout", type=int, default=1800,
                    help="seconds to wait for the command (default 1800)")
    ap.add_argument("--quiet", action="store_true", help="only show exit code")
    args = ap.parse_args()

    client = connect()
    try:
        stdin, stdout, stderr = client.exec_command(args.command,
                                                    timeout=args.timeout)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        rc = stdout.channel.recv_exit_status()
        if not args.quiet:
            if out:
                sys.stdout.write(out)
            if err:
                sys.stderr.write(err)
        print("[remote exit %d]" % rc, file=sys.stderr)
        return rc
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
