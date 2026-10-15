"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/01/23 23:36
"""
from .App import create_app
import os

app = create_app()
# app.secret_key = os.getenv("FLASK_SECRET_KEY")
# app.config['PERMANENT_SESSION_LIFETIME'] = 3600

if __name__ == '__main__':
    app.run(debug=True)
