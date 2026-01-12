"""Processing example: build an RGB preview.

Requires:
  pip install cdse-client[processing]

This example assumes you already downloaded a product.
"""

from cdse.processing import preview_product


def main() -> None:
    safe_path = "./downloads/your-product.SAFE"  # or extracted SAFE folder
    preview_product(safe_path=safe_path, output_path="preview.png")


if __name__ == "__main__":
    main()
