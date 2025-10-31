from flask import render_template


def register(bp):
    @bp.route("/settings", methods=["GET"])
    def settings_page():
        return render_template("settings.html")

    @bp.route("/settings/indicators", methods=["GET"])
    def settings_indicators_page():
        return render_template("settings_indicators.html")

    @bp.route("/news/view", methods=["GET"])
    def news_view():
        return render_template("news.html")

    @bp.route("/trades/view", methods=["GET"])
    def trades_view():
        return render_template("trades.html")