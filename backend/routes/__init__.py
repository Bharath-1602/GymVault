"""
GymVault - Routes Package
Registers all API route blueprints.
"""

from flask import Flask


def register_routes(app: Flask):
    """Register all route blueprints with the Flask app."""
    from routes.members import members_bp
    from routes.plans import plans_bp
    from routes.payments import payments_bp
    from routes.checkins import checkins_bp

    app.register_blueprint(members_bp)
    app.register_blueprint(plans_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(checkins_bp)
