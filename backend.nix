{ pkgs, ... }: {

  imports = [
    ./hardware-configuration.nix
  ];

  services.openssh = {
    enable = true;
    startWhenNeeded = true;
    ports = [ 22 ];
    settings = {
      PasswordAuthentication = true;
      AllowUsers = [ "jaoleal" ];
      UseDns = true;
      X11Forwarding = true;
      X11UseLocalhost = "no";
    };
  };
  fileSystems."/mnt/bigd" = {
    device = "/dev/sda";
    fsType = "ext4";
    options = [ "defaults" "noatime" ];
  };
  networking.firewall.allowedTCPPorts = [ 6010 ];

  # Fica frio ai. Deixa eu dar hot reload no meu sistema em paz.
  systemd.network.wait-online.enable = false;
  boot.initrd.systemd.network.wait-online.enable = false;

  systemd.user.services =
    {
      florestad-master = {
        enable = true;
        after = [ "network.target" ];
        wantedBy = [ "multi-user.target" ];
        description = "Florestad service";
        serviceConfig = {
          Type = "simple";
          ExecStart = ''/home/jaoleal/floresta/target/release/florestad'';
        };
      };
      utreexod = {
        enable = true;
        after = [ "network.target" ];
        wantedBy = [ "multi-user.target" ];
        description = "Florestad service";
        serviceConfig = {
          Type = "simple";
          ExecStart = ''/home/jaoleal/utreexod/utreexod --utreexoproofindex --prune=0 -b  /home/jaoleal/.utreexod/data'';
        };
      };
    };

  programs =
    {
      nix-ld.enable = true;
      ssh.forwardX11 = true;

    };
  environment.systemPackages =
    let
      #Some packages that i need locally to do remote development
      dev_deps = with pkgs;
        [
          rustup
          git
          just
          clang
          pkg-config
          openssl

        ];
    in
    with pkgs;
    [
      wget
      vim
      yubikey-manager
      usbutils
      xorg.xauth
    ] ++ dev_deps;


  users.users.jaoleal = {
    isNormalUser = true;
    linger = true;
    description = "Joao Leal";
    extraGroups = [ "networkmanager" "wheel" ];
  };

  nixpkgs.config.allowUnfree = true;
  services.pcscd.enable = true;
  services.tailscale.enable = true;
  networking.networkmanager.enable = true;
  time.timeZone = "America/Sao_Paulo";
  services.xserver.xkb = {
    layout = "us";
    variant = " ";
  };
  hardware.pulseaudio.enable = false;
  security.rtkit.enable = true;
  services.pipewire = {
    enable = true;
    alsa.enable = true;
    alsa.support32Bit = true;
    pulse.enable = true;
  };
  i18n.defaultLocale = "en_US.UTF-8";
  time.hardwareClockInLocalTime = true;
  boot.loader.systemd-boot.enable = true;
  systemd.sleep.extraConfig = ''
    AllowSuspend=no
    AllowHibernation=no
    AllowHybridSleep=no
    AllowSuspendThenHibernate=no
  '';

  system.stateVersion = " 24.05 "; # Did you read the comment?

  nix.settings.experimental-features = [
    "nix-command"
    "flakes"
  ];
}
