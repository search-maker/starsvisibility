# Installation — libRadtran environment for the twilight-LUT experiment

Two supported paths. Path A (conda-forge binary) is what this branch actually
used and is fully reproducible; Path B (source build) is documented for
Windows/WSL2 users when libradtran.org is reachable.

## Path A — conda-forge binary (used on this branch)

The Vera C. Rubin Observatory packages libRadtran for conda-forge as
`rubin-libradtran`. It ships `uvspec` (reported version **2.0.6-MYSTIC**),
the static libraries, and the complete `share/libRadtran/data` package.
This is a real libRadtran build (GPL-2.0), not a mock.

Works on Linux and on Windows via WSL2 (Ubuntu). No compiler needed.

```bash
# 1. Get micromamba (any method; shown: direct download of the conda-forge pkg)
curl -L -o micromamba.tar.bz2 \
  https://conda.anaconda.org/conda-forge/linux-64/micromamba-2.8.1-0.tar.bz2
mkdir -p mm && tar -xjf micromamba.tar.bz2 -C mm

# 2. Create an environment with libRadtran
export MAMBA_ROOT_PREFIX=$PWD/mamba-root
mm/bin/micromamba create -y -p $PWD/lrt-env -c conda-forge rubin-libradtran

# 3. Point the pipeline at it
export LIBRADTRAN_BIN=$PWD/lrt-env/bin/uvspec
export LIBRADTRAN_DATA=$PWD/lrt-env/share/libRadtran/data

# 4. Verify
$LIBRADTRAN_BIN -v          # expect: uvspec, version 2.0.6-MYSTIC
python scripts/check_environment.py
```

If you already have conda/mamba: `conda create -n lrt -c conda-forge rubin-libradtran`.

## Path B — build from source under WSL2 (Windows)

1. Install WSL2 + Ubuntu (PowerShell, admin): `wsl --install -d Ubuntu-24.04`.
2. Inside Ubuntu:

```bash
sudo apt update
sudo apt install -y build-essential gfortran flex make \
    libgsl-dev libnetcdf-dev netcdf-bin python3 python3-pip
pip3 install numpy scipy pytest
```

3. Download libRadtran (registration page at http://www.libradtran.org/ →
   direct link `http://www.libradtran.org/download/libRadtran-2.0.6.tar.gz`,
   sha256 `999e47f4af4b5df6f85a6887fc105fc8f6e1a7cee89a3124f69ac8d8912c8e85`
   per the conda-forge recipe).

```bash
tar xzf libRadtran-2.0.6.tar.gz && cd libRadtran-2.0.6
./configure --prefix=$HOME/libradtran
make -j$(nproc)
make check          # optional, slow
make install
export LIBRADTRAN_BIN=$HOME/libradtran/bin/uvspec
export LIBRADTRAN_DATA=$HOME/libradtran/share/libRadtran/data
```

Note: on this branch's build machine, direct HTTP(S) access to libradtran.org
was blocked by the network policy (HTTP 403 at the proxy), which is why Path A
was used. The binary provenance is the conda-forge `rubin-libradtran-feedstock`,
whose recipe builds the identical upstream tarball.

## Environment variables used by every script in `scripts/`

| Variable | Meaning | Default |
|---|---|---|
| `LIBRADTRAN_BIN` | path to `uvspec` | searched on PATH |
| `LIBRADTRAN_DATA` | libRadtran `data/` directory | `<uvspec>/../share/libRadtran/data` |

## Verification

`python scripts/check_environment.py` checks Python ≥3.10, numpy/scipy/pytest,
uvspec presence + version, the data directory, a minimal DISORT run, solver
availability (disort, twostr, sdisort, mystic/montecarlo), and prints whether
the environment is REAL or MOCKED. It never fakes a pass.
