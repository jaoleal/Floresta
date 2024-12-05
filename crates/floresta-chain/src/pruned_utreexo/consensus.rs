//! A collection of functions that implement the consensus rules for the Bitcoin Network.
//! This module contains functions that are used to verify blocks and transactions, and doesn't
//! assume anything about the chainstate, so it can be used in any context.
//! We use this to avoid code reuse among the different implementations of the chainstate.
extern crate alloc;

use core::ffi::c_uint;

use bitcoin::block::Header as BlockHeader;
use bitcoin::hashes::sha256;
use bitcoin::hashes::Hash;
use bitcoin::Block;
use bitcoin::CompactTarget;
use bitcoin::ScriptBuf;
use bitcoin::Target;
use bitcoin::Transaction;
use bitcoin::TxIn;
use bitcoin::TxOut;
use bitcoin::Txid;
use floresta_common::prelude::*;
use rustreexo::accumulator::node_hash::BitcoinNodeHash;
use rustreexo::accumulator::proof::Proof;
use rustreexo::accumulator::stump::Stump;

use super::chainparams::ChainParams;
use super::error::BlockValidationErrors;
use super::error::BlockchainError;
use super::nodetime::NodeTime;
use super::nodetime::HOUR;
use super::udata;
use super::utxo_data::UtxoMap;
use crate::TransactionError;

pub const SEQUENCE_LOCKTIME_MASK: u32 = 0x0000_ffff;

/// The value of a single coin in satoshis.
pub const COIN_VALUE: u64 = 100_000_000;

/// The version tag to be prepended to the leafhash. It's just the sha512 hash of the string
/// `UtreexoV1` represented as a vector of [u8] ([85 116 114 101 101 120 111 86 49]).
/// The same tag is "5574726565786f5631" as a hex string.
pub const UTREEXO_TAG_V1: [u8; 64] = [
    0x5b, 0x83, 0x2d, 0xb8, 0xca, 0x26, 0xc2, 0x5b, 0xe1, 0xc5, 0x42, 0xd6, 0xcc, 0xed, 0xdd, 0xa8,
    0xc1, 0x45, 0x61, 0x5c, 0xff, 0x5c, 0x35, 0x72, 0x7f, 0xb3, 0x46, 0x26, 0x10, 0x80, 0x7e, 0x20,
    0xae, 0x53, 0x4d, 0xc3, 0xf6, 0x42, 0x99, 0x19, 0x99, 0x31, 0x77, 0x2e, 0x03, 0x78, 0x7d, 0x18,
    0x15, 0x6e, 0xb3, 0x15, 0x1e, 0x0e, 0xd1, 0xb3, 0x09, 0x8b, 0xdc, 0x84, 0x45, 0x86, 0x18, 0x85,
];

/// This struct contains all the information and methods needed to validate a block,
/// it is used by the [ChainState] to validate blocks and transactions.
#[derive(Debug, Clone)]
pub struct Consensus {
    /// The parameters of the chain we are validating, it is usually hardcoded
    /// constants. See [ChainParams] for more information.
    pub parameters: ChainParams,
}

impl Consensus {
    /// Returns the amount of block subsidy to be paid in a block, given it's height.
    /// Bitcoin Core source: https://github.com/bitcoin/bitcoin/blob/2b211b41e36f914b8d0487e698b619039cc3c8e2/src/validation.cpp#L1501-L1512
    pub fn get_subsidy(&self, height: u32) -> u64 {
        let halvings = height / self.parameters.subsidy_halving_interval as u32;
        // Force block reward to zero when right shift is undefined.
        if halvings >= 64 {
            return 0;
        }
        let mut subsidy = 50 * COIN_VALUE;
        // Subsidy is cut in half every 210,000 blocks which will occur approximately every 4 years.
        subsidy >>= halvings;
        subsidy
    }

