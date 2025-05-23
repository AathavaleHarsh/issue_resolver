# GitHub Issue Fetcher & Processor

This project consists of a React frontend and a Python FastAPI backend designed to fetch and process GitHub issues. The backend utilizes an agentic workflow for issue processing and streams logs to the frontend via WebSockets.

## Project Structure

```
issue-bot-explorer/
├── backend/            # Python FastAPI backend
│   ├── app/            # Main application logic (main.py)
│   ├── agentic_workflow/ # Logic for processing issues
│   ├── utils/          # Utility scripts (e.g., fetch_issues.py)
│   ├── requirements.txt # Python dependencies
│   ├── Dockerfile      # Dockerfile for the backend
│   └── .env            # Environment variables for backend
├── public/             # Static assets for the frontend
├── src/                # React frontend source code (TypeScript, Vite)
│   ├── components/     # Reusable UI components (shadcn/ui)
│   ├── pages/          # Application pages (e.g., ChatPage.tsx)
│   └── App.tsx         # Main application component
├── Dockerfile          # Dockerfile for the frontend (likely)
├── docker-compose.yml  # Docker Compose configuration for multi-container setup
├── nginx.conf          # Nginx configuration (likely for reverse proxy/serving)
├── package.json        # Frontend dependencies and scripts
├── vite.config.ts      # Vite configuration
├── tsconfig.json       # TypeScript configuration
└── README.md           # This file
```

## Prerequisites

*   Node.js and npm (or Bun, as `bun.lockb` is present)
*   Python 3.x and pip
*   Docker and Docker Compose (optional, for containerized deployment)

## Setup and Running the Project

### Environment Variables

1.  **Backend:**
    *   Navigate to the `backend` directory: `cd backend`
    *   Create a `.env` file by copying from `.env.example`: `cp .env.example .env`
    *   Fill in the required environment variables in `backend/.env` (e.g., GitHub tokens, API keys for the agent).

2.  **Frontend (if applicable):**
    *   There's a root `.env` file. Check if it's used by the frontend and if it requires any specific variables (e.g., `VITE_API_BASE_URL` to point to the backend).

### 1. Running Locally (Frontend and Backend Separately)

**Backend (Python FastAPI):**

1.  **Navigate to the backend directory:**
    ```bash
    cd backend
    ```
2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    ```
3.  **Activate the virtual environment:**
    *   Windows:
        ```bash
        .\venv\Scripts\activate
        ```
    *   macOS/Linux:
        ```bash
        source venv/bin/activate
        ```
4.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
5.  **Run the FastAPI application (usually with uvicorn):**
    The `main.py` seems to be in `backend/app/main.py`. Uvicorn is typically run from the directory where you can import the app module.
    ```bash
    # From the 'backend' directory
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    ```
    (The port might be different, check your FastAPI app configuration or `.env` if specified there. Default FastAPI port is 8000 if not specified in `uvicorn` command or app itself.)

**Frontend (React + Vite):**

1.  **Navigate to the project root directory:**
    ```bash
    cd .. 
    # (If you are in the backend directory)
    ```
    Or open a new terminal in the root: `c:\Users\ACER\Desktop\Project\issue_resolver\issue-bot-explorer`

2.  **Install dependencies (using npm or bun):**
    *   Using npm:
        ```bash
        npm install
        ```
    *   Or using Bun (since `bun.lockb` is present):
        ```bash
        bun install
        ```
3.  **Run the development server:**
    *   Using npm:
        ```bash
        npm run dev
        ```
    *   Or using Bun:
        ```bash
        bun run dev
        ```
    The frontend will typically be available at `http://localhost:5173` (Vite's default) or as specified in `vite.config.ts`.

### 2. Running with Docker Compose (Frontend and Backend Together)

This method uses the `docker-compose.yml` file to build and run both frontend and backend services.

1.  **Ensure Docker Desktop is running.**
2.  **Navigate to the project root directory:**
    ```bash
    cd c:\Users\ACER\Desktop\Project\issue_resolver\issue-bot-explorer
    ```
3.  **Build and start the services:**
    ```bash
    docker-compose up --build
    ```
    To run in detached mode (in the background):
    ```bash
    docker-compose up --build -d
    ```
4.  **Accessing the application:**
    *   The application will likely be accessible via Nginx, typically on `http://localhost` or `http://localhost:80` (or another port if configured in `docker-compose.yml` or `nginx.conf`). Check the `ports` section in your `docker-compose.yml` for the Nginx service.

5.  **Stopping the services:**
    ```bash
    docker-compose down
    ```

## Building for Production

**Frontend:**

1.  Navigate to the project root.
2.  Run the build command:
    *   Using npm:
        ```bash
        npm run build
        ```
    *   Or using Bun:
        ```bash
        bun run build
        ```
    This will create a `dist` folder in the root directory with the optimized static assets.

**Backend:**

The backend is a Python application. For production, it's typically run within a Docker container using an ASGI server like Uvicorn with Gunicorn as a process manager.
The provided `backend/Dockerfile` and `docker-compose.yml` likely handle this setup.

## Key Technologies

*   **Frontend:** React, Vite, TypeScript, Tailwind CSS, shadcn/ui
*   **Backend:** Python, FastAPI, Uvicorn, WebSockets
*   **Containerization:** Docker, Docker Compose
*   **Web Server/Proxy:** Nginx (likely)

## Further Development

*   **Linting (Frontend):** `npm run lint` or `bun run lint`
*   **Previewing Production Build (Frontend):** `npm run preview` or `bun run preview` (after running `build`)
