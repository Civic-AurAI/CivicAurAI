# Stage 1: Build the React frontend
FROM node:22-alpine as frontend-builder
WORKDIR /app/frontend
# Copy dependency maps and source code
COPY frontend/package.json frontend/yarn.lock ./
# Install dependencies
RUN yarn install --frozen-lockfile || yarn install
# Copy the rest of the frontend source
COPY frontend/ ./
# Build the static files
RUN npm run build

# Stage 2: Build the Python backend and final image
FROM python:3.10-slim
WORKDIR /app

# Install uv for fast python package management
RUN pip install uv

# Copy the python lockfiles and pyproject.toml
COPY pyproject.toml uv.lock ./

# Install python dependencies system-wide (no venv needed in docker)
RUN uv pip install --system fastapi uvicorn httpx pydantic google-cloud-spanner

# Copy the rest of the backend files
COPY *.py ./

# Copy the built React app from Stage 1 into the designated dist folder
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Expose the port Cloud Run uses
EXPOSE 8080

# Run the FastAPI application using uvicorn
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080"]
