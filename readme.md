### Floresta

Welcome to Floresta, a lightweight Bitcoin full node implementation written in Rust, powered by [Utreexo](https://eprint.iacr.org/2019/611) a novel dynamic accumulator  designed for the Bitcoin UTXO set.

This project is composed of two parts, `libfloresta` and `florestad`. `libfloresta` is
a set of reusable components that can be used to build Bitcoin applications. `florestad` is built on top of `libfloresta` to provide a full node implementation, including a watch-only wallet and an Electrum server. If you just want to run a full node, you can use `florestad` directly, either by building it from source or by downloading a pre-built binary from the [releases](https://github.com/Davidson-Souza/Floresta/releases/tag/v0.4.0).

If you want to use `libfloresta` to build your own Bitcoin application, you can find the documentation [here](https://docs.getfloresta.sh/floresta/).

### Community

If you want to discuss this project, you can join our Discord server [here](https://discord.gg/5Wj8fjjS93).

### Building

You'll need Rust and Cargo, refer to [this](https://www.rust-lang.org/) for more details. Minimum support version is rustc 1.74 and newer.

Once you have Cargo, clone the repository with:

```bash
git clone https://github.com/Davidson-Souza/Floresta.git
```

go to the Floresta directory

```bash
cd Floresta/
```

and build with cargo build

```bash
cargo build --release --bin florestad
# Optionally, you can add florestad to the path with
cargo install --path ./florestad
```

### Building with nix

If you're using Nix, you can add Florestad to your system with its overlay.

```nix
{
  #Here you declare the import for your flake
  inputs.florestad = {
    url = "github:Davidson-Souza/Floresta";
    inputs = {
      nixpkgs.follows = "nixpkgs";
      flake-parts.follows = "flake-parts";
    };
  };

  outputs = inputs @ { self, ... }:
  {
    imports = [
      {
        nixpkgs.overlays = [
          # Here you use the floresta overlay with your others
          inputs.florestad.overlays.default
        ];
      }
    ];
  };
```
then Florestad will be available just like any other package with

```nix
pkgs.florestad
```


But if you just want to test it or quickly run a instance you can do 
```bash
$ nix run github:Davidson-Souza/Floresta
```

### Running
Right now, this project is working on signet only. Mainnet support is still a todo thing. You can get some signet coins [here](https://www.signetfaucet.com/) and just play around with it.
Copy `config.toml.sample` to `config.toml`, and fill up your xpubs and addresses that you intend to track, and then run with

```bash
florestad -c config.toml --network signet run
```

or

```bash
./target/release/florestad -c config.toml --network signet run
```

or

```bash
cargo run --release -- -c config.toml --network signet run
```

### Running the tests

#### Requirements

```bash
cargo build
```

There's a set of unit tests that you can run with
```bash
cargo test
```

There's also a set of functional tests that you can run with

```bash
pip3 install -r tests/requirements.txt
python tests/run_tests.py
```

### Contributing
Contributions are welcome, feel free to open an issue or a pull request.

If you want to contribute but don't know where to start, take a look at the issues, there's a few of them marked as `good first issue`.

Here's some Guidelines:
- Has to compile.
- Has to run.
- Use [pre-commit](https://pre-commit.com/) for the language that you're using (if possible 👍).

You can accomplish that using our flake.nix for development.

### Using Nix

If you already have [Nix](https://nixos.org/) you just need to do:

```Bash
    $ nix develop
```

and use our flake for development with include

- nix(fmt) and rust(fmt) pre-commit.
- Rust Msrv(1.74.0).
- Clippy and some libs so rust can compile.
- Typos for good spelling.

If you do not have Nix
[Check their guide](https://nixos.org/download/).

### License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details

### Acknowledgments
* [Utreexo](https://eprint.iacr.org/2019/611)
* [Bitcoin Core](https://github.com/bitcoin/bitcoin)
* [Rust Bitcoin](https://github.com/rust-bitcoin/rust-bitcoin)
* [Rust Miniscript](https://github.com/rust-bitcoin/rust-miniscript)

### Consensus implementation

One of the most challenging parts of working with Bitcoin is keeping up with the consensus rules. Given it's nature as a consensus protocol, it's very important to make sure that the implementation is correct. Instead of reimplementing a Script interpreter, we use [`rust-bitcoinconsensus`](https://github.com/rust-bitcoin/rust-bitcoinconsensus/) to verify transactions. This is a bind around a shared library that is part of Bitcoin Core. This way, we can be sure that the consensus rules are the same as Bitcoin Core, at least for scripts.

Although tx validation is arguably the hardest part in this process. This integration can be further improved by using `libbitcoinkernel`, that will increase the scope of `libbitcoinconsensus` to outside scripts, but this is still a work in progress.
