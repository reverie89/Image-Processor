#!/bin/sh
gunicorn -b ${GUNICORN_HOST}:${GUNICORN_PORT} -w ${GUNICORN_WORKERS} app.run:app
