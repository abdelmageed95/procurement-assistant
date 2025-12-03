#!/usr/bin/env python3
"""
Comprehensive Dataset Setup Script for California Procurement Data

This script automates the entire dataset setup process:
1. Downloads the Kaggle dataset ZIP file
2. Creates data directory if it doesn't exist
3. Extracts the ZIP file
4. Renames the CSV file (replaces spaces with underscores)
5. Imports data to MongoDB with proper type conversion

Usage:
    python setup_dataset.py [options]

    Options:
        --mongo-uri URI       MongoDB connection URI
                             (default: mongodb://localhost:27017/)
        --database DB         Database name (default: procurement_db)
        --collection COLL     Collection name (default: purchase_orders)
        --batch-size SIZE     Batch size for inserts (default: 1000)
        --no-clear            Don't clear existing data before import
        --keep-zip            Keep the downloaded ZIP file after extraction

    Examples:
        # Basic usage (download, extract, import)
        python setup_dataset.py

        # Custom database
        python setup_dataset.py --database my_db

        # Remote MongoDB
        python setup_dataset.py --mongo-uri mongodb://host:27017/

        # Don't clear existing data
        python setup_dataset.py --no-clear
"""

import os
import sys
import argparse
import zipfile
import shutil
from pathlib import Path
import subprocess

# Import the existing CSV importer
from import_csv_to_mongodb import ProcurementDataImporter


