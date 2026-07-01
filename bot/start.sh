#!/bin/bash

alembic upgrade head && python -u ./app.py