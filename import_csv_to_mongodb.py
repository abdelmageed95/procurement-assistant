#!/usr/bin/env python3
"""
CSV to MongoDB Importer for California Procurement Data

Converts CSV file to MongoDB collection with proper data type handling:
- Dates: MM/DD/YYYY strings → datetime objects
- Currency: "$1,234.56" → 1234.56 (float)
- Numbers: "123" → 123 (int/float)
- Empty strings → None (cleaner queries)

Usage:
    python import_csv_to_mongodb.py <csv_file> [options]

    Arguments:
        csv_file              Path to CSV file (required)

    Options:
        --mongo-uri URI       MongoDB connection URI
                             (default: mongodb://localhost:27017/)
        --database DB         Database name (default: procurement_db)
        --collection COLL     Collection name (default: purchase_orders)
        --batch-size SIZE     Batch size for inserts (default: 1000)
        --no-clear            Don't clear existing data before import

    Examples:
        # Basic usage
        python import_csv_to_mongodb.py data.csv

        # Custom database
        python import_csv_to_mongodb.py data.csv --database my_db

        # Remote MongoDB
        python import_csv_to_mongodb.py data.csv --mongo-uri mongodb://host:27017/

        # Don't clear existing data
        python import_csv_to_mongodb.py data.csv --no-clear
"""

import csv
import sys
import argparse
from pymongo import MongoClient
from datetime import datetime
from pathlib import Path


