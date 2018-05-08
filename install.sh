# install miniconda
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

# install conda in the base environment
conda install conda --yes
conda install conda-verify --yes
conda install conda-build --yes
conda install anaconda --yes