{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
    nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixos-unstable";
    rust-overlay = {
      url = "github:oxalica/rust-overlay";
      inputs = { nixpkgs.follows = "nixpkgs"; };
    };
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, rust-overlay, flake-utils, nixpkgs-unstable, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        overlays = [ (import rust-overlay) ];

        pkgs = import nixpkgs { inherit system overlays; };
        upkgs = import nixpkgs-unstable { inherit system overlays; };

        lib = pkgs.lib;

        # libsDarwin are the necessary deps that are needed to build the floresta project for Darwin devices (?)
        # TODO: is it ?
        _libsDarwin = with pkgs.darwin.apple_sdk.frameworks;
          lib.optionals
          (system == "x86_64-darwin" || system == "aarch64-darwin")
          [ Security ];

        # This are deps needed to run and build rust projects.
        _basicDeps = [ pkgs.openssl pkgs.pkg-config ];

        # Here we set system related deps, checking if we are building for a Darwin device
        _buildInputs =
          if system == "x86_64-darwin" || system == "aarch64-darwin" then
            _basicDeps ++ _libsDarwin
          else
            _basicDeps;

        # This is the 1.74.1 rustup (and its components) toolchain from our `./rust-toolchain.toml`
        _florestaRust =
          pkgs.rust-bin.fromRustupToolchainFile ./rust-toolchain.toml;

      in with pkgs; {
        checks = {
          pythonCheck = let

            #floresta = self.packages.${system}.florestad;

            #utreexod = self.packages.${system}.utreexod;

            pythonDeps = with pkgs.python312Packages;
              [ jsonrpc-base requests black pylint ] ++ [ pkgs.python312 ];

          in pkgs.runCommand "Python Functional Tests Checks" rec {
            src = "${./.}";
            nativeBuildInputs = [ upkgs.uv ] ++ pythonDeps;

            PATH = lib.makeBinPath nativeBuildInputs;
            IS_RUNNING_BY_NIX = "true";
            FLORESTA_PROJ_DIR = "${./.}";
            UV_NO_CACHE = "true";

          } (''
            mkdir $out
            ${builtins.readFile ./tests/run.sh}
          '');
        };

        packages = let
          # Here we set system related deps. See _buildInputs above.
          buildInputs = _buildInputs;

          # This is the 1.74.1 rustup (and its components) toolchain from our `./rust-toolchain.toml`. See _florestaRust above.
          florestaRust = _florestaRust;

          utreexodGithubSrc = fetchFromGitHub {
            owner = "utreexo";
            repo = "utreexod";
            rev = "v0.4.1";
            sha256 = "sha256-oC+OqRuOp14qW2wrgmf4gss4g1DoaU4rXorlUDsAdRA=";
          };
        in rec {
          florestad = import ./build_floresta.nix {
            inherit lib rustPlatform florestaRust buildInputs;
          };

          utreexod = import ./build_utreexod.nix {
            inherit pkgs;
            src = utreexodGithubSrc;
          };
          default = florestad;
        };

        flake.overlays.default = (final: prev: {
          floresta-overlay = self.packages.${final.system}.default;
        });

        devShells = let
          # Here we set system related deps. See _buildInputs above.
          buildInputs = _buildInputs;

          # This is the dev tools used while developing in Floresta. see _florestaRust above.
          devTools = with pkgs; [ just _florestaRust ];
        in {
          default = mkShell {
            inherit buildInputs;
            nativeBuildInputs = devTools;

            shellHook = "\n";
          };
        };
      });
}
