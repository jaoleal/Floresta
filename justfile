default:
    @just --list

# Set the last `backend` generation to active.
set-backend:
    @just _set-sysconf
    sudo nixos-rebuild switch --flake /etc/nixos/#backend

# Set the last `userland` generation to active.
set-userland:
    @just _set-sysconf
    sudo nixos-rebuild switch --flake /etc/nixos/#userland

# Set the last home-manager generation to active.
set-hman:
    @just _set-homeconf
    home-manager switch

check:
    @just _set-sysconf
    nix flake check /etc/nixos#

# Allows /etc/nixos to jaoleal... Once in a life of a partition.
allow:
    sudo chown jaoleal /etc/nixos

gen-hardware-config:
    nixos-generate-config --dir .
    mv ./hardware-configuration.nix ./src/.
    rm -rf ./configuration.nix

_set-sysconf:
    #!/usr/bin/env bash
    cp /etc/nixos/src/hardware-configuration.nix ./src/.
    rm -rf /etc/nixos/*
    cp -r ./src /etc/nixos/
    cp -r hardware-config/ /etc/nixos/
    cp flake.nix /etc/nixos/
    cp flake.lock /etc/nixos/

_set-homeconf:
    #!/usr/bin/env bash
    rm -rf ~/.config/home-manager
    mkdir ~/.config/home-manager
    cp -r home.nix ~/.config/home-manager/
