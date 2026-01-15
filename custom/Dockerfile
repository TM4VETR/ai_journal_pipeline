FROM python:3.11-slim

WORKDIR /opt/custom

# -----------------------------------------------------------
# Install OS-level dependencies, R, and uv in one layer
# -----------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        r-base r-base-dev \
        libcurl4-openssl-dev libssl-dev libxml2-dev \
        libpcre2-dev liblzma-dev libbz2-dev libicu-dev libtirpc-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && pip install uv

# -----------------------------------------------------------
# Copy and install Python requirements (for layer caching)
# -----------------------------------------------------------
COPY requirements.txt .
COPY oc/requirements.txt oc/requirements.txt
RUN uv pip install --system -r requirements.txt
RUN uv pip install --system -r oc/requirements.txt

# -----------------------------------------------------------
# Copy custom scripts last for layer caching
# -----------------------------------------------------------
COPY . /opt/custom

CMD ["tail", "-f", "/dev/null"]
