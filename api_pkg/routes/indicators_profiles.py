import json
from flask import jsonify, request, current_app, Response

from indicator_settings import default_indicator_settings, sanitize_indicator_settings, get_indicator_settings


def _sv():
    return current_app.extensions["services"]


def register(bp):
    @bp.route("/indicators", methods=["GET", "POST"])
    def api_indicators():
        sv = _sv()
        if request.method == "GET":
            data = sv.db.get_setting("indicators") or default_indicator_settings()
            return jsonify({"data": sanitize_indicator_settings(data)})
        body = request.get_json(force=True) or {}
        sv.db.set_setting("indicators", sanitize_indicator_settings(body))
        return jsonify({"ok": True, "data": sanitize_indicator_settings(sv.db.get_setting("indicators"))})

    @bp.route("/signal_params", methods=["GET", "POST"])
    def signal_params():
        sv = _sv()
        if request.method == "GET":
            return jsonify({"data": sv.db.load_signal_params()})
        body = request.get_json(force=True) or {}
        sv.db.save_signal_params(body)
        return jsonify({"ok": True, "data": sv.db.load_signal_params()})

    @bp.route("/signal_profiles", methods=["GET", "POST", "DELETE"])
    def signal_profiles():
        sv = _sv()
        if request.method == "GET":
            return jsonify({"data": sv.db.get_signal_profiles()})
        if request.method == "POST":
            body = request.get_json(force=True) or {}
            name = (body.get("name") or "").strip() or "default"
            params = body.get("params") or {}
            sv.db.save_signal_profile(name, params)
            if body.get("activate"):
                sv.db.set_active_signal_profile(name)
            return jsonify({"ok": True, "data": sv.db.get_signal_profiles()})
        name = request.args.get("name")
        if not name:
            return jsonify({"ok": False, "message": "name is required"}), 400
        sv.db.delete_signal_profile(name)
        return jsonify({"ok": True, "data": sv.db.get_signal_profiles()})

    @bp.route("/signal_profiles/activate", methods=["POST"])
    def signal_profiles_activate():
        sv = _sv()
        body = request.get_json(force=True) or {}
        name = (body.get("name") or "").strip()
        if not name:
            return jsonify({"ok": False, "message": "name is required"}), 400
        ok = sv.db.set_active_signal_profile(name)
        if not ok:
            return jsonify({"ok": False, "message": "profile not found"}), 404
        return jsonify({"ok": True, "data": sv.db.get_signal_profiles()})

    @bp.route("/signal_profiles/export", methods=["GET"])
    def signal_profiles_export():
        sv = _sv()
        data = sv.db.get_signal_profiles()
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        return Response(
            payload,
            mimetype="application/json",
            headers={"Content-Disposition": "attachment; filename=signal_profiles.json"},
        )

    @bp.route("/signal_profiles/import", methods=["POST"])
    def signal_profiles_import():
        sv = _sv()
        profiles_obj = None
        merge = True
        overwrite = True
        if request.content_type and request.content_type.startswith("multipart/form-data"):
            file = request.files.get("file")
            if not file:
                return jsonify({"ok": False, "message": "file is required"}), 400
            try:
                profiles_obj = json.loads(file.read().decode("utf-8"))
            except Exception as e:
                return jsonify({"ok": False, "message": f"invalid JSON file: {e}"}), 400
            merge = request.form.get("merge", "true").lower() != "false"
            overwrite = request.form.get("overwrite", "true").lower() != "false"
        else:
            body = request.get_json(force=True) or {}
            profiles_obj = body.get("data") or body.get("profiles") or body
            merge = bool(body.get("merge", True))
            overwrite = bool(body.get("overwrite", True))

        if not profiles_obj or not isinstance(profiles_obj, dict) or "profiles" not in profiles_obj:
            return jsonify({"ok": False, "message": "invalid format: expected {active, profiles}"}), 400

        incoming_profiles = profiles_obj.get("profiles") or {}
        incoming_active = profiles_obj.get("active") or "default"

        cur = sv.db.get_signal_profiles()
        cur_profiles = cur["profiles"]
        cur_active = cur["active"]

        if not merge:
            sv.db.set_signal_profiles(incoming_profiles, incoming_active)
        else:
            for name, params in incoming_profiles.items():
                if name in cur_profiles:
                    if overwrite:
                        cur_profiles[name] = params
                else:
                    cur_profiles[name] = params
            new_active = incoming_active if incoming_active in cur_profiles else cur_active
            sv.db.set_signal_profiles(cur_profiles, new_active)

        return jsonify({"ok": True, "data": sv.db.get_signal_profiles()})