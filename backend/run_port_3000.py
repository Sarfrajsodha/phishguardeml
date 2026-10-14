import os

import app


os.environ["FLASK_ENV"] = "production"
server = app.create_app()
server.run(host="0.0.0.0", port=3000, debug=False)
