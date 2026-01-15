from flask import Flask

from webapp.logger import setup_logging
from webapp.routes import bp as routes_blueprint

logger = setup_logging()

app = Flask(__name__)
app.secret_key = "super-secret-key-change-me"

# Register blueprint
app.register_blueprint(routes_blueprint)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
