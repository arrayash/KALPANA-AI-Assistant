import os
import re
import json
import oracledb
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from fastapi.middleware.cors import CORSMiddleware

from visualizer import generate_visualization, get_available_viz_types, VisualizationRequest
from memory import( HistoryMessage, init_memory,
    get_session, rewrite_query, clear_session, get_store_stats
   )

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"Hello": "World"}


# =========================
# Database Configuration
# =========================
DB_CONFIG = {
    "user": "rag_user",
    "password": "rag123",
    "dsn": "localhost:1521/FREEPDB1"
}


def get_db_connection():
    return oracledb.connect(**DB_CONFIG)


# =========================
# LLM Configuration
# =========================
groq_api_key = os.getenv("GROQ_API_KEY")
llm = ChatGroq(api_key=groq_api_key, model="llama-3.3-70b-versatile", temperature=0)

# Initialise memory module (QueryRewriter + SessionStore)
init_memory(groq_api_key)

prompt_template = ChatPromptTemplate.from_template("""
You are an AI assistant for ISRO mission data.
Answer using ONLY the provided context chunks below.
Do NOT use outside knowledge.

Rules:
- If the context has partial information, answer with what is available and mention what is missing.
- If comparing two missions, compare whatever details are present for each.
- If a specific fact is not in the context, say "not mentioned in the Knowldege Base" for that specific fact only.
- Only say "I don't have enough information" if the context has NO relevant information at all.

Conversation History (for context only — do not answer old questions again):
{history}

Context from MOSDAC documents:  
{context}

Current Question: {question}

Answer:
""")


# =========================
# Content Cleaning
# =========================
SKIP_TITLES = {"data products", "documents"}
SKIP_CONTENT_PREFIXES = (
    "content for this page could not be found",
    "placeholder for extracted text",
)


