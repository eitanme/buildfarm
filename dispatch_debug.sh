set -ex
/bin/echo "vvvvvvvvvvvvvvvvvvv  dispatch.sh vvvvvvvvvvvvvvvvvvvvvv"

# pass all arguments to the dispatcher on to the script we're running
SCRIPT_ARGS=""
for i in $*
  do 
  SCRIPT_ARGS=`echo $SCRIPT_ARGS $i`
done
echo "Arguments for script: " $SCRIPT_ARGS

#always ask for pbuilder to make sure we have the updated patched version
sudo apt-get update
sudo apt-get -y install pbuilder


#  update buildfarm utils
cd $WORKSPACE

. ./buildfarm/buildfarm_util.sh

export > env


sudo mkdir -p /var/cache/pbuilder/ccache
sudo chmod a+w /var/cache/pbuilder/ccache

cat > pbuilder-env.sh <<EOF
#!/bin/bash -ex
/bin/echo "vvvvvvvvvvvvvvvvvvv  pbuilder-env.sh vvvvvvvvvvvvvvvvvvvvvv"
export CCACHE_DIR="/var/cache/pbuilder/ccache"
export PATH="/usr/lib/ccache:${PATH}"
export IMAGETYPE=$IMAGETYPE

export OS_NAME=$OS_NAME
export OS_PLATFORM=$OS_PLATFORM
export UBUNTU_DISTRO=$UBUNTU_DISTRO
export ARCH=$ARCH

export WORKSPACE=$WORKSPACE
export PYTHONPATH=$WORKSPACE/catkin-debs/src/buildfarm

if [ -d \$HOME/.ssh ]; then
  cp -a \$HOME/.ssh /root
  chown -R root.root /root/.ssh
fi
if [ -d \$HOME/.subversion ]; then
  cp -a \$HOME/.subversion /root
  chown -R root.root /root/.subversion
fi
pwd
ls -l
cd $WORKSPACE
ls -l
chmod 755 $WORKSPACE/buildfarm/${SCRIPT}

echo "============================================================"
echo "==== Begin" $SCRIPT "script.    Ignore the output above ====="
echo "============================================================"

$WORKSPACE/buildfarm/${SCRIPT} ${SCRIPT_ARGS}

echo "============================================================"
echo "==== End" $SCRIPT "script.    Ignore the output below ====="
echo "============================================================"

EOF


chmod 755 pbuilder-env.sh

TOP=$(cd `dirname $0` ; /bin/pwd)

/usr/bin/env

tmpdir=`mktemp -d`
basetgz_filename=$tmpdir/basetgz
$WORKSPACE/buildfarm/create_chroot.sh $IMAGETYPE $UBUNTU_DISTRO $ARCH $basetgz_filename
basetgz=`cat $basetgz_filename`
rm -rf $tmpdir

sudo pbuilder execute \
    --basetgz $basetgz \
    --bindmounts "/var/cache/pbuilder/ccache $WORKSPACE" \
    --inputfile $WORKSPACE/buildfarm/$SCRIPT \
    -- $WORKSPACE/pbuilder-env.sh $SCRIPT


/bin/echo "^^^^^^^^^^^^^^^^^^  dispatch.sh ^^^^^^^^^^^^^^^^^^^^"
