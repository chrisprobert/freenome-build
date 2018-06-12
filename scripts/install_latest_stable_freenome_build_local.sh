#!/usr/bin/env bash

isZsh() {
    if [ -n "$(ps -p "$$" | grep zsh)" ]; then
        return 0
    else
        return 1
     fi
 }

set -e

ANACONDA_TOKEN=$1
if [ $(uname) = 'Linux' ]; then
    MINICONDA_URL='https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh'
elif [ $(uname) = 'Darwin' ]; then
    MINICONDA_URL='https://repo.continuum.io/miniconda/Miniconda3-latest-MacOSX-x86_64.sh'
else
    echo "We do not support $(uname) architecture at this time"
    exit 1
fi

MINICONDA_INSTALL_PATH=$HOME/miniconda

mkdir -p $MINICONDA_INSTALL_PATH;
pushd $MINICONDA_INSTALL_PATH;

# check for conda install, and install if neessary
CONDA_INSTALLED=1
command -v conda >/dev/null 2>&1 || CONDA_INSTALLED=0
if [[ $ANACONDA_INSTALLED -eq 0 ]]; then
    # install conda
    curl -sO $MINICONDA_URL;
    bash $(basename $MINICONDA_URL) -b -u -p $MINICONDA_INSTALL_PATH;
    # activate the base conda environment
    export PATH="$MINICONDA_INSTALL_PATH/bin:$PATH";
fi

ACCOUNT_INSTRUCTIONS='Please head to https://anaconda.org and create an account. Then ask an admin to add you to the Freenome group. When have finished with this, press ENTER'

# If we are using zsh, 'read' has different syntax
if [ $isZsh ]; then
    read "?$ACCOUNT_INSTRUCTIONS"
else
    read -p "$ACCOUNT_INSTRUCTIONS"
fi

ANACONDA_TOKEN=$(anaconda auth --create --name $USER-admin-token8)

# setup the condarc with the correct set of channels
conda config --remove channels defaults || true
conda config --add channels https://repo.anaconda.com/pkgs/pro/
conda config --add channels https://repo.anaconda.com/pkgs/free/
conda config --add channels https://repo.anaconda.com/pkgs/main/
conda config --add channels conda-forge
conda config --add channels bioconda
conda config --add channels https://conda.anaconda.org/t/$ANACONDA_TOKEN/freenome

# install freenome-build
conda install freenome-build --yes

RC_PROMPT='Please enter the directory for you *.rc file for us to automatically add conda to PATH on shell startup (if you wish to skip this step, just press ENTER): '

# If we are using zsh, 'read' has different syntax
if [ $isZsh ]; then
    read "RC_PATH?$RC_PROMPT"
else
    read -p "$RC_PROMPT" -r RC_PATH
fi


# Expand directory shorthands
eval RC_PATH=$RC_PATH
if [ -z $RC_PATH ]; then
    echo 'Since you have opted out of adding conda to PATH on shell startup, you will have to run this script each time you wish to use Conda in a shell'
else
    echo "
# Conda initialization
export ANACONDA_TOKEN=$ANACONDA_TOKEN
. ~/miniconda3/etc/profile.d/conda.sh
conda activate
        " >> $RC_PATH
fi

popd;
