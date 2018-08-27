FROM python:3.6.6-alpine
MAINTAINER asi@dbca.wa.gov.au

WORKDIR /app
COPY requirements.txt status.py /app/
COPY static /app/static
RUN pip install -r /app/requirements.txt

EXPOSE 8080
CMD ["python", "status.py"]
