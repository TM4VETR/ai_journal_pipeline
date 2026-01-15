FROM python:3.11-slim

WORKDIR /opt/webapp

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy app code
COPY . /opt/webapp

EXPOSE 5000

CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
