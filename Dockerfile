FROM python:3.7.2-alpine as healthcheck_base
MAINTAINER asi@dbca.wa.gov.au
WORKDIR /app
COPY requirements.txt ./
RUN pip install --upgrade pip \
  && pip install --no-cache-dir -r requirements.txt

# Install the project.
FROM healthcheck_base
COPY status.py ./
COPY static ./static
RUN pip install -r /app/requirements.txt
EXPOSE 8080
CMD ["python", "status.py"]
