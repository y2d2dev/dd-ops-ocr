"""
Gunicorn entry point for Cloud Run deployment
"""
from .main import app

if __name__ == "__main__":
    app.run()