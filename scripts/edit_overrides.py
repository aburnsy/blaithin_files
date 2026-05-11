"""CLI for viewing and editing data/match_overrides.parquet.

Subcommands:
  list                — print all overrides
  set <name> <rhs_id> — manually map a product name to an RHS id
  delete <name>       — remove an override
"""

import argparse
import os
import sys
from pathlib import Path

# Add repo root to sys.path for imports
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# Allow OVERRIDES_PARQUET env override (used by tests)
if "OVERRIDES_PARQUET" in os.environ:
    import src.matching.overrides as overrides_mod
    overrides_mod.OVERRIDES_PARQUET = Path(os.environ["OVERRIDES_PARQUET"])

from src.matching.models import MatchOverride
from src.matching.overrides import load_overrides, upsert_override


def cmd_list(_args):
    overrides = load_overrides()
    if not overrides:
        print("(no overrides)")
        return
    for o in overrides:
        print(f"{o.product_name_clean!r}  ->  rhs_id={o.rhs_id}  cultivar={o.cultivar!r}  source={o.source}")


def cmd_set(args):
    upsert_override(MatchOverride(
        product_name_clean=args.name,
        rhs_id=args.rhs_id,
        cultivar=args.cultivar,
        is_plant=args.is_plant,
        source="manual",
        notes=args.notes,
    ))
    print(f"Set override: {args.name!r} -> rhs_id={args.rhs_id}")


def cmd_delete(args):
    overrides = load_overrides()
    keep = [o for o in overrides if o.product_name_clean != args.name]
    if len(keep) == len(overrides):
        print(f"No override found for {args.name!r}")
        return 1
    from src.matching.overrides import save_overrides
    save_overrides(keep)
    print(f"Deleted override: {args.name!r}")


def main():
    parser = argparse.ArgumentParser(description="Edit data/match_overrides.parquet")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list").set_defaults(func=cmd_list)

    s = sub.add_parser("set")
    s.add_argument("name", help="product_name_clean")
    s.add_argument("rhs_id", type=int)
    s.add_argument("--cultivar", default=None)
    s.add_argument("--is-plant", type=bool, default=True)
    s.add_argument("--notes", default=None)
    s.set_defaults(func=cmd_set)

    s = sub.add_parser("delete")
    s.add_argument("name")
    s.set_defaults(func=cmd_delete)

    args = parser.parse_args()
    sys.exit(args.func(args) or 0)


if __name__ == "__main__":
    main()
