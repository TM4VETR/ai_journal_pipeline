#!/bin/bash

# Script to run docker compose with docker-compose.yml
# Sequentially executes: down -> build -> up

set -e  # Exit on error

echo "Running docker compose down..."
docker compose -f docker-compose.yml down

echo "Running docker compose build..."
docker compose -f docker-compose.yml build

echo "Running docker compose up..."
docker compose -f docker-compose.yml up