def clean_text(text: str) -> str:
    """Fix HTML scraping artifacts like 'I\\nNSAT' -> 'INSAT', 'T\\nhe' -> 'The'"""
    if not text:
        return ""
    text = re.sub(r'(?m)^([A-Za-z])\n([a-zA-Z])', r'\1\2', text)
    text = re.sub(r'\b([A-Z])\n([a-z])', r'\1\2', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def is_valid_content(content: str) -> bool:
    """Returns False for placeholder/missing content"""
    if not content or len(content.strip()) < 50:
        return False
    lower = content.strip().lower()
    return not any(lower.startswith(p) for p in SKIP_CONTENT_PREFIXES)


def extract_sections(missions: list) -> list:
    """
    Extracts all indexable (mission_name, section_title, source_url, content) tuples
    from the JSON structure, skipping useless sections.
    """
    sections = []
    for mission in missions:
        mission_name = mission.get("mission_name", "Unknown")

        # 1. main_page_content -> "Overview" section
        main_content = clean_text(mission.get("main_page_content", ""))
        if is_valid_content(main_content):
            sections.append({
                "mission_name":  mission_name,
                "section_title": "Overview",
                "source_url":    mission.get("url", ""),
                "content":       main_content
            })

        # 2. sub_pages -> each sub page is a section
        for sub in mission.get("sub_pages", []):
            title   = sub.get("title", "").strip()
            url     = sub.get("url", "")
            content = clean_text(sub.get("content", ""))

            if title.lower() in SKIP_TITLES:
                continue
            if not is_valid_content(content):
                continue

            sections.append({
                "mission_name":  mission_name,
                "section_title": title,
                "source_url":    url,
                "content":       content
            })

            # 3. scraped_documents inside sub_pages (when real PDF text exists)
            for doc in sub.get("scraped_documents", []):
                doc_text = clean_text(doc.get("extracted_text", ""))
                doc_url  = doc.get("document_url", "")
                if is_valid_content(doc_text):
                    filename = doc_url.split("/")[-1].replace(".pdf", "").replace("_", " ").replace("-", " ")
                    sections.append({
                        "mission_name":  mission_name,
                        "section_title": f"PDF: {filename[:60]}",
                        "source_url":    doc_url,
                        "content":       doc_text
                    })

    return sections


# =========================
# Upload & Vectorize
# =========================
@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Read and decode
        file_bytes = await file.read()
        raw_content = file_bytes.decode("utf-8", errors="replace")

        # 2. Parse JSON
        try:
            json_data = json.loads(raw_content, strict=False)
        except json.JSONDecodeError as je:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"JSON Error: {je.msg} at line {je.lineno}, col {je.colno}. "
                    f"Check near: {raw_content[je.pos - 20:je.pos + 20]}"
                )
            )

        # 3. Insert raw JSON
        insert_raw_sql = (
            "INSERT INTO mission_data (json_doc) VALUES (:1) RETURNING id INTO :2"
        )
        new_id_var = cursor.var(oracledb.NUMBER)
        cursor.execute(insert_raw_sql, [json.dumps(json_data), new_id_var])
        new_id = int(new_id_var.getvalue()[0])

        # 4. Extract clean sections in Python
        missions = json_data if isinstance(json_data, list) else [json_data]
        sections = extract_sections(missions)
        print(f"DEBUG: Extracted {len(sections)} sections from JSON")

        # 5. Chunk each section and insert embeddings
        chunk_sql = """
            INSERT INTO mission_chunks
                (mission_name, source_url, section_title, chunk_text, embedding)
            SELECT
                :mission_name,
                :source_url,
                :section_title,
                :section_title || ' | ' || ct.chunk_data   AS chunk_text,
                VECTOR_EMBEDDING(
                    DOC_MODEL USING (
                        :mission_name || ' ' || :section_title || ': ' || ct.chunk_data
                    ) AS data
                )                                           AS embedding
            FROM TABLE(
                DBMS_VECTOR_CHAIN.UTL_TO_CHUNKS(
                    :content,
                    JSON('{"by":"words","max":"100","overlap":"15","split":"sentence","normalize":"all"}')
                )
            ) vt,
            JSON_TABLE(
                vt.column_value, '$'
                COLUMNS (chunk_data CLOB PATH '$.chunk_data')
            ) ct
            WHERE ct.chunk_data IS NOT NULL
              AND LENGTH(TRIM(ct.chunk_data)) > 20
        """

        total_chunks = 0
        for sec in sections:
            cursor.execute(chunk_sql, {
                "mission_name":  sec["mission_name"],
                "source_url":    sec["source_url"],
                "section_title": sec["section_title"],
                "content":       sec["content"]
            })
            total_chunks += cursor.rowcount
            print(f"  -> {sec['mission_name']} / {sec['section_title']}: {cursor.rowcount} chunks")

        try:
            cursor.execute("BEGIN CTX_DDL.SYNC_INDEX('mission_txt_idx'); END;")
        except Exception as sync_err:
            print(f"WARNING: Index sync failed (non-fatal): {sync_err}")

        conn.commit()

        return {
            "status":             "success",
            "mission_id":         new_id,
            "sections_processed": len(sections),
            "chunks_inserted":    total_chunks
        }

    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"DEBUG ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


# =========================
# Vector Search (RAG)
# =========================
class Question(BaseModel):
    query: str
    session_id: str = "default"                 # identifies the conversation session
    history: list[HistoryMessage] = []          # optional: client can pass history directly


