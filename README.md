# Kalpana AI - ISRO MOSDAC Assistant

Kalpana AI is an intelligent, interactive assistant designed exclusively around data from the **MOSDAC (Meteorological & Oceanographic Satellite Data Archival Centre)** portal of **ISRO**. It serves as a specialized knowledge base and visualization tool, allowing users to naturally query complex space mission data and visualize spacecraft capabilities.

## What It Is

The system extracts, indexes, and queries extensive documents and web pages sourced strictly from ISRO's MOSDAC portal. By combining an advanced Retrieval-Augmented Generation (RAG) architecture with interactive frontend components, Kalpana AI can:
- Answer specific questions regarding meteorological and oceanographic missions based only on verified MOSDAC data.
- Retain conversation memory for follow-up queries and context-aware interactions.
- Dynamically generate 3D orbital visualizations and payload specification charts corresponding to the retrieved mission data.

## Tech Stack

**Frontend**
- **React & Vite**: Powers the fast, interactive user interface.
- **Three.js & Chart.js**: Used for rendering in-browser 3D spacecraft orbits and comparative data charts locally.

**Backend**
- **Python & FastAPI**: Serves as the robust, high-performance API routing layer.
- **Oracle DB (Vector Search)**: Handles the storage and cosine-similarity retrieval of chunked MOSDAC document embeddings.
- **LangChain & Groq (Llama 3)**: Manages the prompt orchestration, query rewriting, and LLM text generation, ensuring the AI strictly answers using the provided MOSDAC context.
