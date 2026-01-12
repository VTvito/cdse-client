"""Command-line interface for CDSE Client."""

import argparse
import json
import os
import sys
from typing import List, Optional

from cdse import CDSEClient, __version__
from cdse.exceptions import AuthenticationError, CatalogError, DownloadError


def main(args: Optional[List[str]] = None) -> int:
    """Main entry point for CLI.

    Args:
        args: Command line arguments (default: sys.argv)

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    parser = argparse.ArgumentParser(
        prog="cdse",
        description="CDSE Client - Search and download Copernicus satellite data",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"cdse-client {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search for products")
    search_parser.add_argument(
        "--bbox",
        type=str,
        required=True,
        help="Bounding box: min_lon,min_lat,max_lon,max_lat",
    )
    search_parser.add_argument(
        "--start",
        type=str,
        required=True,
        help="Start date (YYYY-MM-DD)",
    )
    search_parser.add_argument(
        "--end",
        type=str,
        required=True,
        help="End date (YYYY-MM-DD)",
    )
    search_parser.add_argument(
        "--collection",
        type=str,
        default="sentinel-2-l2a",
        help="Collection name (default: sentinel-2-l2a)",
    )
    search_parser.add_argument(
        "--cloud",
        type=float,
        default=100.0,
        help="Maximum cloud cover %% (default: 100)",
    )
    search_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum results (default: 10)",
    )
    search_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    # Download command
    download_parser = subparsers.add_parser("download", help="Download a product")
    download_parser.add_argument(
        "product_id",
        type=str,
        help="Product ID or name to download",
    )
    download_parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=".",
        help="Output directory (default: current directory)",
    )

    # Collections command
    subparsers.add_parser("collections", help="List available collections")

    # Parse arguments
    parsed = parser.parse_args(args)

    if not parsed.command:
        parser.print_help()
        return 0

    # Check credentials
    client_id = os.environ.get("CDSE_CLIENT_ID")
    client_secret = os.environ.get("CDSE_CLIENT_SECRET")

    if not client_id or not client_secret:
        print(
            "Error: Set CDSE_CLIENT_ID and CDSE_CLIENT_SECRET environment variables",
            file=sys.stderr,
        )
        return 1

    try:
        client = CDSEClient(client_id, client_secret)

        if parsed.command == "search":
            return cmd_search(client, parsed)
        elif parsed.command == "download":
            return cmd_download(client, parsed)
        elif parsed.command == "collections":
            return cmd_collections(client)

    except AuthenticationError as e:
        print(f"Authentication error: {e.message}", file=sys.stderr)
        return 1
    except CatalogError as e:
        print(f"Catalog error: {e.message}", file=sys.stderr)
        return 1
    except DownloadError as e:
        print(f"Download error: {e.message}", file=sys.stderr)
        return 1

    return 0


def cmd_search(client: CDSEClient, args: argparse.Namespace) -> int:
    """Execute search command."""
    # Parse bbox
    try:
        bbox = [float(x) for x in args.bbox.split(",")]
        if len(bbox) != 4:
            raise ValueError("bbox must have 4 values")
    except ValueError as e:
        print(f"Invalid bbox format: {e}", file=sys.stderr)
        return 1

    products = client.search(
        bbox=bbox,
        start_date=args.start,
        end_date=args.end,
        collection=args.collection,
        cloud_cover_max=args.cloud,
        limit=args.limit,
    )

    if args.json:
        output = [p.to_dict() for p in products]
        print(json.dumps(output, indent=2, default=str))
    else:
        print(f"Found {len(products)} products:\n")
        for p in products:
            dt_str = p.datetime.strftime("%Y-%m-%d") if p.datetime else "N/A"
            cloud = f"{p.cloud_cover:.1f}%" if p.cloud_cover is not None else "N/A"
            print(f"  {p.name}")
            print(f"    Date: {dt_str}  Cloud: {cloud}")
            print()

    return 0


def cmd_download(client: CDSEClient, args: argparse.Namespace) -> int:
    """Execute download command."""
    # For now, this is a placeholder
    # Full implementation would query by product ID
    print(f"Downloading {args.product_id} to {args.output}")
    print("Note: Direct download by ID coming in next version")
    return 0


def cmd_collections(client: CDSEClient) -> int:
    """Execute collections command."""
    collections = client.get_collections()

    print("Available collections:\n")
    for coll_id, description in collections.items():
        print(f"  {coll_id}")
        print(f"    {description}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
