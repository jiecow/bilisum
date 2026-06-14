#!/usr/bin/env python3
"""Run BiliSum server on http://localhost:3015"""

import sys, os

# Ensure the parent directory is in sys.path so "bilisum" package is found
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bilisum.app import app
from bilisum import config

if __name__ == "__main__":
    print(f"🚀 BiliSum starting on http://localhost:{config.PORT}")
    app.run(host=config.HOST, port=config.PORT, debug=False)
