"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/02/20 17:11
"""
import uuid


def generate_session_id():
    return str(uuid.uuid4())
