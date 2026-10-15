"""
-*- coding: utf-8 -*-
@author: zhihong.du
@Time  : 2025/01/23 23:39
"""
from flask import Blueprint, render_template, request, jsonify, session
from .mdr.neo4jservice import Neo4jService
from .mdr.localization import localize_metadata_response
from .chat.utils.agent_utils import generate_session_id
from .chat.agent_scot_bridge import generate_response
from collections import defaultdict
from .graph.graphservice import GraphService
import uuid

# from threading import Lock
# session_lock = Lock()

blue = Blueprint('rice', __name__)
blue.after_request(localize_metadata_response)

neo4jservice = Neo4jService()
chat_history = defaultdict(list)
graphService = GraphService()


# user_sessions = []


@blue.route('/')
def index():
    return render_template("index.html")


@blue.route('/mdr/getObjectClassList', methods=['GET'])
def get_object_class_list():
    try:
        return jsonify(neo4jservice.get_object_class_list())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blue.route('/mdr/getObjectClassByIdentifier', methods=['GET'])
def get_object_class_by_identifier():
    identifier = request.args.get('identifier')
    if not identifier:
        return jsonify({"error": "Missing identifier parameter"}), 400
    try:
        return jsonify(neo4jservice.get_object_class_by_identifier(identifier))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blue.route('/mdr/getPropertyList', methods=['GET'])
def get_property_list():
    try:
        return jsonify(neo4jservice.get_property_list())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blue.route('/mdr/getPropertyByIdentifier', methods=['GET'])
def get_property_by_identifier():
    identifier = request.args.get('identifier')
    if not identifier:
        return jsonify({"error": "Missing identifier parameter"}), 400
    try:
        return jsonify(neo4jservice.get_property_by_identifier(identifier))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blue.route('/mdr/getConceptualDomainList', methods=['GET'])
def get_conceptual_domain_list():
    try:
        return jsonify(neo4jservice.get_conceptual_domain_list())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blue.route('/mdr/getConceptualDomainByIdentifier', methods=['GET'])
def get_conceptual_domain_by_identifier():
    identifier = request.args.get('identifier')
    if not identifier:
        return jsonify({"error": "Missing identifier parameter"}), 400
    try:
        return jsonify(neo4jservice.get_conceptual_domain_by_identifier(identifier))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blue.route('/mdr/getDataElementConceptList', methods=['GET'])
def get_data_element_concept_list():
    try:
        return jsonify(neo4jservice.get_data_element_concept_list())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blue.route('/mdr/getDataElementConceptByIdentifier', methods=['GET'])
def get_data_element_concept_by_identifier():
    identifier = request.args.get('identifier')
    if not identifier:
        return jsonify({"error": "Missing identifier parameter"}), 400
    try:
        return jsonify(neo4jservice.get_data_element_concept_by_identifier(identifier))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blue.route('/mdr/getValueDomainList', methods=['GET'])
def get_value_domain_list():
    try:
        return jsonify(neo4jservice.get_value_domain_list())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blue.route('/mdr/getValueDomainByIdentifier', methods=['GET'])
def get_value_domain_by_identifier():
    identifier = request.args.get('identifier')
    if not identifier:
        return jsonify({"error": "Missing identifier parameter"}), 400
    try:
        return jsonify(neo4jservice.get_value_domain_by_identifier(identifier))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blue.route('/mdr/getDataElementList', methods=['GET'])
def get_data_element_list():
    try:
        return jsonify(neo4jservice.get_data_element_list())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blue.route('/mdr/getDataElementByIdentifier', methods=['GET'])
def get_data_element_by_identifier():
    identifier = request.args.get('identifier')
    if not identifier:
        return jsonify({"error": "Missing identifier parameter"}), 400
    try:
        return jsonify(neo4jservice.get_data_element_by_identifier(identifier))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blue.route('/mfi/getSubdomainList', methods=['GET'])
def get_subdomain_list():
    try:
        return jsonify(neo4jservice.get_subdomain_list())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blue.route('/mdr/getSubdomainByIdentifier', methods=['GET'])
def get_subdomain_by_identifier():
    identifier = request.args.get('identifier')
    if not identifier:
        return jsonify({"error": "Missing identifier parameter"}), 400
    try:
        return jsonify(neo4jservice.get_subdomain_by_identifier(identifier))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blue.route('/mfi/geTablesBySubdomainIdentifierAndDatasetIdentifier', methods=['GET'])
