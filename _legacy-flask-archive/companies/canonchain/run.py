"""
The on switch.

    python run.py    ->  http://127.0.0.1:5001
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host=app.config["HOST"], port=app.config["PORT"], debug=app.config["DEBUG"])
