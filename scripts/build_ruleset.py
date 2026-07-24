#!/usr/bin/env python3
import json
import sys


def main():
    path = sys.argv[1]
    domains = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            domains.append(line)

    rules = []
    if domains:
        rules.append({
            "domain": domains,
            "domain_suffix": [f".{d}" for d in domains],
        })

    json.dump({"version": 1, "rules": rules}, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
