"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/01/23 23:38
"""
# -*- coding: utf-8 -*-
from flask import Flask
from .views import blue
from .exts import cors

def create_app():
    app = Flask(__name__)
    app.register_blueprint(blue)
    cors.init_app(app)
    return app

