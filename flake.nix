{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-24.11";
    vscode-server.url = "github:nix-community/nixos-vscode-server";
  };
  outputs = { self, nixpkgs, vscode-server }:
    let
      system = "x86_64-linux";
      # May god permit that i have some ARM userland but not now.
      pkgs = nixpkgs.legacyPackages.${system};

      hardware = import ./src/hardware-configuration.nix;
    in
    {
      devShells.${system} = {
        default = pkgs.mkShell {
          packages = with pkgs; [
            python312
            uv
          ];
          env =
            {
              # Prevent uv from managing Python downloads
              UV_PYTHON_DOWNLOADS = "never";
              # Force uv to use nixpkgs Python interpreter
              UV_PYTHON = pkgs.python312.interpreter;
            }
            // pkgs.lib.optionalAttrs pkgs.stdenv.isLinux {
              # Python libraries often load native shared objects using dlopen(3).
              # Setting LD_LIBRARY_PATH makes the dynamic library loader aware of libraries without using RPATH for lookup.
              LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath pkgs.pythonManylinuxPackages.manylinux1;
            };
          shellHook = ''
            unset PYTHONPATH
          '';
        };
      };
      nixosConfigurations = {
        userland = nixpkgs.lib.nixosSystem {
          modules = [
            hardware
            ./src/userland.nix
          ];
          inherit system;
        };
        backend = nixpkgs.lib.nixosSystem {
          modules = [
            ./src/backend.nix
            vscode-server.nixosModules.default
            ({ pkgs, ... }: {
              services.vscode-server.enable = true;
            })
          ];
          inherit system;
        };
      };
    };

  description = "Remember the DISSSSS ";
}
