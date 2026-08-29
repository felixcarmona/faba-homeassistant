FROM python:3.12-alpine
WORKDIR /app
COPY pyproject.toml README.md ./
COPY faba_bridge ./faba_bridge
RUN pip install --no-cache-dir --root-user-action=ignore .
CMD ["faba-bridge"]
