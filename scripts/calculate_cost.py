"""
Purpose: Calculate the cost of generating bugs across all repositories

Usage: python scripts/calculate_cost.py <bug_type (e.g. "lm_rewrite")>
"""

import argparse
import os

from swesmith.bug_gen.get_cost import main as get_cost
from swesmith.constants import LOG_DIR_BUG_GEN


def main(bug_type: str) -> None:
    folders = [
        x
        for x in os.listdir(LOG_DIR_BUG_GEN)
        if os.path.isdir(os.path.join(LOG_DIR_BUG_GEN, x))
    ]
    total_cost, total_bugs = 0, 0
    print("Repo | Cost | Bugs | Cost/Instance")
    for folder in folders:
        cost, bugs, per_instance = get_cost(
            os.path.join(LOG_DIR_BUG_GEN, folder), bug_type
        )
        if cost == 0:
            continue
        print(f"- {folder}: {cost} | {bugs} | {per_instance}")
        total_cost += cost
        total_bugs += bugs
    print(
        f"Total: {round(total_cost, 2)} | {total_bugs} | {round(total_cost / total_bugs, 6)}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Determine the total cost of generating bugs across all repositories"
    )
    parser.add_argument(
        dest="bug_type",
        type=str,
        help="Type of patches to collect. (default: all)",
        default="all",
    )
    args = parser.parse_args()
    main(**vars(args))