def get_tables_by_subdomain_identifier_and_dataset_identifier():
    subdomain_identifier = request.args.get('subdomain_identifier')
    dataset_identifier = request.args.get('dataset_identifier')
    page = int(request.args.get('page', 1))
    try:
        return jsonify(neo4jservice.get_tables_by_subdomain_identifier_and_dataset_identifier(subdomain_identifier,
                                                                                              dataset_identifier, page))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# @blue.route('/qa/initChat', methods=['GET'])
# def init_chat():
#     if 'session_id' not in session:
#         session.permanent = True
#         session['session_id'] = uuid.uuid4().hex
#     message = {"role": "assistant", "content": "你好，请问有什么水稻基因组学相关问题可以帮助你？"}
#     return jsonify({'message': message})

@blue.route('/qa/initChat', methods=['GET'])
def init_chat():
    session_id = generate_session_id()
    language = _normalize_language(request.args.get('language'))
    # user_sessions.append(session_id)
    print("session_id_init:", session_id)
    greeting = (
        "Hello, I am the Rice MDR assistant. What rice genomics question can I help with?"
        if language == "en"
        else "你好，请问有什么水稻基因组学相关问题可以帮助你？"
    )
    message = {"role": "assistant", "content": greeting}
    return jsonify({'session_id': session_id, 'message': message, 'language': language})


@blue.route('/qa/chat', methods=['GET'])
def get_chat():
    content = (request.args.get('content') or '').strip()
    session_id = request.args.get('session_id') or generate_session_id()
    method = request.args.get('method', 's_cot_raps')
    language = _normalize_language(request.args.get('language'))
    answer = generate_response(content, session_id, method=method, language=language)
    message = {"role": "assistant", "content": answer}
    return jsonify({'message': message, 'answer': answer, 'session_id': session_id, 'method': method, 'language': language})


def _normalize_language(language):
    value = (language or "en").strip().lower()
    if value in {"zh", "cn", "chinese", "zh-cn"}:
        return "zh"
    return "en"

@blue.route('/graph/getGeneBasicInfo', methods=['GET'])
def get_gene_basic_info():
    gene_id = request.args.get('gene_id')
    if not gene_id:
        return jsonify({"error": "Missing gene_id parameter"}), 400
    try:
        data = graphService.get_gene_info(gene_id)
        result = {"graph": data.to_graph_data(), "table": data.to_table_data()}
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blue.route('/graph/getExpressionInfo', methods=['GET'])
def get_expression_info():
    gene_id = request.args.get('gene_id')
    if not gene_id:
        return jsonify({"error": "Missing gene_id parameter"}), 400
    try:
        data = graphService.get_expression_info(gene_id)
        result = {"graph": data.to_graph_data(), "table": data.to_table_data()}
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blue.route('/graph/getHomologuesInfo')
def get_homologues_info():
    gene_id = request.args.get('gene_id')
    if not gene_id:
        return jsonify({"error": "Missing gene_id parameter"}), 400
    try:
        data = graphService.get_homologous_info(gene_id)
        result = {"graph": data.to_graph_data(), "table": data.to_table_data()}
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blue.route('/graph/getSVInfo')
def get_sv_info():
    sv_id = request.args.get('sv_id')
    if not sv_id:
        return jsonify({"error": "Missing sv_id parameter"}), 400
    try:
        data = graphService.get_sv_info(sv_id)
        result = {"graph": data.to_graph_data(), "table": data.to_table_data()}
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# @blue.route('/qa/chat', methods=['GET'])
# def get_chat():
#     content = request.args.get('content')
#     if 'session_id' not in session:
#         return jsonify({'error': 'Session not initialized'}), 400
#     session_id = session['session_id']
#     answer = generate_response(content, session_id)
#
#     # 保存对话记录到全局存储
#     chat_history[session_id].append({
#         "user": content,
#         "assistant": answer
#     })
#     print(chat_history)
#
#     # 构造响应
#     message = {"role": "assistant", "content": answer}
#     return jsonify({
#         'message': message,
#         'history': chat_history[session_id]
#     })


# @blue.route('/qa/closeChat', methods=['GET'])
# def close_chat():
#     if 'session_id' in session:
#         session_id = session['session_id']
#
#         if session_id in chat_history:
#             del chat_history[session_id]
#
#         session.clear()
#
#     return jsonify({'status': 'success', 'message': '对话已关闭'})
