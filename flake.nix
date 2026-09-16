{
  description = "Unified Technical Telemetry Gateway (UTTG)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
  };

  outputs = { self, nixpkgs }:
    let
      systems = [ "aarch64-darwin" "aarch64-linux" "x86_64-darwin" "x86_64-linux" ];
    in
    nixpkgs.lib.genAttrs systems (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            pkgs.python313
            pkgs.python313Packages.pip
            pkgs.python313Packages.virtualenv
            pkgs.just
            pkgs.k6
          ] ++ pkgs.lib.optionals pkgs.stdenv.isLinux [
            pkgs.docker
            pkgs.docker-compose
          ];
          shellHook = ''
            export VIRTUAL_ENV=$PWD/.venv
            export PATH=$VIRTUAL_ENV/bin:$PATH
            if [ ! -d $VIRTUAL_ENV ]; then
              python3.13 -m venv $VIRTUAL_ENV
              python -m pip install -e '.[dev]'
            fi
            echo "UTTG development environment loaded"
          '';
        };
      }
    );
}
