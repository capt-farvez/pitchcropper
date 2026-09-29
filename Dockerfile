# Three stages. The runtime image cannot be built unless the test stage passed,
# because it copies a marker file that only a green test run produces.

FROM python:3.12-slim AS base

# The opencv-python wheel links against these even when no window is ever opened.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1


FROM base AS test
RUN python -m pytest -q && touch /tests-passed


FROM base AS runtime
COPY --from=test /tests-passed /tests-passed
CMD ["python", "-m", "engine"]
