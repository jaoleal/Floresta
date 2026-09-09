# SPDX-License-Identifier: MIT OR Apache-2.0

"""
This module contains constants used throughout the Floresta tests.
"""

import os

# defaults to import...
GENESIS_BLOCK_HEIGHT = 0
GENESIS_BLOCK_HASH = "0f9188f13cb7b2c71f2a335e3a4fc328bf5beb436012afca590b1a11466e2206"
GENESIS_BLOCK_DIFFICULTY_INT = 1
GENESIS_BLOCK_DIFFICULTY_FLOAT = 4.656542373906925e-10
GENESIS_BLOCK_LEAF_COUNT = 0
CHAIN_NAME = "regtest"
FLORESTA_TEMP_DIR = os.getenv("FLORESTA_TEMP_DIR")

# Wallets information,
# Mnemonics = useless ritual arm slow mention dog force almost sudden pulp rude eager
# pylint: disable = line-too-long
WALLET_XPRIV = "tprv8hCwaWbnCTeqSXMmEgtYqC3tjCHQTKphfXBG5MfWgcA6pif3fAUqCuqwphSyXmVFhd8b5ep5krkRxF6YkuQfxSAhHMTGeRA8rKPzQd9BMre"
WALLET_DESCRIPTOR_PRIV_INTERNAL = f"wpkh({WALLET_XPRIV}/1/*)#v08p3aj4"
WALLET_DESCRIPTOR_PRIV_EXTERNAL = f"wpkh({WALLET_XPRIV}/0/*)#amzqvgzd"
# pylint: disable = line-too-long
WALLET_XPUB = "tpubDDtyive2LqLWKzPZ8LZ9Ebi1JDoLcf1cEpn3Mshp6sxVfCupHZJRPQTozp2EpTF76vJcyQBN7VP7CjUntEJxeADnuTMNTYKoSWNae8soVyv"
WALLET_DESCRIPTOR_INTERNAL = f"wpkh({WALLET_XPUB}/1/*)#0rlhs7rw"
WALLET_DESCRIPTOR_EXTERNAL = f"wpkh({WALLET_XPUB}/0/*)#7h6kdtnk"
# pylint: disable = line-too-long
WALLET_XPUB_BIP_84 = "vpub5ZrpbMUWLCJ6MbpU1RzocWBddAQnk2XYry9JSXrtzxSqoicei28CzqUhiN2HJ8z2VjY6rsUNf4qxjym43ydhAFQJ7BDDcC2bK6et6x9hc4D"
WALLET_ADDRESS = "bcrt1q427ze5mrzqupzyfmqsx9gxh7xav538yk2j4cft"

# JSON-RPC protocol versions accepted by both florestad and bitcoind
JSONRPC_VERSION_1 = "1.0"
JSONRPC_VERSION_2 = "2.0"

# JSON-RPC spec error code constants
JSONRPC_ERRCODE_PARSE = -32700
JSONRPC_ERRCODE_INVALID_REQUEST = -32600
JSONRPC_ERRCODE_METHOD_NOT_FOUND = -32601
JSONRPC_ERRCODE_INVALID_PARAMS = -32602
JSONRPC_ERRCODE_INTERNAL = -32603

# JSON-RPC error message constants
JSONRPC_ERRMSG_MISSING_PARAMS = "Missing parameter"
JSONRPC_ERRMSG_WRONG_PARAM_TYPE = "Invalid parameter type"
JSONRPC_ERRMSG_METHOD_NOT_FOUND = "Method not found"
JSONRPC_ERRMSG_INVALID_VERSION = "The request contains a invalid jsonrpc version"
JSONRPC_ERRMSG_MALFORMATED_PARAMS = (
    "A parameter is malformated, the parameter MUST be an array or an object"
)
JSONRPC_ERRMSG_INVALID_REQUEST = "Invalid request"
JSONRPC_ERRMSG_PARSE_ERROR = "Parse error"

# Bitcoin Core error codes, from `src/rpc/protocol.h`. Core answers most parameter
# problems with these instead of the JSON-RPC spec codes florestad uses, so the parity
# tests need both vocabularies.
CORE_ERRCODE_MISC = -1
CORE_ERRCODE_TYPE = -3
CORE_ERRCODE_INVALID_PARAMETER = -8

# Bitcoin Core error messages, for the cases where its wording differs from florestad's
CORE_ERRMSG_MALFORMATED_PARAMS = "Params must be an array or object"
CORE_ERRMSG_INVALID_VERSION = "JSON-RPC version not supported"
CORE_ERRMSG_UNKNOWN_NAMED_PARAM = "Unknown named parameter"

# RPC method lists for testing
NO_PARAM_METHODS = [
    "getbestblockhash",
    "getblockchaininfo",
    "getblockcount",
    "getroots",
    "getrpcinfo",
    "uptime",
    "getpeerinfo",
    "listdescriptors",
]

# `NO_PARAM_METHODS` minus the methods Bitcoin Core does not expose as node RPCs:
# `getroots` is utreexo-only, and `listdescriptors` is a wallet RPC in Core, which
# answers it with -18 (no wallet loaded) while florestad answers it from the node.
CORE_NO_PARAM_METHODS = [
    "getbestblockhash",
    "getblockchaininfo",
    "getblockcount",
    "getrpcinfo",
    "uptime",
    "getpeerinfo",
]

METHODS_REQUIRING_PARAMS = [
    "getblock",
    "getblockhash",
    "getblockheader",
    "getblockfrompeer",
    "getrawtransaction",
    "gettxout",
    "gettxoutproof",
    "findtxout",
    "addnode",
    "disconnectnode",
    "loaddescriptor",
    "sendrawtransaction",
]

# `METHODS_REQUIRING_PARAMS` minus the methods that don't fit Core's uniform
# "required argument is missing" answer:
# - `findtxout` and `loaddescriptor` are floresta-only, so Core replies -32601;
# - `disconnectnode` takes only optional arguments in Core, which accepts the empty
#   call and then rejects it at dispatch time with -32602 instead.
CORE_METHODS_REQUIRING_PARAMS = [
    "getblock",
    "getblockhash",
    "getblockheader",
    "getblockfrompeer",
    "getrawtransaction",
    "gettxout",
    "gettxoutproof",
    "addnode",
    "sendrawtransaction",
]
