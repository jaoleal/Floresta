{ pkgs, ... }: {
 imports =  [ ../hardware-config/backend-hardware-configuration.nix ];

  systemd.user.services = {
    florestad-master = {
      enable = true;
      after = [ "network.target" ];
      wantedBy = [ "multi-user.target" ];
      description = "Florestad service";
      serviceConfig = {
        Type = "simple";
        ExecStart = "/home/jaoleal/floresta/target/release/florestad";
      };
    };
    utreexod = {
      enable = true;
      after = [ "network.target" ];
      wantedBy = [ "multi-user.target" ];
      description = "Utreexod Service";
      serviceConfig = {
        Type = "simple";
        ExecStart =
         ''
	/home/jaoleal/utreexod/utreexod --utreexoproofindex --prune=0 --datadir="/mnt/bigd/.utreexod/data"
	'';
      };
    };
  };
  boot.kernelPackages = pkgs.linuxPackages;
  programs = {
    gamescope = {
      enable = true;
      capSysNice = true;
    };
    steam = {
      enable = true;
      remotePlay.openFirewall = true;
    };
  };
  services = {
    pipewire = {
      enable = true;
      alsa.enable = true;
      alsa.support32Bit = true;
      pulse.enable = true;
    };
    sunshine = {
      enable = true;
      autoStart = true;
      capSysAdmin = true;
      openFirewall = true;
    };
    openssh = {
      enable = true;
      startWhenNeeded = true;
      ports = [ 22 ];
      settings = {
        PasswordAuthentication = true;
        AllowUsers = [ "jaoleal" ];
        UseDns = true;
        X11Forwarding = true;
      };
    };
    xserver = {
      enable = true;
      desktopManager.gnome.enable = true;
      displayManager.gdm.enable = true;
    };
  };
  programs = {
    nix-ld.enable = true;
    ssh.forwardX11 = true;
  };
  environment.systemPackages =
    let
      #Some packages that i need locally to do remote development
      dev_deps = with pkgs; [
        rustup
        git
        just
        clang
        pkg-config
        openssl
      ];
    in
    with pkgs; [ ryujinx mangohud wget vim yubikey-manager usbutils ] ++ dev_deps;
  
hardware.graphics.enable = true;
  users.users.jaoleal = {
    isNormalUser = true;
    linger = true;
    description = "Joao Leal";
    extraGroups = [ "networkmanager" "wheel" ];
  };
  nixpkgs.config.allowUnfree = true;
  services.pcscd.enable = true;
  services.tailscale.enable = true;
  time.timeZone = "America/Sao_Paulo";
  services.xserver.xkb = {
    layout = "us";
    variant = " ";
  };

  hardware.pulseaudio.enable = false;
  security.rtkit.enable = true;
  i18n.defaultLocale = "en_US.UTF-8";
  time.hardwareClockInLocalTime = true;
  boot = {
    initrd.systemd.network.wait-online.enable = false;
    loader.systemd-boot.enable = true;
  };
  systemd = {
    sleep.extraConfig = ''
      AllowSuspend=no
      AllowHibernation=no
      AllowHybridSleep=no
      AllowSuspendThenHibernate=no
    '';
    targets.sleep.enable = false;
    targets.suspend.enable = false;
    targets.hibernate.enable = false;
    targets.hybrid-sleep.enable = false;
    network.wait-online.enable = false;
  };

  networking = { 
	hostName = "sv"; 
	networkmanager.enable = true; 
	};

  networking.firewall = {
    enable = true;
    allowedTCPPorts = [ 22 47984 3389 47989 47990 48010 ];
    allowedUDPPortRanges = [
      {
        from = 47998;
        to = 48000;
      }
      {
        from = 8000;
        to = 8010;
      }
    ];
  };

  system.stateVersion = "24.05"; # Did you read the comment?

  nix.settings.experimental-features = [ "nix-command" "flakes" ];
}
