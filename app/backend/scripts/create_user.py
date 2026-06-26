from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from themis.auth import load_users, md5_password, save_users


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update a Themis JSON-file user.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--role", choices=["admin", "labeler"], required=True)
    parser.add_argument("--password", help="Password. If omitted, prompts securely.")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Password: ")
    users = [user for user in load_users() if user.get("username") != args.username]
    users.append(
        {
            "username": args.username,
            "password_md5": md5_password(password),
            "role": args.role,
            "active": True,
        }
    )
    save_users(users)
    print(f"User {args.username} saved to app/env/users.json")


if __name__ == "__main__":
    main()

