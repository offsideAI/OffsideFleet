FROM python:3.12-slim
RUN pip install --no-cache-dir "httpx2>=0.1"
WORKDIR /app
COPY egress_proxy/ /app/egress_proxy/
USER 65534:65534
ENTRYPOINT ["python", "-m", "egress_proxy.proxy"]
