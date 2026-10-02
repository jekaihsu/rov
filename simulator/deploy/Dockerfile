FROM python:3.11-slim
WORKDIR /app
COPY requirements-server.txt ./
RUN pip install --no-cache-dir -r requirements-server.txt
COPY qysim ./qysim
COPY viewer ./viewer
RUN useradd --create-home simulator
USER simulator
EXPOSE 8080 8765
CMD ["python", "-m", "qysim.server", "--host", "0.0.0.0"]
