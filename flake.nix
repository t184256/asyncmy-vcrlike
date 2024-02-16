{
  description = "Something like pyvcr and python-recording, but for recording SQL queries.";

  inputs.pytest-icecream = {
    url = "github:t184256/pytest-icecream";
    inputs.nixpkgs.follows = "nixpkgs";
    inputs.flake-utils.follows = "flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils, ... }@inputs:
    let
      deps = pyPackages: with pyPackages; [
        asyncmy
        ruamel_yaml
        pytest-recording
        pytest
      ];
      tools = pkgs: pyPackages: (with pyPackages; [
        pytest pytestCheckHook pytest-asyncio
        pytest-mysql
        aiohttp
        coverage pytest-cov
        mypy pytest-mypy
      ] ++ [pkgs.mariadb pkgs.ruff]);
      devTools = pkgs: pyPackages: (with pyPackages; [
        pytest-icecream
      ]);

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
              propagatedBuildInputs = with pyPrev; [
                pytest port-for mirakuru mysqlclient
              ];
              nativeBuildInputs = with pyPrev; [ setuptools ];
            };
          })];
      };

      fresh-mypy-overlay = final: prev: {
        pythonPackagesExtensions =
          prev.pythonPackagesExtensions ++ [(pyFinal: pyPrev: {
            mypy =
              if prev.lib.versionAtLeast pyPrev.mypy.version "1.7.0"
              then pyPrev.mypy
              else pyPrev.mypy.overridePythonAttrs (_: {
                version = "1.8.0";
                patches = [];
                src = prev.fetchFromGitHub {
                  owner = "python";
                  repo = "mypy";
                  rev = "refs/tags/v1.8.0";
                  hash = "sha256-1YgAswqLadOVV5ZSi5ZXWYK3p114882IlSx0nKChGPs=";
                };
              });
          })];
      };

      asyncmy-vcrlike-package = {pkgs, python3Packages}:
        python3Packages.buildPythonPackage {
          pname = "asyncmy-vcrlike";
          version = "0.0.1";
          src = ./.;
          format = "pyproject";
          propagatedBuildInputs = deps python3Packages;
          nativeBuildInputs = [ python3Packages.setuptools ];
          nativeCheckInputs = tools pkgs python3Packages;
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
        fresh-mypy-overlay
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
            buildInputs = [(defaultPython3Packages.python.withPackages deps)];
            nativeBuildInputs = [
              (tools pkgs defaultPython3Packages)
              (devTools pkgs defaultPython3Packages)
            ];
            shellHook = ''
              export PYTHONASYNCIODEBUG=1 PYTHONWARNINGS=error
            '';
          };
          packages.asyncmy-vcrlike = asyncmy-vcrlike;
          packages.default = asyncmy-vcrlike;
        }
      ) // {
        overlays = {
          all = overlay-all;
          fresh-mypy = fresh-mypy-overlay;
          pytest-mysql = pytest-mysql-overlay;
          default = overlay;
        };
      };
}
