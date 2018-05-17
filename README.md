# freenome-build
Packaging and build tools.

## Bootstrapping requires scripts/conda_build.sh
Each repo must clone the freenome-build repo during a travis build so that it can call `scripts/conda_build.sh`. This requires that that repo on travis has a github access token generated locally using the ruby travis script. For example for LIMS-API I ran the following

travis endpoint --pro --set-default
travis login
travis sshkey --generate -r freenome/LIMS-API     --debug
