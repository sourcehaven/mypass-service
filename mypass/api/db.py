import logging
import os

import flask
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from werkzeug.exceptions import UnsupportedMediaType

from mypass import crypto
from mypass.middlewares import RaiseErr
from mypass.persistence.blacklist.memory import blacklist
from . import _utils as utils

DbApi = Blueprint('db', __name__)


@DbApi.route('/api/db/master/read', methods=['POST'])
@RaiseErr.raise_if_unauthorized
@jwt_required(fresh=True, optional=bool(int(os.environ.get('MYPASS_OPTIONAL_JWT_CHECKS', 0))))
def query_master_pw():
    # TODO: return identity?
    return {
        'msg': 'NOT IMPLEMENTED :: Your master password is stored in a hashed format, it cannot be recovered. Ever.'
    }, 501


@DbApi.route('/api/db/master/update', methods=['POST'])
@RaiseErr.raise_if_unauthorized
@jwt_required(fresh=True, optional=bool(int(os.environ.get('MYPASS_OPTIONAL_JWT_CHECKS', 0))))
def update_master_pw():
    """
    Returns:
        201 status code on success
    """

    request_obj = request.json
    identity = get_jwt_identity()
    uid = identity['uid']
    user = identity['user']
    pw = identity['pw']
    new_pw = request_obj['pw']
    assert uid is not None and user is not None and pw is not None, 'None user identity should not happen.'

    res = utils.get_master_info(uid)
    if res is not None:
        secret_token, secret_pw, salt = res
        token, salt = utils.refresh_master_token(secret_token, pw, salt, new_pw)
        hashed_pw = crypto.hash_pw(new_pw, salt)
        result_json, status_code = utils.update_user(uid, token=token, pw=hashed_pw, salt=salt)

        if status_code == 200:
            # blacklist old token
            jti = get_jwt()['jti']
            logging.getLogger().debug(f'Blacklisting token: {jti}.')
            blacklist.add(jti)
            return flask.redirect(flask.url_for('auth.login', _method='POST', uid=result_json['id']), 307)
        return result_json, status_code
    return {'msg': f'AUTHORIZATION FAILURE :: Could not update master password for user {user}.'}, 401


@DbApi.route('/api/db/vault/create', methods=['POST'])
@RaiseErr.raise_if_unauthorized
@jwt_required(optional=bool(int(os.environ.get('MYPASS_OPTIONAL_JWT_CHECKS', 0))))
def create_vault_entry():
    """
    Returns:
        201 status code on success
    """

    request_obj = dict(request.json)
    identity = get_jwt_identity()
    uid = identity['uid']
    user = identity['user']
    pw = identity['pw']
    assert uid is not None and user is not None and pw is not None, 'None user identity should not happen.'

    protected_fields = request_obj.pop('protected_fields', None)
    fields = request_obj.pop('fields', None)
    if fields is None:
        return {'msg': 'BAD REQUEST :: Empty request will not be handled.'}, 400

    result_json, status_code = utils.create_vault_entry(
        uid, pw, fields=fields, protected_fields=protected_fields)
    return result_json, status_code


@DbApi.route('/api/db/vault/read', methods=['POST'])
@RaiseErr.raise_if_unauthorized
@jwt_required(optional=bool(int(os.environ.get('MYPASS_OPTIONAL_JWT_CHECKS', 0))))
def query_vault_entry():
    """
    Returns:
        200 status code on success
    """

    try:
        request_obj = request.json
    except UnsupportedMediaType:
        request_obj = {}
    identity = get_jwt_identity()
    uid = identity['uid']
    user = identity['user']
    pw = identity['pw']
    assert uid is not None and user is not None and pw is not None, 'None user identity should not happen.'

    pk = request_obj.get('id', None)
    pks = request_obj.get('ids', None)
    crit = request_obj.get('crit', None)

    assert pk is None or pks is None, 'Making a request with both id and ids at the same time is invalid.'
    result_json, status_code = utils.query_vault_entry(uid, pw, pk=pk, crit=crit, pks=pks)
    if status_code == 200:
        result_json = utils.clear_hidden(result_json)
        if isinstance(result_json, list):
            return [{'entity': e} for e in result_json], status_code
        return {'entity': result_json}, status_code
    return result_json, status_code


@DbApi.route('/api/db/vault/raw_read', methods=['POST'])
@RaiseErr.raise_if_unauthorized
@jwt_required(optional=bool(int(os.environ.get('MYPASS_OPTIONAL_JWT_CHECKS', 0))))
def query_raw_vault_entry():
    """
    Returns:
        200 status code on success
    """

    try:
        request_obj = request.json
    except UnsupportedMediaType:
        request_obj = {}
    identity = get_jwt_identity()
    uid = identity['uid']
    user = identity['user']
    pw = identity['pw']
    assert uid is not None and user is not None and pw is not None, 'None user identity should not happen.'

    pk = request_obj.get('id', None)
    pks = request_obj.get('ids', None)
    crit = request_obj.get('crit', None)

    assert pk is None or pks is None, 'Making a request with both id and ids at the same time is invalid.'
    result_json, status_code = utils.query_raw_vault_entry(uid, pk=pk, crit=crit, pks=pks)
    if status_code == 200:
        protected_fields = utils.get_protected_fields(result_json)
        result_json = utils.clear_hidden(result_json)
        if isinstance(result_json, list):
            return [{'entity': e, 'protected_fields': p} for e, p in zip(result_json, protected_fields)], status_code
        return {'entity': result_json, 'protected_fields': protected_fields}, status_code
    return result_json, status_code


@DbApi.route('/api/db/vault/update', methods=['POST'])
@RaiseErr.raise_if_unauthorized
@jwt_required(optional=bool(int(os.environ.get('MYPASS_OPTIONAL_JWT_CHECKS', 0))))
def update_vault_entry():
    """
    Returns:
        200 status code on success
    """

    request_obj = request.json
    identity = get_jwt_identity()
    uid = identity['uid']
    user = identity['user']
    pw = identity['pw']
    assert uid is not None and user is not None and pw is not None, 'None user identity should not happen.'

    pk = request_obj.get('id', None)
    pks = request_obj.get('ids', None)
    fields = request_obj.get('fields', None)
    protected_fields = request_obj.get('protected_fields', None)
    crit = request_obj.get('crit', None)

    result_json, status_code = utils.update_vault_entry(
        uid, pw, fields=fields, protected_fields=protected_fields, crit=crit, pk=pk, pks=pks)
    return result_json, status_code


@DbApi.route('/api/db/vault/delete', methods=['POST'])
@RaiseErr.raise_if_unauthorized
@jwt_required(optional=bool(int(os.environ.get('MYPASS_OPTIONAL_JWT_CHECKS', 0))))
def delete_vault_entry():
    """
    Returns:
        200 status code on success
    """

    request_obj = request.json
    identity = get_jwt_identity()
    uid = identity['uid']
    user = identity['user']
    pw = identity['pw']
    assert uid is not None and user is not None and pw is not None, 'None user identity should not happen.'

    pk = request_obj.get('id', None)
    pks = request_obj.get('ids', None)
    crit = request_obj.get('crit', None)

    result_json, status_code = utils.delete_vault_entry(
        uid, pw, crit=crit, pk=pk, pks=pks)
    return result_json, status_code
