{
  description = "Something like pyvcr and python-recording, but for recording SQL queries.";

  inputs.pytest-icecream = {
    url = "github:t184256/pytest-icecream";
    inputs.nixpkgs.follows = "nixpkgs";
    inputs.flake-utils.follows = "flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils, ... }@inputs:
    let
      pyDeps = pyPackages: with pyPackages; [
        asyncmy
        ruamel_yaml
        pytest-recording
        pytest
      ];
      pyTestDeps = pyPackages: with pyPackages; [
        pytestCheckHook pytest-asyncio
        coverage pytest-cov
        pytest-mysql
        aiohttp
      ];
      pyTools = pyPackages: with pyPackages; [ mypy pytest-icecream ];

      testDeps = pkgs: with pkgs; [ mariadb ];
      tools = pkgs: with pkgs; [
        pre-commit
        ruff
        codespell
        actionlint
        python3Packages.pre-commit-hooks
      ];

      pytest-mysql-overlay = final: prev: {
        pythonPackagesExtensions =
          prev.pythonPackagesExtensions ++ [(pyFinal: pyPrev: {
            pytest-mysql = pyPrev.buildPythonPackage rec {
              pname = "pytest-mysql";
              version = "2.5.0";
              src = pyPrev.fetchPypi {
                inherit pname version;
                sha256 = "sha256-IhP9edq1I+msqMnQqurWv6oiZrLDfDJw33VWwWezi8M=";
              };
              format = "pyproject";
              build-system = [ pyPrev.setuptools ];
              propagatedBuildInputs = with pyPrev; [
                pytest port-for mirakuru mysqlclient
              ];
            };
          })];
      };

      asyncmy-vcrlike-package = {pkgs, python3Packages}:
        python3Packages.buildPythonPackage {
          pname = "asyncmy-vcrlike";
          version = "0.0.1";
          src = ./.;
          format = "pyproject";
          build-system = [ python3Packages.setuptools ];
          propagatedBuildInputs = pyDeps python3Packages;
          checkInputs = pyTestDeps python3Packages;
          nativeCheckInputs = testDeps pkgs;
        };

      overlay = final: prev: {
        pythonPackagesExtensions =
          prev.pythonPackagesExtensions ++ [(pyFinal: pyPrev: {
            asyncmy-vcrlike = final.callPackage asyncmy-vcrlike-package {
              python3Packages = pyFinal;
            };
          })];
      };

      overlay-all = nixpkgs.lib.composeManyExtensions [
        inputs.pytest-icecream.overlays.default
        pytest-mysql-overlay
        overlay
      ];
    in
      flake-utils.lib.eachDefaultSystem (system:
        let
          pkgs = import nixpkgs { inherit system; overlays = [ overlay-all ]; };
          defaultPython3Packages = pkgs.python311Packages;  # force 3.11

          asyncmy-vcrlike = defaultPython3Packages.asyncmy-vcrlike;
        in
        {
          devShells.default = pkgs.mkShell {
            buildInputs = [(defaultPython3Packages.python.withPackages (
              pyPkgs: pyDeps pyPkgs ++ pyTestDeps pyPkgs ++ pyTools pyPkgs
            ))];
            nativeBuildInputs = [(pkgs.buildEnv {
              name = "asyncmy-vcrlike-tools-env";
              pathsToLink = [ "/bin" "/share" ];
              paths = testDeps pkgs ++ tools pkgs;
            })];
            shellHook = ''
              [ -e .git/hooks/pre-commit ] || \
                echo "suggestion: pre-commit install --install-hooks" >&2
              export PYTHONASYNCIODEBUG=1 PYTHONWARNINGS=error
            '';
          };
          packages.asyncmy-vcrlike = asyncmy-vcrlike;
          packages.default = asyncmy-vcrlike;
        }
      ) // {
        overlays = {
          all = overlay-all;
          pytest-mysql = pytest-mysql-overlay;
          default = overlay;
        };
      };
}
