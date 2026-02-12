"""Command-line interface for CDSE Client."""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

from cdse import CDSEClient, __version__
from cdse.exceptions import AuthenticationError, CatalogError, DownloadError


def main(args: Optional[list[str]] = None) -> int:
    """Main entry point for CLI.

    Args:
        args: Command line arguments (default: sys.argv)

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    parser = argparse.ArgumentParser(
        prog="cdse",
        description="CDSE Client - Search and download Copernicus satellite data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Search for products
  cdse search --bbox 9.0,45.0,9.5,45.5 -s 2024-01-01 -e 2024-01-31

  # Search with cloud filter and download
  cdse search --bbox 9.0,45.0,9.5,45.5 -s 2024-01-01 -e 2024-01-31 -c 20 -d

  # Save footprints to GeoJSON
  cdse search --bbox 9.0,45.0,9.5,45.5 -s 2024-01-01 -e 2024-01-31 -f footprints.geojson

  # Download by product name
  cdse download --name S2A_MSIL2A_20240115T102351_N0510_R065_T32TQM_20240115T134815

  # Download by UUID
  cdse download --uuid a1b2c3d4-e5f6-...

  # Download quicklook only
  cdse download --name S2A_MSIL2A_... --quicklook
        """,
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
        help="Bounding box: min_lon,min_lat,max_lon,max_lat",
    )
    search_parser.add_argument(
        "-g",
        "--geometry",
        type=str,
        help="Path to GeoJSON file with search area",
    )
    search_parser.add_argument(
        "-s",
        "--start",
        type=str,
        required=True,
        help="Start date (YYYY-MM-DD)",
    )
    search_parser.add_argument(
        "-e",
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
        "-c",
        "--cloud",
        type=float,
        default=100.0,
        help="Maximum cloud cover %% (default: 100)",
    )
    search_parser.add_argument(
        "-l",
        "--limit",
        type=int,
        default=10,
        help="Maximum results (default: 10)",
    )
    search_parser.add_argument(
        "-d",
        "--download",
        action="store_true",
        help="Download all search results",
    )
    search_parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=".",
        help="Output directory for downloads (default: current directory)",
    )
    search_parser.add_argument(
        "-f",
        "--footprints",
        type=str,
        metavar="PATH",
        help="Save footprints to GeoJSON file",
    )
    search_parser.add_argument(
        "--json",
        action="store_true",
        help="Output search results as JSON",
    )
    search_parser.add_argument(
        "--parallel",
        action="store_true",
        help="Enable parallel downloads",
    )
    search_parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel download workers (default: 4)",
    )

    # Download command
    download_parser = subparsers.add_parser("download", help="Download a product")
    download_parser.add_argument(
        "--uuid",
        type=str,
        help="Product UUID to download",
    )
    download_parser.add_argument(
        "--name",
        type=str,
        help="Product name to download (e.g., S2A_MSIL2A_...)",
    )
    download_parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=".",
        help="Output directory (default: current directory)",
    )
    download_parser.add_argument(
        "--checksum",
        action="store_true",
        help="Verify MD5 checksum after download",
    )
    download_parser.add_argument(
        "--quicklook",
        action="store_true",
        help="Download quicklook preview only (small JPEG)",
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
        if parsed.command == "search":
            return cmd_search(client_id, client_secret, parsed)
        elif parsed.command == "download":
            return cmd_download(client_id, client_secret, parsed)
        elif parsed.command == "collections":
            return cmd_collections(client_id, client_secret)

    except AuthenticationError as e:
        print(f"Authentication error: {e.message}", file=sys.stderr)
        return 1
    except CatalogError as e:
        print(f"Catalog error: {e.message}", file=sys.stderr)
        return 1
    except DownloadError as e:
        print(f"Download error: {e.message}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nAborted by user.")
        return 130

    return 0


def cmd_search(client_id: str, client_secret: str, args: argparse.Namespace) -> int:
    """Execute search command."""
    client = CDSEClient(client_id, client_secret, args.output)

    # Get bbox from args or GeoJSON file
    bbox = None
    if args.bbox:
        try:
            bbox = [float(x) for x in args.bbox.split(",")]
            if len(bbox) != 4:
                raise ValueError("bbox must have 4 values")
        except ValueError as e:
            print(f"Invalid bbox format: {e}", file=sys.stderr)
            return 1
    elif args.geometry:
        from cdse import geojson_to_bbox, read_geojson

        try:
            geojson = read_geojson(args.geometry)
            bbox = geojson_to_bbox(geojson)
        except Exception as e:
            print(f"Error reading GeoJSON: {e}", file=sys.stderr)
            return 1
    else:
        print("Error: Either --bbox or -g/--geometry is required", file=sys.stderr)
        return 1

    # Search products
    products = client.search(
        bbox=bbox,
        start_date=args.start,
        end_date=args.end,
        collection=args.collection,
        cloud_cover_max=args.cloud,
        limit=args.limit,
    )

    if not products:
        print("No products found.")
        return 0

    # Output results
    if args.json:
        output = [p.to_dict() for p in products]
        print(json.dumps(output, indent=2, default=str))
    else:
        total_size = client.get_products_size(products)
        print(f"Found {len(products)} products (total: {total_size:.2f} GB)\n")
        for p in products:
            dt_str = p.datetime.strftime("%Y-%m-%d") if p.datetime else "N/A"
            cloud = f"{p.cloud_cover:.1f}%" if p.cloud_cover is not None else "N/A"
            print(f"  {p.name}")
            print(f"    Date: {dt_str}  Cloud: {cloud}")

    # Save footprints to GeoJSON
    if args.footprints:
        geojson = client.to_geojson(products)
        footprints_path = Path(args.footprints)
        with open(footprints_path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, indent=2, default=str)
        print(f"\nFootprints saved to: {footprints_path}")

    # Download if requested
    if args.download:
        print(f"\nDownloading {len(products)} products to {args.output}...")
        paths = client.download_all(
            products,
            output_dir=args.output,
            parallel=args.parallel,
            max_workers=args.workers,
        )
        print(f"\nDownloaded {len(paths)} files.")

    return 0


def cmd_download(client_id: str, client_secret: str, args: argparse.Namespace) -> int:
    """Execute download command."""
    if not args.uuid and not args.name:
        print("Error: Either --uuid or --name is required", file=sys.stderr)
        return 1

    client = CDSEClient(client_id, client_secret, args.output)

    # Find product by UUID or name
    product = None
    if args.uuid:
        print(f"Looking up product by UUID: {args.uuid}")
        product = client.search_by_id(args.uuid)
        if not product:
            print(f"Error: Product not found with UUID: {args.uuid}", file=sys.stderr)
            return 1
    elif args.name:
        print(f"Looking up product by name: {args.name}")
        product = client.search_by_name(args.name, exact=True)
        if not product:
            # Try prefix match
            product = client.search_by_name(args.name, exact=False)
        if not product:
            print(f"Error: Product not found: {args.name}", file=sys.stderr)
            return 1

    print(f"Found: {product.name}")

    # Download quicklook only
    if args.quicklook:
        print("Downloading quicklook preview...")
        try:
            path = client.download_quicklook(product, args.output)
            print(f"Quicklook saved to: {path}")
            return 0
        except DownloadError as e:
            print(f"Error: {e.message}", file=sys.stderr)
            return 1

    # Download full product
    print(f"Downloading to: {args.output}")
    if args.checksum:
        path = client.download_with_checksum(product, args.output)
    else:
        path = client.download(product, args.output)

    print(f"Downloaded: {path}")
    return 0


def cmd_collections(client_id: str, client_secret: str) -> int:
    """Execute collections command."""
    client = CDSEClient(client_id, client_secret)
    collections = client.get_collections()

    print("Available collections:\n")
    for coll_id, description in collections.items():
        print(f"  {coll_id}")
        print(f"    {description}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
