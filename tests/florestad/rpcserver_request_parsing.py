# SPDX-License-Identifier: MIT OR Apache-2.0

"""
Tests for JSON-RPC request parsing in florestad, with bitcoind as a parity reference.

Every case runs against both daemons with the very same request bytes (the JSON-RPC
version is pinned, since the two clients default to different ones), so the suite
records how each one answers instead of assuming they agree.

Validates that the RPC servers correctly handle:
- Positional (array) parameters
- Named (object) parameters
- Null / omitted parameters
- Default values for optional parameters
- JSON-RPC error codes and HTTP status codes
- Methods that require no params vs methods that require params
- JSON-RPC 1.0 and 2.0 version acceptance
- Content-type handling

The two implementations agree on the happy paths and on `-32601`/`-32600`, but they
answer parameter problems with different vocabularies, which `RpcDialect` below spells
out. The three divergences we consider actual florestad gaps are the tests at the end
of the class, which take Core as the reference and are marked `xfail(strict=True)`:
they fail on florestad today and are expected to pass once the gap is closed.
"""

# pylint: disable=redefined-outer-name

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import pytest
from test_framework.constants import (
    CORE_ERRCODE_INVALID_PARAMETER,
    CORE_ERRCODE_MISC,
    CORE_ERRCODE_TYPE,
    CORE_ERRMSG_INVALID_VERSION,
    CORE_ERRMSG_MALFORMATED_PARAMS,
    CORE_METHODS_REQUIRING_PARAMS,
    CORE_NO_PARAM_METHODS,
    JSONRPC_ERRCODE_INVALID_PARAMS,
    JSONRPC_ERRCODE_INVALID_REQUEST,
    JSONRPC_ERRCODE_METHOD_NOT_FOUND,
    JSONRPC_ERRCODE_PARSE,
    JSONRPC_ERRMSG_INVALID_REQUEST,
    JSONRPC_ERRMSG_INVALID_VERSION,
    JSONRPC_ERRMSG_MALFORMATED_PARAMS,
    JSONRPC_ERRMSG_METHOD_NOT_FOUND,
    JSONRPC_ERRMSG_MISSING_PARAMS,
    JSONRPC_ERRMSG_PARSE_ERROR,
    JSONRPC_ERRMSG_WRONG_PARAM_TYPE,
    JSONRPC_VERSION_1,
    JSONRPC_VERSION_2,
    METHODS_REQUIRING_PARAMS,
    NO_PARAM_METHODS,
)
from test_framework.node import Node

FLORESTAD = "florestad"
BITCOIND = "bitcoind"


@dataclass(frozen=True)
class ExpectedError:
    """
    How one implementation reports a given failure.

    `message` is `None` when the wording is not worth pinning down, which is the case
    for every Core error that embeds the method's whole help text.
    """

    status: int
    code: int
    message: Optional[str] = None


# pylint: disable=too-many-instance-attributes
@dataclass(frozen=True)
class RpcDialect:
    """
    The implementation-specific half of a parity case.

    Requests are identical for both daemons; what changes is the set of methods each
    one implements, how it spells named parameters, and how it reports failures.
    """

    name: str

    # Methods from `NO_PARAM_METHODS` / `METHODS_REQUIRING_PARAMS` this daemon has
    no_param_methods: Tuple[str, ...]
    methods_requiring_params: Tuple[str, ...]

    # Named-parameter spelling, keyed by florestad's name for the parameter
    param_names: Dict[str, str]

    # Failure modes
    missing_param: ExpectedError
    wrong_param_type: ExpectedError
    method_not_found: ExpectedError
    malformed_params: ExpectedError
    invalid_version: ExpectedError
    unknown_named_param: ExpectedError
    non_json_body: ExpectedError

    def named(self, **params) -> Dict[str, object]:
        """Translate florestad's parameter names into this daemon's spelling."""
        return {self.param_names[name]: value for name, value in params.items()}


