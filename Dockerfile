# Use Python 3.11 as the base image
FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Install system dependencies including curl for uv installation
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install playwright browsers
RUN pip install playwright && playwright install chromium

# Copy application code
COPY . .

# Set environment variable for API key (should be overridden at runtime)
ENV OPERATIVE_API_KEY="your_api_key_here"

# Run the MCP server
CMD ["uv", "run", "mcp_server.py"]

