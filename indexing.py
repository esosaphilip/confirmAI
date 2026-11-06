import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import Chroma

embeddings = OllamaEmbeddings(model="nomic-embed-text")

SinglePDFLoader = PyPDFLoader

def index_single_document(file_path: str, persist_directory: str):
    """
    Lädt ein einzelnes Dokument (entweder AB oder Rechnung), 
    chunkt es und speichert es in seiner eigenen ChromaDB-Collection.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Die Datei {file_path} wurde nicht gefunden.")
        
    loader = SinglePDFLoader(file_path)
    pages = loader.load()
    
    # Text in Chunks aufteilen
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, 
        chunk_overlap=100
    )
    chunks = text_splitter.split_documents(pages)

    # Persistent in der spezifischen Datenbank speichern
    vectorstore = Chroma.from_documents(
        documents=chunks, 
        embedding=embeddings, 
        persist_directory=persist_directory
    )
    
    print(f"Erfolgreich {len(chunks)} Chunks für {file_path} in {persist_directory} indexiert.")
    return vectorstore