# florestad maps every parameter problem to the JSON-RPC spec code -32602 and answers
# with 4xx, reserving 5xx for failures that are actually the server's fault.
FLORESTAD_DIALECT = RpcDialect(
    name=FLORESTAD,
    no_param_methods=tuple(NO_PARAM_METHODS),
    methods_requiring_params=tuple(METHODS_REQUIRING_PARAMS),
    param_names={
        "block_height": "block_height",
        "block_hash": "block_hash",
        "verbosity": "verbosity",
    },
    missing_param=ExpectedError(
        400, JSONRPC_ERRCODE_INVALID_PARAMS, JSONRPC_ERRMSG_MISSING_PARAMS
    ),
    wrong_param_type=ExpectedError(
        400, JSONRPC_ERRCODE_INVALID_PARAMS, JSONRPC_ERRMSG_WRONG_PARAM_TYPE
    ),
    method_not_found=ExpectedError(
        404, JSONRPC_ERRCODE_METHOD_NOT_FOUND, JSONRPC_ERRMSG_METHOD_NOT_FOUND
    ),
    malformed_params=ExpectedError(
        400, JSONRPC_ERRCODE_INVALID_PARAMS, JSONRPC_ERRMSG_MALFORMATED_PARAMS
    ),
    invalid_version=ExpectedError(
        400, JSONRPC_ERRCODE_INVALID_REQUEST, JSONRPC_ERRMSG_INVALID_VERSION
    ),
    # florestad ignores parameter names it doesn't know, so an unknown name is
    # indistinguishable from the expected one being absent.
    unknown_named_param=ExpectedError(
        400, JSONRPC_ERRCODE_INVALID_PARAMS, JSONRPC_ERRMSG_MISSING_PARAMS
    ),
    non_json_body=ExpectedError(
        400, JSONRPC_ERRCODE_INVALID_REQUEST, JSONRPC_ERRMSG_INVALID_REQUEST
    ),
)

# Bitcoin Core v30 keeps its own error codes (`src/rpc/protocol.h`) for anything raised
# after the request is dispatched, and, for JSON-RPC 2.0 requests, answers those with
# HTTP 200 as the spec asks. Only protocol-level rejections still get a 4xx.
BITCOIND_DIALECT = RpcDialect(
    name=BITCOIND,
    no_param_methods=tuple(CORE_NO_PARAM_METHODS),
    methods_requiring_params=tuple(CORE_METHODS_REQUIRING_PARAMS),
    param_names={
        "block_height": "height",
        "block_hash": "blockhash",
        "verbosity": "verbosity",
    },
    # Core answers a missing required argument with the method's help text.
    missing_param=ExpectedError(200, CORE_ERRCODE_MISC),
    wrong_param_type=ExpectedError(200, CORE_ERRCODE_TYPE),
    method_not_found=ExpectedError(
        200, JSONRPC_ERRCODE_METHOD_NOT_FOUND, JSONRPC_ERRMSG_METHOD_NOT_FOUND
    ),
    malformed_params=ExpectedError(
        400, JSONRPC_ERRCODE_INVALID_REQUEST, CORE_ERRMSG_MALFORMATED_PARAMS
    ),
    invalid_version=ExpectedError(
        400, JSONRPC_ERRCODE_INVALID_REQUEST, CORE_ERRMSG_INVALID_VERSION
    ),
    # Core rejects names it doesn't know instead of ignoring them.
    unknown_named_param=ExpectedError(200, CORE_ERRCODE_INVALID_PARAMETER),
    non_json_body=ExpectedError(500, JSONRPC_ERRCODE_PARSE, JSONRPC_ERRMSG_PARSE_ERROR),
)

DIALECTS = {dialect.name: dialect for dialect in (FLORESTAD_DIALECT, BITCOIND_DIALECT)}

# Run the case on both daemons, each against its own recorded behavior.
BOTH_DAEMONS = pytest.mark.parametrize("daemon", [FLORESTAD, BITCOIND])


def core_is_the_reference(reason: str):
    """
    Run the case on both daemons against Core's behavior, expecting florestad to fail.

    For the handful of divergences where Core is right and florestad isn't, so that the
    gap stays visible in the report instead of being frozen into an expectation.
    """
    return pytest.mark.parametrize(
        "daemon",
        [
            BITCOIND,
            pytest.param(
                FLORESTAD, marks=pytest.mark.xfail(strict=True, reason=reason)
            ),
        ],
    )


@pytest.fixture(scope="class")
def parity_nodes(shared_florestad_node, shared_bitcoind_node) -> Dict[str, Node]:
    """The two daemons the parity cases run against, keyed by name."""
    return {FLORESTAD: shared_florestad_node, BITCOIND: shared_bitcoind_node}