    /// Verify if all transactions in a block are valid. Here we check the following:
    /// - The block must contain at least one transaction, and this transaction must be coinbase
    /// - The first transaction in the block must be coinbase
    /// - The coinbase transaction must have the correct value (subsidy + fees)
    /// - The block must not create more coins than allowed
    /// - All transactions must be valid:
    ///     - The transaction must not be coinbase (already checked)
    ///     - The transaction must not have duplicate inputs
    ///     - The transaction must not spend more coins than it claims in the inputs
    ///     - The transaction must have valid scripts
    pub fn verify_block_transactions(
        height: u32,
        block_time: u32,
        mut utxos: UtxoMap,
        transactions: &[Transaction],
        subsidy: u64,
        verify_script: bool,
        flags: c_uint,
    ) -> Result<(), BlockchainError> {
        // Blocks must contain at least one transaction (i.e. the coinbase)
        if transactions.is_empty() {
            return Err(BlockValidationErrors::EmptyBlock)?;
        }

        // Total block fees that the miner can claim in the coinbase
        let mut fee = 0;

        for (n, transaction) in transactions.iter().enumerate() {
            let txid = || transaction.compute_txid();

            if n == 0 {
                if !transaction.is_coinbase() {
                    return Err(BlockValidationErrors::FirstTxIsNotCoinbase)?;
                }
                Self::verify_coinbase(transaction)?;

                // Skip the rest of checks for the coinbase transaction
                continue;
            }

            // Sum tx output amounts, check their locking script sizes (scriptpubkey)
            let mut out_value = 0;
            for output in transaction.output.iter() {
                out_value += output.value.to_sat();

                Self::validate_script_size(&output.script_pubkey, txid)?;
            }

            // Sum tx input amounts, check their unlocking script sizes (scriptsig and TODO witness)
            let mut in_value = 0;
            for input in transaction.input.iter() {
                let txo = Self::get_utxo(input, &utxos, txid)?;

                in_value += txo.value.to_sat();

                Self::validate_script_size(&input.script_sig, txid)?;

                Self::validate_locktime(input, transaction, &utxos, height, block_time)?;

                // TODO check also witness script size
            }

            // Value in should be greater or equal to value out. Otherwise, inflation.
            if out_value > in_value {
                return Err(tx_err!(txid, NotEnoughMoney))?;
            }
            // Sanity check
            if out_value > 21_000_000 * COIN_VALUE {
                return Err(BlockValidationErrors::TooManyCoins)?;
            }

            // Fee is the difference between inputs and outputs
            fee += in_value - out_value;

            // Verify the tx script
            #[cfg(feature = "bitcoinconsensus")]
            if verify_script {
                transaction
                    .verify_with_flags(
                        |outpoint| utxos.remove(outpoint).map(|utxodata| utxodata.txout),
                        flags,
                    )
                    .map_err(|e| tx_err!(txid, ScriptValidationError, e.to_string()))?;
            };
        }

        // Checks if the miner isn't trying to create inflation
        if fee + subsidy
            < transactions[0]
                .output
                .iter()
                .fold(0, |acc, out| acc + out.value.to_sat())
        {
            return Err(BlockValidationErrors::BadCoinbaseOutValue)?;
        }

        Ok(())
    }

    /// Returns the TxOut being spent by the given input.
    ///
    /// Fails if the UTXO is not present in the given hashmap.

