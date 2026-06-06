"""
Main entry point for the GenAI Hardware Price Assistant application.
This file initializes the Streamlit app.
"""

import streamlit as st
from ui.app import run_app

def main():
    """Main application runner."""
    st.set_page_config(
        page_title="Hardware Price Assistant",
        page_icon="💻",
        layout="wide",
    )
    run_app()

if __name__ == "__main__":
    main()
