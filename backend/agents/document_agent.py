"""Document Agent: Processes PDFs and documents with OCR and extraction.

This agent handles:
- PDF text extraction using pdfplumber
- Document chunking for retrieval
- Semantic search via ChromaDB
- Structured data extraction from invoices, contracts, reports
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

import chromadb
import pdfplumber
from langchain_core.messages import HumanMessage, SystemMessage

from backend.core.config import settings
from backend.core.llm import get_llm, invoke_llm_with_retry
from backend.core.models import (
    AgentStep,
    AgentType,
    DocumentChunk,
    DocumentResult,
    SourceReference,
)

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """\
You are a document analysis expert. Analyze the following document content \
and answer the user's question.

DOCUMENT CONTENT:
{content}

RULES:
1. Only use information from the provided document content.
2. If the information is not in the documents, say so clearly.
3. Quote specific values, dates, and amounts from the documents.
4. Reference which document/page the information comes from.

Respond with a clear, concise answer."""

STRUCTURED_EXTRACTION_PROMPT = """Extract structured data from this document content.

DOCUMENT CONTENT:
{content}

Extract the following fields if present (return JSON, no code fences):
{{
    "document_type": "invoice/contract/report/other",
    "dates": [{{"label": "...", "value": "YYYY-MM-DD"}}],
    "amounts": [{{"label": "...", "value": 0.00, "currency": "USD"}}],
    "parties": [{{"role": "...", "name": "..."}}],
    "key_terms": ["..."],
    "status": "...",
    "summary": "One-line summary"
}}"""


class DocumentAgent:
    """Agent for processing and querying business documents."""

    def __init__(self, provider: str | None = None) -> None:
        self.llm = get_llm(provider=provider, temperature=0)
        self.chunk_size = settings.document_agent_chunk_size
        self.chunk_overlap = settings.document_agent_chunk_overlap

        # Initialize ChromaDB
        self.chroma_client = chromadb.Client(chromadb.Settings(
            persist_directory=settings.chroma_persist_dir,
            anonymized_telemetry=False,
        ))
        self.collection = self.chroma_client.get_or_create_collection(
            name="datapilot_documents",
            metadata={"hnsw:space": "cosine"},
        )

    def _extract_text_from_pdf(self, file_path: str) -> list[DocumentChunk]:
        """Extract text from PDF using pdfplumber."""
        chunks: list[DocumentChunk] = []
        file_name = Path(file_path).name

        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                if not text.strip():
                    continue

                # Split page text into chunks
                words = text.split()
                for i in range(0, len(words), self.chunk_size - self.chunk_overlap):
                    chunk_words = words[i : i + self.chunk_size]
                    if not chunk_words:
                        continue
                    chunk_text = " ".join(chunk_words)
                    chunks.append(DocumentChunk(
                        content=chunk_text,
                        source_file=file_name,
                        page_number=page_num,
                        chunk_index=len(chunks),
                        metadata={"file_path": file_path},
                    ))

                # Also extract tables
                tables = page.extract_tables()
                for table in tables:
                    if table:
                        table_text = "\n".join(
                            [" | ".join(str(cell or "") for cell in row) for row in table]
                        )
                        chunks.append(DocumentChunk(
                            content=f"[TABLE from page {page_num}]\n{table_text}",
                            source_file=file_name,
                            page_number=page_num,
                            chunk_index=len(chunks),
                            metadata={"file_path": file_path, "type": "table"},
                        ))

        return chunks

    def _extract_text_from_txt(self, file_path: str) -> list[DocumentChunk]:
        """Extract text from plain text files."""
        file_name = Path(file_path).name
        chunks: list[DocumentChunk] = []

        with open(file_path, encoding="utf-8", errors="ignore") as f:
            text = f.read()

        words = text.split()
        for i in range(0, len(words), self.chunk_size - self.chunk_overlap):
            chunk_words = words[i : i + self.chunk_size]
            if chunk_words:
                chunks.append(DocumentChunk(
                    content=" ".join(chunk_words),
                    source_file=file_name,
                    page_number=1,
                    chunk_index=len(chunks),
                    metadata={"file_path": file_path},
                ))

        return chunks

    def ingest_file(self, file_path: str) -> list[DocumentChunk]:
        """Ingest a document file and store chunks in ChromaDB."""
        ext = Path(file_path).suffix.lower()

        if ext == ".pdf":
            chunks = self._extract_text_from_pdf(file_path)
        elif ext in (".txt", ".md", ".csv"):
            chunks = self._extract_text_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported file type: {ext}")

        if not chunks:
            return []

        # Store in ChromaDB
        self.collection.upsert(
            ids=[f"{Path(file_path).stem}_{c.chunk_index}" for c in chunks],
            documents=[c.content for c in chunks],
            metadatas=[
                {
                    "source_file": c.source_file,
                    "page_number": c.page_number,
                    "chunk_index": c.chunk_index,
                }
                for c in chunks
            ],
        )

        logger.info("Ingested %d chunks from %s", len(chunks), file_path)
        return chunks

    def ingest_directory(self, dir_path: str) -> int:
        """Ingest all supported documents from a directory."""
        total_chunks = 0
        supported_exts = {".pdf", ".txt", ".md", ".csv"}

        for file_name in os.listdir(dir_path):
            if Path(file_name).suffix.lower() in supported_exts:
                full_path = os.path.join(dir_path, file_name)
                chunks = self.ingest_file(full_path)
                total_chunks += len(chunks)

        return total_chunks

    def _search_documents(self, query: str, n_results: int = 5) -> list[DocumentChunk]:
        """Search ChromaDB for relevant document chunks."""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
            )
        except Exception as e:
            logger.warning("ChromaDB search failed: %s", e)
            return []

        chunks = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                chunks.append(DocumentChunk(
                    content=doc,
                    source_file=meta.get("source_file", "unknown"),
                    page_number=meta.get("page_number", 0),
                    chunk_index=meta.get("chunk_index", 0),
                ))

        return chunks

    async def process(self, question: str) -> tuple[DocumentResult, list[AgentStep]]:
        """Process a question against ingested documents."""
        steps: list[AgentStep] = []

        # Step 1: Search for relevant chunks
        search_start = time.time()
        chunks = self._search_documents(question)
        search_duration = int((time.time() - search_start) * 1000)

        steps.append(AgentStep(
            agent=AgentType.DOCUMENT,
            action="search_documents",
            input_summary=question[:100],
            output_summary=f"Found {len(chunks)} relevant chunks",
            confidence=0.8 if chunks else 0.0,
            duration_ms=search_duration,
        ))

        if not chunks:
            return DocumentResult(
                summary="No relevant documents found. Please upload documents first.",
                confidence=0.0,
            ), steps

        # Step 2: Generate answer from chunks
        combined_content = "\n\n---\n\n".join(
            f"[{c.source_file}, Page {c.page_number}]\n{c.content}" for c in chunks
        )

        answer_start = time.time()
        messages = [
            SystemMessage(content=EXTRACTION_PROMPT.format(content=combined_content)),
            HumanMessage(content=question),
        ]
        response = await invoke_llm_with_retry(self.llm, messages)
        answer_duration = int((time.time() - answer_start) * 1000)

        steps.append(AgentStep(
            agent=AgentType.DOCUMENT,
            action="analyze_documents",
            input_summary=f"{len(chunks)} chunks analyzed",
            output_summary=response.content[:100],
            confidence=0.8,
            duration_ms=answer_duration,
        ))

        return DocumentResult(
            chunks=chunks,
            summary=response.content,
            confidence=0.8,
        ), steps

    async def extract_structured(self, file_path: str) -> tuple[dict[str, Any], list[AgentStep]]:
        """Extract structured data from a single document."""
        steps: list[AgentStep] = []

        # Get chunks from file
        ext = Path(file_path).suffix.lower()
        if ext == ".pdf":
            chunks = self._extract_text_from_pdf(file_path)
        else:
            chunks = self._extract_text_from_txt(file_path)

        combined = "\n".join(c.content for c in chunks[:10])  # First 10 chunks

        extract_start = time.time()
        messages = [
            SystemMessage(content=STRUCTURED_EXTRACTION_PROMPT.format(content=combined)),
            HumanMessage(content="Extract all structured data from this document."),
        ]
        response = await invoke_llm_with_retry(self.llm, messages)
        extract_duration = int((time.time() - extract_start) * 1000)

        steps.append(AgentStep(
            agent=AgentType.DOCUMENT,
            action="extract_structured_data",
            input_summary=Path(file_path).name,
            output_summary=response.content[:100],
            confidence=0.85,
            duration_ms=extract_duration,
        ))

        try:
            import json

            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            extracted = json.loads(content)
        except (json.JSONDecodeError, IndexError):
            extracted = {"raw_response": response.content}

        return extracted, steps

    def get_sources(self, result: DocumentResult) -> list[SourceReference]:
        """Extract source references from document result."""
        seen = set()
        sources = []
        for chunk in result.chunks:
            key = f"{chunk.source_file}:{chunk.page_number}"
            if key not in seen:
                seen.add(key)
                sources.append(SourceReference(
                    source_type="document",
                    source_name=chunk.source_file,
                    details=f"Page {chunk.page_number}",
                ))
        return sources
