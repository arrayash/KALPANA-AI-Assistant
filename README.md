# Kalpana AI - Spacecraft Visualization & RAG System

Kalpana AI is an intelligent assistant for ISRO mission data, featuring an advanced retrieval-augmented generation (RAG) backend and dynamic 3D spacecraft visualizations.

## Directory Structure

- `backend/`: Contains the FastAPI application, vector search logic, memory management, and visualization generator.
- `frontend/`: Contains the React-based user interface.
- `Scrapped Content/`: Miscellaneous data or content used for training/referencing.

## Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables. Create a `.env` file in the `backend` directory with at least:
   ```env
   GROQ_API_KEY=your_groq_api_key
   ```
5. Run the development server:
   ```bash
   uvicorn main:app --reload
   ```

## Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the frontend server:
   ```bash
   npm run dev
   ```

## Features
- **Retrieval-Augmented Generation (RAG)**: Integrates OracleDB vector search with the LLM (Llama 3 via Groq) to accurately respond to questions about ISRO missions based on MOSDAC documents.
- **3D Visualization**: Renders spacecraft models and orbital trajectories locally using Three.js and Chart.js, powered by a custom Python visualizer.
- **Session Memory**: Preserves context across conversations for accurate query rewriting and continued discussions.