    fn get_utxo<'a, F: Fn() -> Txid>(
        input: &TxIn,
        utxos: &'a UtxoMap,
        txid: F,
    ) -> Result<&'a TxOut, TransactionError> {
        match utxos.get(&input.previous_output) {
            Some(txout) => Ok(&txout.txout),
            // This is the case when the spender:
            // - Spends an UTXO that doesn't exist
            // - Spends an UTXO that was already spent
            None => Err(tx_err!(txid, UtxoNotFound, input.previous_output)),
        }
    }

    /// From a block timestamp, with a given MTP and a real world time, validate if a block timestamp
    /// is correct.
    pub fn validate_block_time(
        block_timestamp: u32,
        mtp: u32,
        time: impl NodeTime,
    ) -> Result<(), BlockValidationErrors> {
        if time.get_time() == 0 {
            return Ok(());
        } // The check for skipping time validation.

        let its_too_old = mtp > block_timestamp;
        let its_too_new = block_timestamp > (time.get_time() + (2 * HOUR));
        if its_too_old {
            return Err(BlockValidationErrors::BlockTooNew);
        }
        if its_too_new {
            return Err(BlockValidationErrors::BlockTooNew);
        }
        Ok(())
    }

    /// Validate if the transaction doesnt have any timelock invalidating its inclusion inside blocks.
    fn validate_locktime(
        input: &TxIn,
        transaction: &Transaction,
        out_map: &UtxoMap,
        height: u32,
        block_time: u32,
    ) -> Result<(), BlockValidationErrors> {
        let is_relative_locked =
            input.sequence.is_relative_lock_time() && transaction.version.0 >= 2;

        if is_relative_locked {
            let prevout = match out_map.get(&input.previous_output) {
                Some(po) => po,
                None => {
                    return Err(BlockValidationErrors::UtxoNotFound(input.previous_output));
                }
            };
            // All the unwraps and casts inside this match are unreachable by logic.
            match input.sequence.to_relative_lock_time() {
                Some(lock) => {
                    match (lock.is_block_height(), lock.is_block_time()) {
                        (true, false) => {
                            // We are validating a relative block lock

                            let block_diff = bitcoin::relative::Height::from_height(
                                height.abs_diff(prevout.commited_height) as u16,
                            );

                            let satisfied = lock.is_satisfied_by_height(block_diff).unwrap();

                            if !satisfied {
                                return Err(BlockValidationErrors::BadRelativeBlockLock);
                            }
                        }
                        (false, true) => {
                            // We are validating a relative block lock

                            let time_diff = bitcoin::relative::Time::from_seconds_floor(
                                block_time.abs_diff(prevout.commited_time),
                            )
                            .unwrap();

                            let satisfied = lock.is_satisfied_by_time(time_diff).unwrap();

                            if !satisfied {
                                return Err(BlockValidationErrors::BadRelativeTimeLock);
                            }
                        }
                        // A relative locktime cannot evaluate to both.
                        _ => unreachable!(),
                    }
                }

                // This should never happen because we already check if the Sequence
                // refers to a relative locktime
                _ => unreachable!(),
            }
        }

        let is_absolute_locked = transaction.is_lock_time_enabled();

        let is_locktime_satisfied = transaction.is_absolute_timelock_satisfied(
            bitcoin::absolute::Height::from_consensus(height).unwrap(),
            bitcoin::absolute::Time::from_consensus(block_time).unwrap(),
        );

        if !is_locktime_satisfied && is_absolute_locked {
            return Err(BlockValidationErrors::BadAbsoluteLockTime);
        }
        Ok(())
    }

    /// Validates the script size and the number of sigops in a scriptpubkey or scriptsig.
    fn validate_script_size<F: Fn() -> Txid>(
        script: &ScriptBuf,
        txid: F,
    ) -> Result<(), TransactionError> {
        // The maximum script size for non-taproot spends is 10,000 bytes
        // https://github.com/bitcoin/bitcoin/blob/v28.0/src/script/script.h#L39
        if script.len() > 10_000 {
            return Err(tx_err!(txid, ScriptError));
        }
        if script.count_sigops() > 80_000 {
            return Err(tx_err!(txid, ScriptError));
        }
        Ok(())
    }

    fn verify_coinbase(tx: &Transaction) -> Result<(), TransactionError> {
        let txid = || tx.compute_txid();
        let input = &tx.input[0];

        // The prevout input of a coinbase must be all zeroes
        if input.previous_output.txid != Txid::all_zeros() {
            return Err(tx_err!(txid, InvalidCoinbase, "Invalid Coinbase PrevOut"));
        }

        let scriptsig_size = input.script_sig.len();

        // The scriptsig size must be between 2 and 100 bytes
        // https://github.com/bitcoin/bitcoin/blob/v28.0/src/consensus/tx_check.cpp#L49
        if !(2..=100).contains(&scriptsig_size) {
            return Err(tx_err!(txid, InvalidCoinbase, "Invalid ScriptSig size"));
        }
        Ok(())
    }

    /// Calculates the next target for the proof of work algorithm, given the
    /// current target and the time it took to mine the last 2016 blocks.
    pub fn calc_next_work_required(
        last_block: &BlockHeader,
        first_block: &BlockHeader,
        params: ChainParams,
    ) -> Target {
        let actual_timespan = last_block.time - first_block.time;

        CompactTarget::from_next_work_required(first_block.bits, actual_timespan as u64, params)
            .into()
    }

    /// Updates our accumulator with the new block. This is done by calculating the new
    /// root hash of the accumulator, and then verifying the proof of inclusion of the
    /// deleted nodes. If the proof is valid, we return the new accumulator. Otherwise,
    /// we return an error.
    /// This function is pure, it doesn't modify the accumulator, but returns a new one.
    pub fn update_acc(
        acc: &Stump,
        block: &Block,
        height: u32,
        proof: Proof,
        del_hashes: Vec<sha256::Hash>,
    ) -> Result<Stump, BlockchainError> {
        let block_hash = block.block_hash();
        let del_hashes = del_hashes
            .iter()
            .map(|hash| BitcoinNodeHash::from(hash.as_byte_array()))
            .collect::<Vec<_>>();

        let adds = udata::proof_util::get_block_adds(block, height, block_hash);

        // Update the accumulator
        let acc = acc.modify(&adds, &del_hashes, &proof)?.0;
        Ok(acc)
    }
}

