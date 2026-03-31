FROM python:3.12-slim

# System dependencies for Playwright/Chromium + Selenium chromedriver (ARM compatible)
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      wget \
      gnupg \
      ca-certificates \
      fonts-liberation \
      libasound2 \
      libatk-bridge2.0-0 \
      libatk1.0-0 \
      libcups2 \
      libdbus-1-3 \
      libdrm2 \
      libgbm1 \
      libgtk-3-0 \
      libnspr4 \
      libnss3 \
      libxcomposite1 \
      libxdamage1 \
      libxrandr2 \
      xdg-utils \
      chromium \
      chromium-driver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
# Copy requirements first for Docker layer caching
COPY WebAxon/sidecar/requirements.txt /app/requirements.txt
ARG PACKAGES_TOKEN=""
RUN pip install --no-cache-dir \
    --extra-index-url https://${PACKAGES_TOKEN}@packages.atlassian.com/pypi/pypi/simple \
    -r requirements.txt

# Install Playwright with Chromium (don't symlink — apt's chromium/chromedriver take priority for Selenium)
RUN pip install --no-cache-dir playwright && \
    playwright install --with-deps chromium

# Copy the three local packages (src-layout, PYTHONPATH approach)
# Build context must be set to the parent CoreProjects/ directory
COPY WebAxon/src/ /app/packages/webaxon_src/
COPY RichPythonUtils/src/ /app/packages/richpythonutils_src/
COPY AgentFoundation/src/ /app/packages/agentfoundation_src/

# Copy sidecar code
COPY WebAxon/sidecar/ /app/sidecar/

# Copy prompt templates for agent workspace
COPY WebAxon/src/webaxon/devsuite/web_agent_service_nextgen/_workspace/ /root/.webaxon/workspace/

# Set PYTHONPATH so all packages are importable
ENV PYTHONPATH="/app/packages/webaxon_src:/app/packages/richpythonutils_src:/app/packages/agentfoundation_src:/app/sidecar:${PYTHONPATH}"

# Environment defaults
ENV WEBAXON_HOST=0.0.0.0
ENV WEBAXON_PORT=18800
ENV WEBAXON_HEADLESS=true
ENV WEBAXON_BACKEND=playwright
ENV WEBAXON_AGENT_TYPE=DefaultAgent
ENV WEBAXON_MAX_STEPS=50
ENV WEBAXON_AGENT_TIMEOUT=300
ENV WEBAXON_DEBUG=false

EXPOSE 18800

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:18800/health')"

CMD ["python", "-m", "sidecar"]
