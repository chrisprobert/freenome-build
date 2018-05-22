#!/bin/bash

PYTHON_VERSION=3.6

# install miniconda
MINICONDA_URL=https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
MINICONDA_INSTALL_PATH=$HOME/miniconda

# check for conda install
ANACONDA_INSTALLED=1
command -v conda >/dev/null 2>&1 || ANACONDA_INSTALLED=0

if [[ $ANACONDA_INSTALLED -eq 0 ]]; then
    #install conda
    wget $MINICONDA_URL
    bash $( basename $MINICONDA_URL ) -b -p $MINICONDA_INSTALL_PATH
    export PATH="$MINICONDA_INSTALL_PATH/bin:$PATH"

    # install conda in the base environment
    conda install conda conda-verify conda-build anaconda-client --yes
fi

python setup.py install
