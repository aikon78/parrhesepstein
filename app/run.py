"""
Parrhesepstein — Entry point (porta 5001)
"""
import sys
import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Ensure the parent directory is in sys.path so 'app' package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

application = create_app()

if __name__ == '__main__':
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5001"))
    application.run(debug=True, host=host, port=port, threaded=True)