#[cfg(test)]
mod tests {
    use bitcoin::absolute::LockTime;
    use bitcoin::hashes::sha256d::Hash;
    use bitcoin::transaction::Version;
    use bitcoin::Amount;
    use bitcoin::OutPoint;
    use bitcoin::ScriptBuf;
    use bitcoin::Sequence;
    use bitcoin::Transaction;
    use bitcoin::TxIn;
    use bitcoin::TxOut;
    use bitcoin::Txid;
    use bitcoin::Witness;

    use super::*;
    use crate::pruned_utreexo::utxo_data::UtxoData;

    fn coinbase(is_valid: bool) -> Transaction {
        // This coinbase transactions was retrieved from https://learnmeabitcoin.com/explorer/block/0000000000000a0f82f8be9ec24ebfca3d5373fde8dc4d9b9a949d538e9ff679
        // Create inputs
        let input_txid = Txid::from_raw_hash(Hash::from_str(&format!("{:0>64}", "")).unwrap());

        let input_vout = 0;
        let input_outpoint = OutPoint::new(input_txid, input_vout);
        let input_script_sig = if is_valid {
            ScriptBuf::from_hex("03f0a2a4d9f0a2").unwrap()
        } else {
            // This should invalidate the coinbase transaction since is a big, really big, script.
            ScriptBuf::from_hex(&format!("{:0>420}", "")).unwrap()
        };

        let input_sequence = Sequence::MAX;
        let input = TxIn {
            previous_output: input_outpoint,
            script_sig: input_script_sig,
            sequence: input_sequence,
            witness: Witness::new(),
        };

        // Create outputs
        let output_value = Amount::from_sat(5_000_350_000);
        let output_script_pubkey = ScriptBuf::from_hex("41047eda6bd04fb27cab6e7c28c99b94977f073e912f25d1ff7165d9c95cd9bbe6da7e7ad7f2acb09e0ced91705f7616af53bee51a238b7dc527f2be0aa60469d140ac").unwrap();
        let output = TxOut {
            value: output_value,
            script_pubkey: output_script_pubkey,
        };

        // Create transaction
        let version = Version(1);
        let lock_time = LockTime::from_height(150_007).unwrap();

        Transaction {
            version,
            lock_time,
            input: vec![input],
            output: vec![output],
        }
    }

    #[test]
    fn test_validate_script_size() {
        use bitcoin::hashes::Hash;
        let dummy_txid = || Txid::all_zeros();

        // Generate a script larger than 10,000 bytes (e.g., 10,001 bytes)
        let large_script = ScriptBuf::from_hex(&format!("{:0>20002}", "")).unwrap();
        assert_eq!(large_script.len(), 10_001);

        let small_script =
            ScriptBuf::from_hex("76a9149206a30c09cc853bb03bd917a4f9f29b089c1bc788ac").unwrap();

        assert!(Consensus::validate_script_size(&small_script, dummy_txid).is_ok());
        assert!(Consensus::validate_script_size(&large_script, dummy_txid).is_err());
    }

