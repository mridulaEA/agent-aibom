FROM python:3.12-slim AS base

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir pydantic typer rich networkx pyyaml python-frontmatter

COPY agent_aibom/ agent_aibom/

ENV PYTHONPATH=/app
ENTRYPOINT ["python", "-m", "agent_aibom.cli"]
CMD ["--help"]
