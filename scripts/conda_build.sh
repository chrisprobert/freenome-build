#!/usr/bin/env bash

ANACONDA_TOKEN=$1
MINICONDA_URL=https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
MINICONDA_INSTALL_PATH=$HOME/miniconda

# check for conda install
ANACONDA_INSTALLED=1
command -v conda >/dev/null 2>&1 || ANACONDA_INSTALLED=0

# check that conda has not been installed with pip
PIP_INSTALLED=$( pip freeze | egrep conda ) >/dev/null 2>&1
if  [[ ! -z $PIP_INSTALLED ]]; then
    echo "conda is pip installed. Exiting."
    exit
fi

if [[ $ANACONDA_INSTALLED -eq 0 ]]; then
    #install conda
    wget $MINICONDA_URL
    bash $( basename $MINICONDA_URL ) -b -p $MINICONDA_INSTALL_PATH
    export PATH="$MINICONDA_INSTALL_PATH/bin:$PATH"
fi

# create a conda build environment
conda create -n freenome_conda_build python=$TRAVIS_PYTHON_VERSION --yes
source activate freenome_conda_build

# install conda packages needed for upload
conda install conda --yes
conda install conda-verify --yes
conda install conda-build --yes
conda install anaconda --yes

# add default channels
conda config --add channels conda-forge
conda config --add channels bioconda

# enable access to freenome channel
conda config --add channels https://conda.anaconda.org/t/$ANACONDA_TOKEN/freenome

# install freenome-build
conda install freenome-build --yes

# output conda info for debugging
conda config --set anaconda_upload no
conda info -a

# build lims_api and upload to conda
freenome_build deploy -u -p .

echo "conda build and upload success."
