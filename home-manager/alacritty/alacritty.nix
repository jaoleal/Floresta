{ config, lib, pkgs, ... }:

{
  programs.alacritty = {
    enable = true;
    settings = {
      # Font settings
      font.size = 10;
      font.normal.family = "Agave Nerd Font Mono";
      font.bold.family = "Agave Nerd Font Mono";
      font.italic.family = "Agave Nerd Font Mono";

      # Colors
      colors = {
        primary = {
          background = "#282828";
          foreground = "#ebdbb2";
        };

        normal = {
          black = "#282828";
          red = "#cc241d";
          green = "#98971a";
          yellow = "#d79921";
          blue = "#458588";
          magenta = "#b16286";
          cyan = "#689d6a";
          white = "#a89984";
        };

        bright = {
          black = "#928374";
          red = "#fb4934";
          green = "#b8bb26";
          yellow = "#fabd2f";
          blue = "#83a598";
          magenta = "#d3869b";
          cyan = "#8ec07c";
          white = "#ebdbb2";
        };
      };

      # Window settings
      window =
        {
          dimensions = {
            columns = 100;
            lines = 30;
          };
          dynamic_padding = true;
          decorations = "none";
          startup_mode = "Maximized";
        };

      # Other settings
      live_config_reload = true;
    };
  };
}
