"""
Service layer containing core business logic for the Hardware Price Assistant.
"""

from data.excel_handler import ExcelHandler
from llm.gemini_client import GeminiClient

class PriceService:
    """
    Service class bridging the data layer and the LLM layer.
    """

    def __init__(self, excel_handler: ExcelHandler, llm_client: GeminiClient):
        """
        Initialize the PriceService.

        Args:
            excel_handler (ExcelHandler): Instance of ExcelHandler.
            llm_client (GeminiClient): Instance of GeminiClient.
        """
        self.excel_handler = excel_handler
        self.llm_client = llm_client

    def process_query(self, query: str) -> str:
        """
        Process a user query regarding hardware prices.

        Args:
            query (str): The user's query.

        Returns:
            str: The assistant's response.
        """
        pass
