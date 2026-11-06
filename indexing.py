import os
import time

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from logging_config import get_logger

logger = get_logger("indexing")


def index_single_document(file_path: str, persist_directory: str):
    """
    Lädt ein einzelnes Dokument (entweder AB oder Rechnung),
    chunkt es und speichert es in seiner eigenen ChromaDB-Collection.

    Blockierend (PDF-Parsing + Embeddings): im Server per
    ``asyncio.to_thread`` aufrufen.
    """
    from langchain_community.vectorstores import Chroma

    from vergleicher import get_embeddings

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Die Datei {file_path} wurde nicht gefunden.")

    started = time.perf_counter()
    pages = PyPDFLoader(file_path).load()
    if not any(page.page_content.strip() for page in pages):
        raise ValueError(
            f"{os.path.basename(file_path)} enthält keinen lesbaren Text (gescanntes PDF ohne OCR?)."
        )

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = text_splitter.split_documents(pages)

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=get_embeddings(),
        persist_directory=persist_directory,
    )

    logger.info(
        "Document indexed",
        extra={"fields": {
            "file": file_path,
            "pages": len(pages),
            "chunks": len(chunks),
            "persist_dir": persist_directory,
            "duration_ms": round((time.perf_counter() - started) * 1000),
        }},
    )
    return vectorstore
