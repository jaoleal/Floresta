//! The pruned utreexo module handles the full blockchain logic: validation, state tracking and
//! interfacing. This blockchain backend does not store the historical blocks, it's pruned.
//!
//! This module file exports the main traits to interact with blockchain backends and databases.

extern crate alloc;

pub mod chain_state;
pub mod chain_interfaces;
pub mod chain_state_builder;
pub mod chainparams;
pub mod chainstore;
#[cfg(feature = "kv-chainstore")]
pub mod kv_chainstore;
#[macro_use]
pub mod error;
pub mod consensus;
#[cfg(feature = "flat-chainstore")]
pub mod flat_chain_store;
pub mod partial_chain;
pub mod udata;

use crate::prelude::*;

/// This module defines an [UtxoData] struct, helpful for transaction validation
pub mod utxo_data {
    use bitcoin::TxOut;

    #[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
    #[cfg_attr(
        any(test, feature = "test-utils"),
        derive(serde::Serialize, serde::Deserialize)
    )]
    /// Represents an unspent transaction output (UTXO) with additional metadata for validation.
    pub struct UtxoData {
        /// The unspent transaction output.
        pub txout: TxOut,
        /// Whether this output was created by a coinbase transaction.
        pub is_coinbase: bool,
        /// The block height at which the UTXO was confirmed.
        pub creation_height: u32,
        /// The creation time of the UTXO, defined by BIP 68 as the median time past (MTP) of the
        /// block preceding the confirming block.
        pub creation_time: u32,
    }
}

