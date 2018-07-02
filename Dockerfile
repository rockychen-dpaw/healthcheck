FROM python:3.6.6-alpine
WORKDIR /app
COPY requirements.txt status.py static /app/
RUN pip install -r /app/requirements.txt
EXPOSE 8080
CMD ["python", "status.py"]
