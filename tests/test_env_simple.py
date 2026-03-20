#!/usr/bin/env python3

print("Testing Python environment...")
import sys
print(f"Python version: {sys.version}")

print("\nTesting Flask...")
try:
    import flask
    print(f"Flask version: {flask.__version__}")
    print("Flask imported successfully")
except Exception as e:
    print(f"Error importing Flask: {e}")

print("\nTesting os module...")
import os
print(f"Current directory: {os.getcwd()}")

print("\nTest completed.")