    #[test]
    fn test_validate_coinbase() {
        let valid_one = coinbase(true);
        let invalid_one = coinbase(false);
        // The case that should be valid
        assert!(Consensus::verify_coinbase(&valid_one).is_ok());
        // Invalid coinbase script
        assert_eq!(
            Consensus::verify_coinbase(&invalid_one)
                .unwrap_err()
                .error
                .to_string(),
            "Invalid coinbase: \"Invalid ScriptSig size\""
        );
    }

    #[test]
    #[cfg(feature = "bitcoinconsensus")]
    fn test_consume_utxos() {
        // Transaction extracted from https://learnmeabitcoin.com/explorer/tx/0094492b6f010a5e39c2aacc97396ce9b6082dc733a7b4151ccdbd580f789278
        // Mock data for testing

        let mut utxos = HashMap::new();
        let tx: Transaction = bitcoin::consensus::deserialize(
            &hex::decode("0100000001bd597773d03dcf6e22ba832f2387152c9ab69d250a8d86792bdfeb690764af5b010000006c493046022100841d4f503f44dd6cef8781270e7260db73d0e3c26c4f1eea61d008760000b01e022100bc2675b8598773984bcf0bb1a7cad054c649e8a34cb522a118b072a453de1bf6012102de023224486b81d3761edcd32cedda7cbb30a4263e666c87607883197c914022ffffffff021ee16700000000001976a9144883bb595608dcfe882aea5f7c579ef107a4fb5b88ac52a0aa00000000001976a914782231de72adb5c9df7367ab0c21c7b44bbd743188ac00000000").unwrap()
        ).unwrap();

        assert_eq!(
            tx.input.len(),
            1,
            "We only spend one utxo in this transaction"
        );
        let outpoint = tx.input[0].previous_output;

        let txout = TxOut {
            value: Amount::from_sat(18000000),
            script_pubkey: ScriptBuf::from_hex(
                "76a9149206a30c09cc853bb03bd917a4f9f29b089c1bc788ac",
            )
            .unwrap(),
        };
        utxos.insert(outpoint, txout);

        // Test consuming UTXOs
        let flags = bitcoinconsensus::VERIFY_P2SH;
        tx.verify_with_flags(|outpoint| utxos.remove(outpoint), flags)
            .unwrap();

        assert!(utxos.is_empty(), "Utxo should have been consumed");
        // Test double consuming UTXOs
        assert_eq!(
            tx.verify_with_flags(|outpoint| utxos.remove(outpoint), flags),
            Err(bitcoin::transaction::TxVerifyError::UnknownSpentOutput(
                outpoint
            )),
        );
    }
    /// Validates a relative timelock transaction and return its errors if any.
    ///
    /// utxo_lock: is the lock value which can be either a height or a timestamp. Defines the creation time/height of the UTXO.
    /// Values > 500,000,000 will be considered a unix timestamp, otherwise a height.
    ///
    /// sequence: a be u32 sequence to be put in a fake transaction that has only 1 input spending the utxo locked.
    ///
    /// actual_tip_lock: the height/time to be considered as the tip of the chain.
    /// Values > 500,000,000 will be considered a unix timestamp, otherwise a height.
    pub fn test_reltimelock(
        utxo_lock: u32,
        sequence: u32,
        actual_tip_lock: u32,
    ) -> Option<BlockValidationErrors> {
        use bitcoin::hashes::Hash;
        let base_tx = Transaction {
            version: Version(2),
            lock_time: LockTime::ZERO,
            input: vec![TxIn {
                previous_output: OutPoint {
                    txid: Hash::all_zeros(),
                    vout: 0,
                },
                sequence: Sequence::from_consensus(sequence),
                script_sig: ScriptBuf::default(),
                witness: Witness::default(),
            }],
            output: vec![TxOut {
                value: Amount::from_sat(0),
                script_pubkey: ScriptBuf::default(),
            }],
        };
        // Check if the value is set for time and resets the default value for height and vice versa.
        let mut actual_time = actual_tip_lock;
        let mut actual_height = actual_tip_lock;

        if actual_tip_lock > 500_000_000 {
            actual_height = 0;
        } else {
            actual_time = 500_000_000;
        }

        // same for utxo_lock
        let mut utxo_time = utxo_lock;
        let mut utxo_height = utxo_lock;
        if utxo_lock > 500_000_000 {
            utxo_height = 0;
        } else {
            utxo_time = 500_000_000;
        }

        let mut utxo_state: UtxoMap = HashMap::new();

        utxo_state.insert(
            OutPoint {
                txid: Hash::all_zeros(),
                vout: 0,
            },
            UtxoData {
                txout: TxOut {
                    value: Amount::from_sat(0),
                    script_pubkey: ScriptBuf::default(),
                },
                commited_time: utxo_time,
                commited_height: utxo_height,
            },
        );

        Consensus::validate_locktime(
            &base_tx.input[0],
            &base_tx,
            &utxo_state,
            actual_height,
            actual_time,
        )
        .err()
    }