# pylint: disable=too-many-public-methods
class TestRpcServerRequestParsing:
    """
    Test JSON-RPC request parsing, parameter extraction (positional and named),
    error codes, and edge cases on the florestad and bitcoind RPC servers.
    """

    @staticmethod
    def assert_error(node: Node, resp, expected: ExpectedError):
        """Assert a response carries the failure the daemon is known to report."""
        node.rpc.assert_rpc_error(
            resp,
            expected_status_code=expected.status,
            expected_rpcerror_code=expected.code,
            expected_message=expected.message,
        )

    @staticmethod
    def call(node: Node, method: str, params=None):
        """Send a JSON-RPC 2.0 call, identical for every daemon, without raising."""
        return node.rpc.noraise_request(
            method=method, params=params, jsonrpc_version=JSONRPC_VERSION_2
        )

    def call_ok(self, node: Node, method: str, params=None):
        """Send a JSON-RPC 2.0 call and assert it succeeded."""
        resp = self.call(node, method, params)
        node.rpc.assert_rpc_success(resp)
        return resp["body"]["result"]

    @BOTH_DAEMONS
    def test_noparammethods_omittedparams_succeeds(self, parity_nodes, daemon):
        """Verify all no-param methods succeed when the params field is omitted."""
        node = parity_nodes[daemon]
        for method in DIALECTS[daemon].no_param_methods:
            self.call_ok(node, method)

    @BOTH_DAEMONS
    def test_noparammethods_nullparams_succeeds(self, parity_nodes, daemon):
        """Verify all no-param methods succeed when params is explicitly null."""
        node = parity_nodes[daemon]
        for method in DIALECTS[daemon].no_param_methods:
            node.rpc.ensure_rpc_raw_request_call_success(
                {
                    "jsonrpc": JSONRPC_VERSION_2,
                    "id": "test",
                    "method": method,
                    "params": None,
                }
            )

    @BOTH_DAEMONS
    def test_noparammethods_emptyarray_succeeds(self, parity_nodes, daemon):
        """Verify all no-param methods succeed when params is an empty array."""
        node = parity_nodes[daemon]
        for method in DIALECTS[daemon].no_param_methods:
            self.call_ok(node, method, params=[])

    @BOTH_DAEMONS
    def test_positionalparams_validargs_succeeds(self, parity_nodes, daemon):
        """Verify methods accept valid positional (array) parameters."""
        node = parity_nodes[daemon]

        genesis_hash = self.call_ok(node, "getblockhash", params=[0])

        self.call_ok(node, "getblockheader", params=[genesis_hash])
        self.call_ok(node, "getblock", params=[genesis_hash, 1])

    @BOTH_DAEMONS
    def test_namedparams_validargs_succeeds(self, parity_nodes, daemon):
        """Verify methods accept valid named (object) parameters."""
        node = parity_nodes[daemon]
        dialect = DIALECTS[daemon]

        genesis_hash = self.call_ok(
            node, "getblockhash", params=dialect.named(block_height=0)
        )

        self.call_ok(
            node, "getblockheader", params=dialect.named(block_hash=genesis_hash)
        )
        self.call_ok(
            node, "getblock", params=dialect.named(block_hash=genesis_hash, verbosity=0)
        )

    @BOTH_DAEMONS
    def test_optionalparams_omitted_usesdefaults(self, parity_nodes, daemon):
        """Verify omitted optional parameters fall back to their defaults."""
        node = parity_nodes[daemon]
        dialect = DIALECTS[daemon]
        genesis_hash = self.call_ok(node, "getbestblockhash")

        result_default = self.call_ok(node, "getblock", params=[genesis_hash])
        # Check that the default verbosity was enabled.
        assert "hash" in result_default
        assert "tx" in result_default

        result_explicit = self.call_ok(node, "getblock", params=[genesis_hash, 1])
        assert result_default == result_explicit

        result_named = self.call_ok(
            node, "getblock", params=dialect.named(block_hash=genesis_hash)
        )
        assert result_default == result_named

    @BOTH_DAEMONS
    def test_unknownmethod_anyparams_returnsmethodnotfound(self, parity_nodes, daemon):
        """Verify unknown methods return METHOD_NOT_FOUND (-32601)."""
        node = parity_nodes[daemon]
        self.assert_error(
            node,
            self.call(node, "nonexistent_method", params=[]),
            DIALECTS[daemon].method_not_found,
        )

    @BOTH_DAEMONS
    def test_requiredparams_missing_returnserror(self, parity_nodes, daemon):
        """Verify missing required parameters are reported as such."""
        node = parity_nodes[daemon]
        expected = DIALECTS[daemon].missing_param

        self.assert_error(node, self.call(node, "getblockhash", params=[]), expected)

        # {} is an empty object, so it should be accepted as an object
        # but raise that is missing the fields
        self.assert_error(node, self.call(node, "getblockhash", params={}), expected)

    @BOTH_DAEMONS
    def test_paramtypes_wrongtype_returnserror(self, parity_nodes, daemon):
        """Verify wrong parameter types are reported as such."""
        node = parity_nodes[daemon]
        expected = DIALECTS[daemon].wrong_param_type

        # getblockhash expects a number, but "not_a_number" is a string
        self.assert_error(
            node, self.call(node, "getblockhash", params=["not_a_number"]), expected
        )

        # getblock hash expects a string, but 12345 is a number
        self.assert_error(node, self.call(node, "getblock", params=[12345]), expected)

        genesis_hash = self.call_ok(node, "getbestblockhash")
        self.assert_error(
            node,
            self.call(node, "getblock", params=[genesis_hash, "invalid_verbosity"]),
            expected,
        )

    @BOTH_DAEMONS
    def test_params_notarrayorobject_returnserror(self, parity_nodes, daemon):
        """Verify a params field that is neither an array nor an object is rejected."""
        node = parity_nodes[daemon]
        self.assert_error(
            node,
            self.call(node, "getblockhash", params="0"),
            DIALECTS[daemon].malformed_params,
        )

    @BOTH_DAEMONS
    def test_namedparams_unknownname_returnserror(self, parity_nodes, daemon):
        """Verify a named parameter the method doesn't take is rejected."""
        node = parity_nodes[daemon]
        self.assert_error(
            node,
            self.call(node, "getblockhash", params={"not_a_parameter": 0}),
            DIALECTS[daemon].unknown_named_param,
        )

    @BOTH_DAEMONS
    def test_jsonrpcversion_invalid_returnsrejection(self, parity_nodes, daemon):
        """Verify invalid jsonrpc versions are rejected and valid ones accepted."""
        node = parity_nodes[daemon]
        self.assert_error(
            node,
            node.rpc.noraise_raw_request(
                {
                    "jsonrpc": "3.0",
                    "id": "test",
                    "method": "getblockcount",
                    "params": [],
                }
            ),
            DIALECTS[daemon].invalid_version,
        )

        for version in [JSONRPC_VERSION_1, JSONRPC_VERSION_2]:
            node.rpc.ensure_rpc_raw_request_call_success(
                {
                    "jsonrpc": version,
                    "id": "test",
                    "method": "getblockcount",
                    "params": [],
                },
            )

        node.rpc.ensure_rpc_raw_request_call_success(
            {"id": "test", "method": "getblockcount"}
        )

    @BOTH_DAEMONS
    def test_parammethods_omittedparams_returnserror(self, parity_nodes, daemon):
        """Verify methods that require params fail when params are omitted."""
        node = parity_nodes[daemon]
        dialect = DIALECTS[daemon]

        for method in dialect.methods_requiring_params:
            self.assert_error(node, self.call(node, method), dialect.missing_param)

    @BOTH_DAEMONS
    def test_responsestructure_success_matchesjsonrpcspec(self, parity_nodes, daemon):
        """Verify successful responses match the JSON-RPC spec structure."""
        node = parity_nodes[daemon]
        resp = node.rpc.noraise_raw_request(
            {
                "jsonrpc": JSONRPC_VERSION_2,
                "id": "struct_test",
                "method": "getblockcount",
            },
        )
        body = resp["body"]
        assert "result" in body
        assert "id" in body
        assert body["id"] == "struct_test"
        assert body.get("result") is not None

    @BOTH_DAEMONS
    def test_responsestructure_error_matchesjsonrpcspec(self, parity_nodes, daemon):
        """Verify error responses match the JSON-RPC spec structure."""
        node = parity_nodes[daemon]
        resp = node.rpc.noraise_raw_request(
            {
                "jsonrpc": JSONRPC_VERSION_2,
                "id": "struct_err",
                "method": "nonexistent",
                "params": [],
            },
        )
        body = resp["body"]
        assert "error" in body
        assert "id" in body
        assert body["id"] == "struct_err"
        err = body["error"]
        assert "code" in err
        assert "message" in err
        assert isinstance(err["code"], int)

    @BOTH_DAEMONS
    def test_jsonrpc_v1_explicit_version_succeeds(self, parity_nodes, daemon):
        """Verify requests with explicit jsonrpc 1.0 version succeed."""
        parity_nodes[daemon].rpc.ensure_rpc_raw_request_call_success(
            {
                "jsonrpc": JSONRPC_VERSION_1,
                "id": "test",
                "method": "getblockcount",
                "params": [],
            },
        )

    @BOTH_DAEMONS
    def test_jsonrpc_v1_omitted_version_succeeds(self, parity_nodes, daemon):
        """Verify requests without jsonrpc field succeed (JSON-RPC 1.0 style)."""
        parity_nodes[daemon].rpc.ensure_rpc_raw_request_call_success(
            {"id": "test", "method": "getblockcount"}
        )

    @BOTH_DAEMONS
    def test_contenttype_applicationjson_succeeds(self, parity_nodes, daemon):
        """Verify requests with application/json content-type succeed."""
        parity_nodes[daemon].rpc.ensure_rpc_raw_request_call_success(
            {"jsonrpc": JSONRPC_VERSION_2, "id": "test", "method": "getblockcount"},
            content_type="application/json",
        )

    @BOTH_DAEMONS
    def test_contenttype_textplain_succeeds(self, parity_nodes, daemon):
        """Verify requests with text/plain content-type succeed."""
        parity_nodes[daemon].rpc.ensure_rpc_raw_request_call_success(
            {"jsonrpc": JSONRPC_VERSION_2, "id": "test", "method": "getblockcount"},
            content_type="text/plain",
        )

    @BOTH_DAEMONS
    def test_contenttype_nonjson_body_rejected(self, parity_nodes, daemon):
        """Verify non-JSON body is rejected regardless of content-type."""
        node = parity_nodes[daemon]
        self.assert_error(
            node,
            node.rpc.noraise_raw_request("this is not json", content_type="text/plain"),
            DIALECTS[daemon].non_json_body,
        )

    # Divergences below are florestad gaps, with Core as the reference.

    @core_is_the_reference(
        "florestad names its parameters after its internal fields (block_height, "
        "block_hash), so clients written against Core's names cannot call it"
    )
    def test_namedparams_corespelling_succeeds(self, parity_nodes, daemon):
        """Verify named parameters spelled the way Bitcoin Core spells them work."""
        node = parity_nodes[daemon]

        genesis_hash = self.call_ok(node, "getblockhash", params={"height": 0})
        self.call_ok(node, "getblockheader", params={"blockhash": genesis_hash})
        self.call_ok(
            node, "getblock", params={"blockhash": genesis_hash, "verbosity": 0}
        )

    @core_is_the_reference(
        "florestad answers a body it cannot parse with INVALID_REQUEST (-32600); the "
        "JSON-RPC spec reserves PARSE_ERROR (-32700) for it, and florestad's own "
        "JsonRpcError::Decode already maps to it"
    )
    def test_nonjson_body_returnsparseerror(self, parity_nodes, daemon):
        """Verify an unparseable body returns PARSE_ERROR (-32700)."""
        # The HTTP status is left out on purpose: florestad answers 4xx and Core 500,
        # and that difference is not what this case is about.
        parity_nodes[daemon].rpc.ensure_rpc_raw_request_call_error(
            payload="this is not json",
            expected_rpcerror_code=JSONRPC_ERRCODE_PARSE,
            expected_message=JSONRPC_ERRMSG_PARSE_ERROR,
        )

    @core_is_the_reference(
        "florestad never emits the `jsonrpc` member, which the 2.0 spec requires on "
        "every response, even though it documents answering in the 2.0 format"
    )
    def test_jsonrpc_v2_response_echoes_version(self, parity_nodes, daemon):
        """Verify responses to JSON-RPC 2.0 requests carry the `jsonrpc` member."""
        node = parity_nodes[daemon]

        success = node.rpc.noraise_raw_request(
            {"jsonrpc": JSONRPC_VERSION_2, "id": "test", "method": "getblockcount"}
        )
        assert success["body"].get("jsonrpc") == JSONRPC_VERSION_2

        failure = node.rpc.noraise_raw_request(
            {"jsonrpc": JSONRPC_VERSION_2, "id": "test", "method": "nonexistent"}
        )
        assert failure["body"].get("jsonrpc") == JSONRPC_VERSION_2


# Cases where florestad's answer is deliberately not Core's, kept as documentation
# rather than as tests:
#
# - Parameter errors: florestad uses the JSON-RPC spec code INVALID_PARAMS (-32602) with
#   a short message; Core uses RPC_MISC_ERROR (-1) plus the method's help text for a
#   missing argument and RPC_TYPE_ERROR (-3) for a wrong type.
# - HTTP status: florestad maps errors to 4xx/5xx by kind (400 for bad input, 404 for
#   unknown method); Core answers JSON-RPC 2.0 requests with 200 and carries the failure
#   in the body only, dropping to 500/404 for 1.0 requests.
# - Unknown named parameters: florestad ignores them and reports the expected parameter
#   as missing; Core rejects them with -8.
# - `getroots` and `loaddescriptor`/`listdescriptors` are florestad's own; `findtxout`
#   too. Core has no `getroots` and keeps descriptors in the wallet, not the node.
