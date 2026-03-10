"""
anysql_sdk/cli.py
CLI entry point: anysql query "SELECT ..." / anysql stats
"""
import sys
import argparse


def main():
    parser = argparse.ArgumentParser(
        prog="anysql",
        description="anySQL — SQL analytics for AI systems",
    )
    subparsers = parser.add_subparsers(dest="command")

    # anysql query "SELECT ..."
    query_parser = subparsers.add_parser("query", help="Run SQL against anysql.db")
    query_parser.add_argument("sql", help="SQL query string")
    query_parser.add_argument("--db", default="anysql.db", help="Path to SQLite database")

    # anysql stats
    stats_parser = subparsers.add_parser("stats", help="Show row counts for all tables")
    stats_parser.add_argument("--db", default="anysql.db", help="Path to SQLite database")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    import anysql_sdk
    db = anysql_sdk.init(args.db)

    if args.command == "query":
        result = db.query(args.sql)
        print(result.to_string(index=False))

    elif args.command == "stats":
        from anysql_sdk.schema import TABLE_NAMES
        print("\nanySQL table row counts:")
        for table in TABLE_NAMES:
            count = db.count(table)
            print(f"  {table:<25} {count:>6} rows")
        print()


if __name__ == "__main__":
    main()
