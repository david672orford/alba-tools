#! /usr/bin/env python3
from werkzeug.serving import run_simple
from app import app
run_simple('0.0.0.0', 5000, app)
