#!/usr/bin/env python3
# -*- coding: utf-8 -*-

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    REQUESTS_AVAILABLE = True
except ImportError:
    requests = None
    HTTPAdapter = None
    Retry = None
    REQUESTS_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BeautifulSoup = None
    BS4_AVAILABLE = False

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    from docx import Document
    HAS_DOCX = True
except ImportError:
    Document = None
    HAS_DOCX = False

try:
    from pypdf import PdfReader
    HAS_PDF = True
except ImportError:
    try:
        from PyPDF2 import PdfReader
        HAS_PDF = True
    except ImportError:
        PdfReader = None
        HAS_PDF = False

try:
    from pptx import Presentation
    HAS_PPTX = True
except ImportError:
    Presentation = None
    HAS_PPTX = False

try:
    import arxiv
    ARXIV_AVAILABLE = True
except ImportError:
    arxiv = None
    ARXIV_AVAILABLE = False

# sentence_transformers 可选
SENTENCE_TRANSFORMERS_AVAILABLE = False
print("注意：sentence_transformers 未强制要求，系统将使用内置检索")



__all__ = [
    "REQUESTS_AVAILABLE", "requests", "HTTPAdapter", "Retry",
    "BS4_AVAILABLE", "BeautifulSoup",
    "pd", "Document", "HAS_DOCX", "PdfReader", "HAS_PDF",
    "Presentation", "HAS_PPTX", "arxiv", "ARXIV_AVAILABLE",
    "SENTENCE_TRANSFORMERS_AVAILABLE",
]
