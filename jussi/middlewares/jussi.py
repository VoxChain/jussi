# -*- coding: utf-8 -*-
import logging
import random
import reprlib
import time

from ..errors import handle_middleware_exceptions
from ..request import JussiJSONRPCRequest
from ..typedefs import HTTPRequest
from ..typedefs import HTTPResponse

logger = logging.getLogger(__name__)
request_logger = logging.getLogger('jussi_request')

REQUEST_ID_TO_INT_TRANSLATE_TABLE = mt = str.maketrans('', '', '-.')


@handle_middleware_exceptions
async def add_jussi_request_id(request: HTTPRequest) -> None:
    try:
        rid = request.headers['x-jussi-request-id']
        request['request_id_int'] = int(rid.translate(mt)[:19])
    except BaseException:
        logger.debug('bad/missing x-jussi-request-id-header: %s',
                     request.headers.get('x-jussi-request-id'))
        rid = random.getrandbits(64)
        request.headers['x-jussi-request-id'] = rid
        request['request_id_int'] = int(str(rid)[:15])

    request['logger'] = request_logger
    request['timing'] = time.perf_counter()


@handle_middleware_exceptions
async def convert_to_jussi_request(request: HTTPRequest) -> None:
    # pylint: disable=no-member
    try:
        jsonrpc_request = request.json
        if isinstance(jsonrpc_request, dict):
            request.parsed_json = JussiJSONRPCRequest.from_request(jsonrpc_request)
        elif isinstance(jsonrpc_request, list):
            reqs = []
            for req in jsonrpc_request:
                reqs.append(JussiJSONRPCRequest.from_request(req))
            request.parsed_json = reqs

    except BaseException:
        logger.exception('error adding info to request', extra=dict(request=request))


@handle_middleware_exceptions
async def finalize_jussi_response(request: HTTPRequest,
                                  response: HTTPResponse) -> None:
    jussi_request_id = request.headers.get('x-jussi-request-id')
    # pylint: disable=bare-except
    if request.method == 'POST':
        try:
            response.headers['x-jussi-namespace'] = request.json.urn.namespace
            response.headers['x-jussi-api'] = request.json.urn.api
            response.headers['x-jussi-method'] = request.json.urn.method
            response.headers['x-jussi-params'] = reprlib.repr(request.json.urn.params)
        except BaseException as e:
            logger.info(e)

    request_elapsed = time.perf_counter() - request['timing']
    response.headers['x-jussi-request-id'] = jussi_request_id
    response.headers['x-jussi-response-time'] = request_elapsed
