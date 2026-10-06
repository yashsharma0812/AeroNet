"""Flask entry point for AeroNet."""

from flask import Flask, jsonify, render_template, request

from simulator.flights import FLIGHTS
from simulator.state import NetworkState, ValidationError

app = Flask(__name__)
state = NetworkState()

@app.get("/")
def index():
    return render_template("index.html")


@app.get("/flights")
def flights():
    return render_template("flights.html", flights=FLIGHTS)


@app.get("/api/state")
def get_state():
    return jsonify({"ok": True, "state": state.snapshot()})


@app.patch("/api/links/<link_id>")
def update_link(link_id):
    payload = request.get_json(silent=True)
    if payload is None:
        return error("Request body must be valid JSON", 400)
    try:
        return jsonify({"ok": True, "state": state.update_link(link_id, payload)})
    except ValidationError as exc:
        return error(str(exc), 400)


@app.post("/api/route")
def select_route():
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify({"ok": True, "state": state.select_source(payload.get("source_pc"))})
    except ValidationError as exc:
        return error(str(exc), 400)


@app.post("/api/request")
def simulate_request():
    payload = request.get_json(silent=True) or {}
    try:
        result = state.send_request(payload.get("source_pc"))
        return jsonify({"ok": True, "result": result, "state": state.snapshot()})
    except ValidationError as exc:
        return error(str(exc), 400)


@app.post("/api/reset")
def reset():
    return jsonify({"ok": True, "state": state.reset()})


def error(message, status):
    return jsonify({"ok": False, "error": {"message": message, "status": status}}), status


@app.errorhandler(404)
def not_found(_exc):
    if request.path.startswith("/api/"):
        return error("API endpoint not found", 404)
    return "Not found", 404


if __name__ == "__main__":
    app.run(debug=True)
