import logging
from argparse import ArgumentParser, Namespace
from datetime import timedelta

import waitress
from flask import Flask
from flask_jwt_extended import JWTManager
from mypass_logman import login
from mypass_logman.exceptions import MissingSessionKeyError
from mypass_logman.logman import gen_api_key
from requests.exceptions import ProxyError
from werkzeug.exceptions import UnsupportedMediaType

from mypass.api import AuthApi, CryptoApi, TeapotApi, DbApi
from mypass.exceptions import TokenExpiredException, FreshTokenRequired
from mypass.middlewares import hooks

HOST = 'localhost'
PORT = 5757
JWT_KEY = 'sourcehaven-service'
SECRET_KEY = 'sourcehaven-service'
DB_API_HOST = 'http://localhost'
DB_API_PORT = 5758


class MyPassArgs(Namespace):
    debug: bool
    host: str
    port: int
    jwt_key: str
    secret_key: str
    db_api_key: str


def run(debug=False, host=HOST, port=PORT, jwt_key=JWT_KEY, secret_key=SECRET_KEY, db_api_key=None):
    app = Flask(__name__)

    app.config['SECRET_KEY'] = secret_key
    app.config['JWT_SECRET_KEY'] = jwt_key
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=10)
    app.config['JWT_BLACKLIST_ENABLED'] = True
    app.config['JWT_BLACKLIST_TOKEN_CHECKS'] = ['access', 'refresh']
    app.config['DB_API_HOST'] = DB_API_HOST
    app.config['DB_API_PORT'] = DB_API_PORT
    app.config['DB_API_KEY'] = db_api_key
    app.config['OPTIONAL_JWT_CHECKS'] = True
    app.config.from_object(__name__)

    app.register_blueprint(AuthApi)
    app.register_blueprint(CryptoApi)
    app.register_blueprint(DbApi)
    app.register_blueprint(TeapotApi)

    app.register_error_handler(TokenExpiredException, hooks.TokenExpiredExceptionHandler(max_retries=1))
    app.register_error_handler(FreshTokenRequired, hooks.FreshTokenRequiredHandler(max_retries=1))
    app.register_error_handler(MissingSessionKeyError, hooks.MissingSessionKeysHandler())
    app.register_error_handler(UnsupportedMediaType, hooks.unsupported_media_type_handler)
    app.register_error_handler(Exception, hooks.base_error_handler)

    jwt = JWTManager(app)
    jwt.token_in_blocklist_loader(hooks.check_if_token_in_blacklist)
    try:
        login(pw=gen_api_key(64), host=app.config['DB_API_HOST'], port=app.config['DB_API_PORT'])
    except ProxyError as e:
        logging.getLogger().critical(e)
        logging.getLogger().critical(
            'DB API ERROR :: Failed signing into db api.\n'
            'This may cause unexpected behaviours, errors on db api endpoints, '
            'and failure on saving passwords. Make sure that the db service is up and running.')

    if debug:
        app.run(host=host, port=port, debug=True)
    else:
        waitress.serve(app, host=host, port=port, channel_timeout=10, threads=1)


if __name__ == '__main__':
    arg_parser = ArgumentParser('MyPass')
    arg_parser.add_argument(
        '-d', '--debug', action='store_true', default=False,
        help='flag for debugging mode')
    arg_parser.add_argument(
        '-H', '--host', type=str, default=HOST,
        help=f'specifies the host for the microservice, defaults to "{HOST}"')
    arg_parser.add_argument(
        '-p', '--port', type=int, default=PORT,
        help=f'specifies the port for the microservice, defaults to {PORT}')
    arg_parser.add_argument(
        '-k', '--jwt-key', type=str, default=JWT_KEY,
        help=f'specifies the secret jwt key for the application, defaults to "{JWT_KEY}" (should be changed)')
    arg_parser.add_argument(
        '-S', '--secret-key', type=str, default=SECRET_KEY,
        help=f'specifies the secret key for the application, defaults to "{SECRET_KEY}" (should be changed)')
    arg_parser.add_argument(
        '-P', '--db-api-key', type=str, default=None,
        help=f'specifies the secret db-api key used by the db-service, defaults to "{None}" (should be set)')

    args = arg_parser.parse_args(namespace=MyPassArgs)
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.ERROR)
    run(
        debug=args.debug, host=args.host, port=args.port, jwt_key=args.jwt_key, secret_key=args.secret_key,
        db_api_key=args.db_api_key)