class ProcurementDataImporter:
    """Handles CSV import to MongoDB with data type conversion"""

    def __init__(
        self,
        csv_file,
        mongo_uri="mongodb://localhost:27017/",
        db_name="procurement_db",
        collection_name="purchase_orders",
        batch_size=1000,
        clear_existing=True,
    ):
        self.csv_file = csv_file
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.collection_name = collection_name
        self.batch_size = batch_size
        self.clear_existing = clear_existing

        # Statistics
        self.stats = {
            "total": 0,
            "dates_converted": 0,
            "prices_converted": 0,
            "errors": 0,
        }

        # Batch processing
        self.batch = []

    def connect_mongodb(self):
        """Establish MongoDB connection"""
        try:
            self.client = MongoClient(self.mongo_uri)
            self.db = self.client[self.db_name]
            self.collection = self.db[self.collection_name]
            print(f"✅ Connected to MongoDB: {self.db_name}.{self.collection_name}")
            return True
        except Exception as e:
            print(f"❌ MongoDB connection failed: {e}")
            return False

    def clear_existing_data(self):
        """Clear existing collection data"""
        result = self.collection.delete_many({})
        print(f"🗑️  Cleared {result.deleted_count} existing documents")

    @staticmethod
    def parse_date(date_str):
        """Convert MM/DD/YYYY string to datetime object"""
        if not date_str or date_str.strip() == "":
            return None
        try:
            return datetime.strptime(date_str.strip(), "%m/%d/%Y")
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def parse_currency(currency_str):
        """Convert '$1,234.56' to float 1234.56"""
        if not currency_str or currency_str.strip() == "":
            return None
        try:
            # Remove $, commas, and convert to float
            cleaned = currency_str.replace("$", "").replace(",", "").strip()
            return float(cleaned) if cleaned else None
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def parse_number(num_str):
        """Convert string to int or float"""
        if not num_str or num_str.strip() == "":
            return None
        try:
            cleaned = num_str.strip()
            # Try int first
            if "." not in cleaned:
                return int(cleaned)
            return float(cleaned)
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def clean_string(s):
        """Clean string fields - convert empty to None"""
        if not s or s.strip() == "":
            return None
        return s.strip()

    def preprocess_row(self, row):
        """
        Transform CSV row into properly typed MongoDB document.

        Improvements:
        - Dates: String → datetime objects (enables native date queries)
        - Currency: "$1,234.56" → 1234.56 (float)
        - Numbers: "123" → 123 (int/float)
        - Empty strings → None (better for queries)
        """
        processed = {}

        # Date fields - CRITICAL for query accuracy
        processed["creation_date"] = self.parse_date(row.get("Creation Date"))
        processed["purchase_date"] = self.parse_date(row.get("Purchase Date"))

        # Keep original strings for display (optional)
        processed["creation_date_str"] = self.clean_string(row.get("Creation Date"))
        processed["purchase_date_str"] = self.clean_string(row.get("Purchase Date"))

        # Fiscal year
        processed["fiscal_year"] = self.clean_string(row.get("Fiscal Year"))

        # IDs and codes
        processed["lpa_number"] = self.clean_string(row.get("LPA Number"))
        processed["purchase_order_number"] = self.clean_string(
            row.get("Purchase Order Number")
        )
        processed["requisition_number"] = self.clean_string(
            row.get("Requisition Number")
        )

        # Classification
        processed["acquisition_type"] = self.clean_string(row.get("Acquisition Type"))
        processed["sub_acquisition_type"] = self.clean_string(
            row.get("Sub-Acquisition Type")
        )
        processed["acquisition_method"] = self.clean_string(
            row.get("Acquisition Method")
        )
        processed["sub_acquisition_method"] = self.clean_string(
            row.get("Sub-Acquisition Method")
        )

        # Department and supplier info
        processed["department_name"] = self.clean_string(row.get("Department Name"))
        processed["supplier_code"] = self.clean_string(row.get("Supplier Code"))
        processed["supplier_name"] = self.clean_string(row.get("Supplier Name"))
        processed["supplier_qualifications"] = self.clean_string(
            row.get("Supplier Qualifications")
        )
        processed["supplier_zip_code"] = self.clean_string(
            row.get("Supplier Zip Code")
        )

        # CalCard
        processed["cal_card"] = self.clean_string(row.get("CalCard"))

        # Item details
        processed["item_name"] = self.clean_string(row.get("Item Name"))
        processed["item_description"] = self.clean_string(row.get("Item Description"))

        # Numeric fields - CRITICAL for sorting/filtering
        processed["quantity"] = self.parse_number(row.get("Quantity"))
        processed["unit_price"] = self.parse_currency(row.get("Unit Price"))
        processed["total_price"] = self.parse_currency(row.get("Total Price"))

        # Keep original currency strings for display
        processed["unit_price_str"] = self.clean_string(row.get("Unit Price"))
        processed["total_price_str"] = self.clean_string(row.get("Total Price"))

        # Classification codes
        processed["classification_codes"] = self.clean_string(
            row.get("Classification Codes")
        )
        processed["normalized_unspsc"] = self.clean_string(
            row.get("Normalized UNSPSC")
        )
        processed["commodity_title"] = self.clean_string(row.get("Commodity Title"))
        processed["class"] = self.clean_string(row.get("Class"))
        processed["class_title"] = self.clean_string(row.get("Class Title"))
        processed["family"] = self.clean_string(row.get("Family"))
        processed["family_title"] = self.clean_string(row.get("Family Title"))
        processed["segment"] = self.clean_string(row.get("Segment"))
        processed["segment_title"] = self.clean_string(row.get("Segment Title"))
        processed["location"] = self.clean_string(row.get("Location"))

        return processed

    def insert_batch(self):
        """Insert current batch to MongoDB"""
        if self.batch:
            self.collection.insert_many(self.batch)
            self.batch = []

    def process_csv(self):
        """Process CSV file and import to MongoDB"""
        csv_path = Path(self.csv_file)

        if not csv_path.exists():
            print(f"❌ CSV file not found: {self.csv_file}")
            return False

        print(f"📄 Processing CSV: {self.csv_file}")
        print(f"   Batch size: {self.batch_size}")
        print()

        try:
            with open(csv_path, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)

                for i, row in enumerate(reader, 1):
                    try:
                        processed_doc = self.preprocess_row(row)
                        self.batch.append(processed_doc)

                        # Track statistics
                        self.stats["total"] += 1
                        if processed_doc.get("creation_date"):
                            self.stats["dates_converted"] += 1
                        if processed_doc.get("total_price") is not None:
                            self.stats["prices_converted"] += 1

                        # Insert batch
                        if i % self.batch_size == 0:
                            self.insert_batch()
                            print(f"   Inserted {i:,} rows...")

                    except Exception as e:
                        self.stats["errors"] += 1
                        print(f"   ⚠️  Error on row {i}: {e}")

                # Insert remaining
                self.insert_batch()

            return True

        except Exception as e:
            print(f"❌ Error processing CSV: {e}")
            return False

    def print_summary(self):
        """Print import summary statistics"""
        print()
        print("=" * 60)
        print("📊 IMPORT SUMMARY")
        print("=" * 60)
        print(f"Total rows processed:    {self.stats['total']:,}")
        print(f"Dates converted:         {self.stats['dates_converted']:,}")
        print(f"Prices converted:        {self.stats['prices_converted']:,}")
        print(f"Errors:                  {self.stats['errors']:,}")
        print()

        # Sample document
        sample = self.collection.find_one()
        if sample:
            print("📝 Sample document structure:")
            creation = sample.get('creation_date')
            print(f"   - creation_date: {creation} (datetime)")
            price = sample.get('total_price')
            price_type = type(price).__name__
            print(f"   - total_price: {price} ({price_type})")
            dept = sample.get('department_name')
            print(f"   - department_name: {dept}")
            print()

        # Collection stats
        total_docs = self.collection.count_documents({})
        coll = self.collection_name
        print(f"✅ Collection '{coll}' now has {total_docs:,} documents")
        print("=" * 60)

    def run(self):
        """Main execution flow"""
        print("=" * 60)
        print("🏛️  CALIFORNIA PROCUREMENT DATA IMPORTER")
        print("=" * 60)
        print()

        # Connect to MongoDB
        if not self.connect_mongodb():
            sys.exit(1)

        # Clear existing data if requested
        if self.clear_existing:
            self.clear_existing_data()
        else:
            print("⚠️  Appending to existing data (--no-clear specified)")

        # Process CSV
        print()
        if not self.process_csv():
            sys.exit(1)

        # Print summary
        self.print_summary()