@app.post("/ask")
async def ask_question(request: Question):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # ───────────────────────────────
        # Step 1: Get session memory
        # ───────────────────────────────
        memory = get_session(request.session_id)

        # If client sends history explicitly, use that
        history = request.history if request.history else memory.get_history()

        # ───────────────────────────────
        # Step 2: Rewrite query using memory
        # ───────────────────────────────
        search_query, was_rewritten = rewrite_query(
            request.query,
            history
        )

        print(f"[ASK] Original: {request.query}")
        if was_rewritten:
            print(f"[ASK] Rewritten: {search_query}")

        # ───────────────────────────────
        # Step 3: Vector search
        # ───────────────────────────────
        vector_search_sql = """
            SELECT chunk_text, mission_name, section_title, source_url, distance
            FROM (
                SELECT chunk_text, mission_name, section_title, source_url,
                       VECTOR_DISTANCE(
                           embedding,
                           VECTOR_EMBEDDING(DOC_MODEL USING :q AS data),
                           COSINE
                       ) as distance,
                       ROW_NUMBER() OVER (
                           PARTITION BY mission_name, section_title
                           ORDER BY VECTOR_DISTANCE(
                               embedding,
                               VECTOR_EMBEDDING(DOC_MODEL USING :q AS data),
                               COSINE
                           )
                       ) as rn
                FROM mission_chunks
            )
            WHERE rn <= 3
            ORDER BY distance
            FETCH FIRST 10 ROWS ONLY
        """

        cursor.execute(vector_search_sql, q=search_query)
        rows = cursor.fetchall()

        if not rows:
            return {
                "query": request.query,
                "rewritten_query": search_query if was_rewritten else None,
                "answer": "I don't have enough information in the Knowledge Base to answer this.",
                "chunks": [],
                "sources": []
            }

        context_list = []
        chunks_meta  = []
        sources_seen = set()

        for r in rows:
            chunk_col  = r[0]
            mission    = r[1]
            section    = r[2]
            source_url = r[3] or ""
            distance   = round(float(r[4]), 4)

            text = chunk_col.read() if hasattr(chunk_col, "read") else str(chunk_col)

            # Skip weak matches
            if distance > 0.80:
                continue

            chunks_meta.append({
                "mission": mission,
                "section": section,
                "distance": distance,
                "source_url": source_url
            })

            if source_url:
                sources_seen.add(source_url)

            if " | " in text:
                clean_val = text.split(" | ", 1)[1]
            else:
                clean_val = text

            context_list.append(
                f"[Mission: {mission} | Section: {section}]\n{clean_val}"
            )

        if not context_list:
            return {
                "query": request.query,
                "rewritten_query": search_query if was_rewritten else None,
                "answer": "I don't have enough information in the provided documents to answer this.",
                "chunks": [],
                "sources": []
            }

        # ───────────────────────────────
        # Step 4: Build LLM context
        # ───────────────────────────────
        context = "\n\n---\n\n".join(context_list)
        history_text = memory.format_for_prompt()

        chain = prompt_template | llm

        response = chain.invoke({
            "context": context,
            "question": request.query,
            "history": history_text
        })

        answer = response.content if hasattr(response, "content") else str(response)

        # ───────────────────────────────
        # Step 5: Save conversation to memory
        # ───────────────────────────────
        memory.add("user", request.query)
        memory.add("assistant", answer)

        return {
            "query": request.query,
            "rewritten_query": search_query if was_rewritten else None,
            "answer": answer,
            "chunks": chunks_meta,
            "sources": list(sources_seen),
            "session_id": request.session_id,
            "history_length": len(memory),
            "viz_buttons": get_available_viz_types(request.query, answer)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


# =========================
# Memory Endpoints
# =========================
@app.post("/memory/clear/{session_id}")
async def clear_memory(session_id: str):
    """Clear conversation history for a specific session."""
    clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}


@app.get("/memory/stats")
async def memory_stats():
    """Returns count of active sessions in memory."""
    return get_store_stats()


# =========================
# Visualization Endpoint
# =========================
class VizRequest(BaseModel):
    query: str
    answer: str
    viz_type: str          # "3d_orbit" | "payload_specs" | "comparison_chart"


@app.post("/visualize")
async def generate_viz(request: VizRequest):
    """
    Generate a self-contained Three.js / Chart.js HTML visualization.
    No external API key required — all rendering is done locally via visualizer.py.
    """
    print(request.answer)
    result = await generate_visualization(
        query=request.query,
        answer=request.answer,
        viz_type=request.viz_type,
        # gemini_api_key kept for signature compatibility but not used
    )

    if result.error:
        raise HTTPException(status_code=500, detail=result.error)

    return {
        "viz_type":     result.viz_types[0] if result.viz_types else request.viz_type,
        "html":         result.html,
        "missions":     list(result.extracted_data.keys()),
        "orbital_data": result.extracted_data
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)