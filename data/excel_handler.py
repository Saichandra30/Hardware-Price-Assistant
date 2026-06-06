"""
Data layer module for handling Excel operations.
"""

import os
import glob
import pandas as pd
import openpyxl
import logging

logger = logging.getLogger(__name__)

class ExcelHandler:
    """
    Class to manage reading and writing Excel files for hardware prices.
    """

    def __init__(self, file_path: str = None):
        """
        Initialize the ExcelHandler. If file_path is not provided, 
        it searches for an Excel file in the project root or data/ dir.

        Args:
            file_path (str, optional): The path to the Excel file.
        """
        if file_path:
            self.file_path = file_path
        else:
            self.file_path = self._find_excel_file()
            
    def _find_excel_file(self) -> str:
        """Find the Excel file automatically."""
        # Try finding in the data directory first
        files = glob.glob("data/*.xlsx")
        if not files:
            # Try finding in the root directory
            files = glob.glob("*.xlsx")
            
        if not files:
            logger.error("No Excel file found in root or data/ directory.")
            raise FileNotFoundError("Could not locate the Excel data file.")
            
        # Return the first found Excel file
        logger.info(f"Located Excel file at: {files[0]}")
        return files[0]

    def load_data(self) -> dict[str, pd.DataFrame]:
        """
        Load data from all sheets in the Excel file.

        Returns:
            dict[str, pd.DataFrame]: A dictionary mapping sheet names to DataFrames.
        """
        logger.info(f"Loading data from {self.file_path}")
        try:
            # Read all sheets, header=None to parse raw data structure
            return pd.read_excel(self.file_path, sheet_name=None, header=None)
        except Exception as e:
            logger.error(f"Error reading Excel file: {e}")
            raise