    /// Validates a timelocked transaction with its timelock set as `height_tx_lock` or `seconds_tx_lock` against `lock`
    ///
    /// when testing `height_tx_lock`, `seconds_tx_lock` needs to be `0` and vice-versa.
    fn test_abstimelock(
        lock: u32,
        height_tx_lock: u32,
        seconds_tx_lock: u32,
    ) -> Option<BlockValidationErrors> {
        use bitcoin::hashes::Hash;
        let base_tx = Transaction {
            version: Version(2),
            lock_time: LockTime::from_consensus(lock),
            input: vec![TxIn {
                previous_output: OutPoint {
                    txid: Hash::all_zeros(),
                    vout: 0,
                },
                sequence: Sequence::ENABLE_LOCKTIME_NO_RBF,
                script_sig: ScriptBuf::default(),
                witness: Witness::default(),
            }],
            output: vec![TxOut {
                value: Amount::from_sat(0),
                script_pubkey: ScriptBuf::default(),
            }],
        };

        // This is necessary because of the seconds gate in timelock...
        let mut seconds_tx_lock = seconds_tx_lock;

        if seconds_tx_lock == 0 {
            seconds_tx_lock = 500000000;
        }

        Consensus::validate_locktime(
            &base_tx.input[0],
            &base_tx,
            &HashMap::new(),
            height_tx_lock,
            seconds_tx_lock,
        )
        .err()
    }
    #[test]
    fn test_timelock_validation() {
        assert!(test_abstimelock(800, 800 + 1, 0).is_none()); //height locked sucess case.
        assert_eq!(
            test_abstimelock(800, 800 - 1, 0), //height locked fail case.
            Some(BlockValidationErrors::BadAbsoluteLockTime)
        );

        assert!(test_abstimelock(1358114045, 0, 1358114045 + 1).is_none()); //time locked sucess case
        assert_eq!(
            test_abstimelock(1358114045, 0, 1358114045 - 1), //time locked fail case
            Some(BlockValidationErrors::BadAbsoluteLockTime)
        );

        // relative height locked success case
        let blocks_to_wait: u16 = 500;
        let sequence = Sequence::from_height(blocks_to_wait);
        assert!(
            test_reltimelock(800_000, sequence.0, 800_000 + (blocks_to_wait + 1) as u32).is_none()
        );

        // relative height locked fail case
        let blocks_to_wait: u16 = 500;
        let sequence = Sequence::from_height(blocks_to_wait);
        assert_eq!(
            test_reltimelock(800_000, sequence.0, 800_000 + (blocks_to_wait - 1) as u32),
            Some(BlockValidationErrors::BadRelativeBlockLock)
        );

        // relative time locked sucess case
        let intervals_to_wait: u16 = 1;
        let sequence = Sequence::from_512_second_intervals(intervals_to_wait);
        assert!(test_reltimelock(
            1358114045,
            sequence.0,
            1358114045 + ((intervals_to_wait * 512) + 1) as u32
        )
        .is_none());

        // relative time locked fail case
        let intervals_to_wait: u16 = 10;
        let sequence = Sequence::from_512_second_intervals(intervals_to_wait);
        assert_eq!(
            test_reltimelock(
                1358114045,
                sequence.0,
                1358114045 + ((intervals_to_wait * 512) - 1) as u32
            ),
            Some(BlockValidationErrors::BadRelativeTimeLock)
        );
    }
}