def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Import CSV data to MongoDB with proper type conversion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python import_csv_to_mongodb.py data.csv

  # Custom database
  python import_csv_to_mongodb.py data.csv --database my_db

  # Remote MongoDB
  python import_csv_to_mongodb.py data.csv \\
    --mongo-uri mongodb://user:pass@host:27017/

  # Don't clear existing data
  python import_csv_to_mongodb.py data.csv --no-clear

  # Custom batch size
  python import_csv_to_mongodb.py data.csv --batch-size 5000
        """,
    )

    parser.add_argument(
        "csv_file", type=str, help="Path to CSV file to import"
    )

    parser.add_argument(
        "--mongo-uri",
        type=str,
        default="mongodb://localhost:27017/",
        help="MongoDB connection URI (default: mongodb://localhost:27017/)",
    )

    parser.add_argument(
        "--database",
        type=str,
        default="procurement_db",
        help="Database name (default: procurement_db)",
    )

    parser.add_argument(
        "--collection",
        type=str,
        default="purchase_orders",
        help="Collection name (default: purchase_orders)",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for inserts (default: 1000)",
    )

    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Don't clear existing collection data before import",
    )

    return parser.parse_args()


def main():
    """Entry point"""
    args = parse_arguments()

    importer = ProcurementDataImporter(
        csv_file=args.csv_file,
        mongo_uri=args.mongo_uri,
        db_name=args.database,
        collection_name=args.collection,
        batch_size=args.batch_size,
        clear_existing=not args.no_clear,
    )

    importer.run()


if __name__ == "__main__":
    main()
