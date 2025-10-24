from quart import Quart, jsonify, make_response, render_template

app = application = Quart("HealthCheck", template_folder="templates", static_folder="static")