class DatasetSetup:
    """Handles complete dataset setup: download, extract, rename, import"""

    def __init__(
        self,
        data_dir="data",
        kaggle_url="https://www.kaggle.com/api/v1/datasets/download/sohier/large-purchases-by-the-state-of-ca",
        mongo_uri="mongodb://localhost:27017/",
        db_name="procurement_db",
        collection_name="procurement_data",
        batch_size=1000,
        clear_existing=True,
        keep_zip=False,
    ):
        self.data_dir = Path(data_dir)
        self.kaggle_url = kaggle_url
        self.zip_file = self.data_dir / "large-purchases-by-the-state-of-ca.zip"
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.collection_name = collection_name
        self.batch_size = batch_size
        self.clear_existing = clear_existing
        self.keep_zip = keep_zip
        self.csv_file = None  # Will be set after extraction

    def create_data_directory(self):
        """Create data directory if it doesn't exist"""
        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True, exist_ok=True)
            print(f"[OK] Created data directory: {self.data_dir}")
        else:
            print(f"[OK] Data directory exists: {self.data_dir}")

    def download_dataset(self):
        """Download the dataset from Kaggle"""
        print()
        print("=" * 70)
        print("STEP 1: DOWNLOADING DATASET FROM KAGGLE")
        print("=" * 70)
        print(f"Source: {self.kaggle_url}")
        print(f"Destination: {self.zip_file}")
        print()

        if self.zip_file.exists():
            print(f"[WARNING] ZIP file already exists: {self.zip_file}")
            response = input("Do you want to re-download? (y/n): ").lower()
            if response != 'y':
                print("[OK] Using existing ZIP file")
                return True

        try:
            # Use curl to download
            print("Downloading... (this may take a few minutes)")
            result = subprocess.run(
                [
                    "curl",
                    "-L",
                    "-o",
                    str(self.zip_file),
                    self.kaggle_url
                ],
                capture_output=True,
                text=True,
                check=True
            )

            if self.zip_file.exists() and self.zip_file.stat().st_size > 0:
                size_mb = self.zip_file.stat().st_size / (1024 * 1024)
                print(f"[OK] Download complete: {size_mb:.2f} MB")
                return True
            else:
                print("[FAILED] Download failed or file is empty")
                return False

        except subprocess.CalledProcessError as e:
            print(f"[FAILED] Download error: {e}")
            print(f"stderr: {e.stderr}")
            return False
        except FileNotFoundError:
            print("[FAILED] curl command not found. Please install curl:")
            print("  - Ubuntu/Debian: sudo apt-get install curl")
            print("  - macOS: curl is pre-installed")
            print("  - Windows: download from https://curl.se/windows/")
            return False

    def extract_zip(self):
        """Extract the ZIP file"""
        print()
        print("=" * 70)
        print("STEP 2: EXTRACTING ZIP FILE")
        print("=" * 70)
        print()

        if not self.zip_file.exists():
            print(f"[FAILED] ZIP file not found: {self.zip_file}")
            return False

        try:
            with zipfile.ZipFile(self.zip_file, 'r') as zip_ref:
                # List files in ZIP
                file_list = zip_ref.namelist()
                print(f"Files in ZIP: {len(file_list)}")
                for filename in file_list:
                    print(f"  - {filename}")

                # Extract all
                print()
                print(f"Extracting to: {self.data_dir}")
                zip_ref.extractall(self.data_dir)
                print("[OK] Extraction complete")

                # Find CSV files
                csv_files = [f for f in file_list if f.lower().endswith('.csv')]
                if csv_files:
                    self.csv_file = self.data_dir / csv_files[0]
                    print(f"[OK] Found CSV file: {csv_files[0]}")
                else:
                    print("[WARNING] No CSV files found in ZIP")
                    return False

            return True

        except zipfile.BadZipFile:
            print(f"[FAILED] Invalid ZIP file: {self.zip_file}")
            return False
        except Exception as e:
            print(f"[FAILED] Extraction error: {e}")
            return False

    def rename_csv_file(self):
        """Rename CSV file: replace spaces with underscores"""
        print()
        print("=" * 70)
        print("STEP 3: RENAMING CSV FILE")
        print("=" * 70)
        print()

        if not self.csv_file or not self.csv_file.exists():
            print("[FAILED] CSV file not found")
            return False

        original_name = self.csv_file.name

        # Replace spaces with underscores
        new_name = original_name.replace(' ', '_')

        if original_name == new_name:
            print(f"[OK] Filename already clean: {original_name}")
            return True

        new_path = self.csv_file.parent / new_name

        try:
            # Rename the file
            self.csv_file.rename(new_path)
            print(f"Renamed:")
            print(f"  From: {original_name}")
            print(f"  To:   {new_name}")

            # Update the csv_file path
            self.csv_file = new_path
            print("[OK] Rename complete")
            return True

        except Exception as e:
            print(f"[FAILED] Rename error: {e}")
            return False

    def import_to_mongodb(self):
        """Import CSV to MongoDB using existing importer"""
        print()
        print("=" * 70)
        print("STEP 4: IMPORTING TO MONGODB")
        print("=" * 70)
        print()

        if not self.csv_file or not self.csv_file.exists():
            print("[FAILED] CSV file not found for import")
            return False

        try:
            importer = ProcurementDataImporter(
                csv_file=str(self.csv_file),
                mongo_uri=self.mongo_uri,
                db_name=self.db_name,
                collection_name=self.collection_name,
                batch_size=self.batch_size,
                clear_existing=self.clear_existing,
            )

            importer.run()
            return True

        except Exception as e:
            print(f"[FAILED] Import error: {e}")
            return False

    def cleanup(self):
        """Clean up downloaded ZIP file if not keeping"""
        if not self.keep_zip and self.zip_file.exists():
            print()
            print("=" * 70)
            print("CLEANUP")
            print("=" * 70)
            try:
                self.zip_file.unlink()
                print(f"[OK] Removed ZIP file: {self.zip_file}")
            except Exception as e:
                print(f"[WARNING] Could not remove ZIP file: {e}")

    def print_final_summary(self):
        """Print final summary"""
        print()
        print("=" * 70)
        print("SETUP COMPLETE")
        print("=" * 70)
        print()
        print("Data Directory:", self.data_dir.absolute())
        print("CSV File:", self.csv_file.absolute() if self.csv_file else "Not found")
        print("MongoDB:", f"{self.mongo_uri}{self.db_name}/{self.collection_name}")
        print()
        print("Next Steps:")
        print("  1. Start the MongoDB server if not running")
        print("  2. Run the procurement assistant:")
        print("     python procurement_agent/api/main.py")
        print("  3. Open browser: http://localhost:8000")
        print()
        print("=" * 70)

    def run(self):
        """Main execution flow"""
        print("=" * 70)
        print("CALIFORNIA PROCUREMENT DATA - COMPLETE SETUP")
        print("=" * 70)
        print()
        print("This script will:")
        print("  1. Download dataset from Kaggle")
        print("  2. Extract ZIP file")
        print("  3. Rename CSV file (replace spaces with _)")
        print("  4. Import to MongoDB with proper type conversion")
        print()

        # Step 1: Create data directory
        self.create_data_directory()

        # Step 2: Download dataset
        if not self.download_dataset():
            sys.exit(1)

        # Step 3: Extract ZIP
        if not self.extract_zip():
            sys.exit(1)

        # Step 4: Rename CSV file
        if not self.rename_csv_file():
            sys.exit(1)

        # Step 5: Import to MongoDB
        if not self.import_to_mongodb():
            sys.exit(1)

        # Step 6: Cleanup
        self.cleanup()

        # Final summary
        self.print_final_summary()


def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Complete dataset setup: download, extract, rename, and import",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage (download, extract, import)
  python setup_dataset.py

  # Custom database
  python setup_dataset.py --database my_db

  # Remote MongoDB
  python setup_dataset.py --mongo-uri mongodb://user:pass@host:27017/

  # Don't clear existing data
  python setup_dataset.py --no-clear

  # Keep ZIP file after extraction
  python setup_dataset.py --keep-zip
        """,
    )

    parser.add_argument(
        "--data-dir",
        type=str,
        default="data",
        help="Data directory path (default: data)",
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
        default="procurement_data",
        help="Collection name (default: procurement_data)",
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

    parser.add_argument(
        "--keep-zip",
        action="store_true",
        help="Keep the downloaded ZIP file after extraction",
    )

    return parser.parse_args()


def main():
    """Entry point"""
    args = parse_arguments()

    setup = DatasetSetup(
        data_dir=args.data_dir,
        mongo_uri=args.mongo_uri,
        db_name=args.database,
        collection_name=args.collection,
        batch_size=args.batch_size,
        clear_existing=not args.no_clear,
        keep_zip=args.keep_zip,
    )

    setup.run()


if __name__ == "__main__":
    main()
