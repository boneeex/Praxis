#!/bin/sh
set -e
mkdir -p /app/pems
if [ ! -f /app/pems/private.pem ]; then
  openssl genrsa -out /app/pems/private.pem 2048
  openssl rsa -in /app/pems/private.pem -pubout -out /app/pems/public.pem
fi
exec "$@"
