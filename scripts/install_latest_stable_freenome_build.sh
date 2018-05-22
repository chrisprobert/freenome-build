#!/usr/bin/env bash

ANACONDA_TOKEN=$1
MINICONDA_URL=https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
MINICONDA_INSTALL_PATH=$HOME/miniconda

# check for conda install, and install if neessary
CONDA_INSTALLED=1
command -v conda >/dev/null 2>&1 || CONDA_INSTALLED=0
if [[ $ANACONDA_INSTALLED -eq 0 ]]; then
    #install conda
    wget $MINICONDA_URL
    bash $( basename $MINICONDA_URL ) -b -p $MINICONDA_INSTALL_PATH
    export PATH="$MINICONDA_INSTALL_PATH/bin:$PATH"
fi

# enable access to freenome channel
conda config --add channels https://conda.anaconda.org/t/$ANACONDA_TOKEN/freenome
conda config --add channels conda-forge
conda config --add channels bioconda

# XXX -- I think this should happen automatically by installing freenome-build
# install conda packages needed for upload
# conda install --yes conda conda-verify conda-build anaconda-client

# install freenome-build
conda install freenome-build --yes

# output conda info for debugging
## I don't think that we need this anymore
# conda config --set anaconda_upload no
conda info -a
