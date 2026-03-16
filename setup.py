#!/usr/bin/env python
"""
Fraud Detection System — Setup & Launch Script
Run: python setup.py
"""
import subprocess
import sys
import os

os.environ["DJANGO_SETTINGS_MODULE"] = "core.settings"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))


def run(cmd, check=True):
    print(f"\n▶ {cmd}")
    return subprocess.run(cmd, shell=True, check=check)


def main():
    print("=" * 60)
    print("  🔒 Fraud Detection System — Setup")
    print("=" * 60)

    # Install deps
    run("pip install -r requirements.txt")

    # Django setup
    os.chdir("backend")
    run("python manage.py makemigrations")
    run("python manage.py migrate")
    run("python manage.py collectstatic --noinput", check=False)

    # Pre-train ML model
    print("\n▶ Pre-training fraud detection model...")
    import django
    django.setup()
    from fraud_app.ml_service import FraudDetectionService
    _ = FraudDetectionService()
    print("✅ Model ready!")

    print("\n" + "=" * 60)
    print("  🚀 Starting server (Daphne ASGI)...")
    print("  API:       http://localhost:8000/api/")
    print("  WebSocket: ws://localhost:8000/ws/fraud/<session>/")
    print("=" * 60)
    run("daphne -p 8000 core.asgi:application")


if __name__ == "__main__":
    main()
