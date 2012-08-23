set -ex
/bin/echo "vvvvvvvvvvvvvvvvvvv  dispatch.sh vvvvvvvvvvvvvvvvvvvvvv"

#always ask for pbuilder to make sure we have the updated patched version
sudo apt-get -y install pbuilder

export WORKSPACE

if [ -z "$WORKSPACE" ] ; then
    /bin/echo "Uh, workspace not set."
    exit 1
fi

# The new way is to set SCRIPT, along with some other important
# variables.  The old way is to infer that stuff from JOB_NAME.
if [[ -z "$SCRIPT" ]]; then
  # Old way
  /bin/echo "IF you fail here your job name is corrupt."
  /bin/echo "Format:"
  /bin/echo "some-script-name.IMAGETYPE.UBUNTUCODENAME.ARCH"
  
  [[ $JOB_NAME =~ ([^\.]+)\.([^\.]+)\.([^\.]+)\.([^\.]+) ]]
  SCRIPT=${BASH_REMATCH[1]}.sh
  IMAGETYPE=${BASH_REMATCH[2]}
  UBUNTU_DISTRO=${BASH_REMATCH[3]}
  ARCH=${BASH_REMATCH[4]}

  /bin/echo <<EOF
  SCRIPT=$SCRIPT
  IMAGETYPE=$IMAGETYPE
  UBUNTU_DISTRO=$UBUNTU_DISTRO
  ARCH=$ARCH
EOF

  if [[ $SCRIPT =~ ^([^_]+)_([^_]+)$ ]] ; then
      SCRIPT=${BASH_REMATCH[1]}
      SCRIPTARGS=${BASH_REMATCH[2]}
  fi
fi

#
#  update buildfarm utils
#
cd $WORKSPACE

if [ -d buildfarm ] ; then
  cd buildfarm
  git clean -dfx
  git reset --hard HEAD
  git pull
  cd ..
else
  git clone git://github.com/willowgarage/buildfarm.git
fi

. ./buildfarm/buildfarm_util.sh

export > env


sudo mkdir -p /var/cache/pbuilder/ccache
sudo chmod a+w /var/cache/pbuilder/ccache

cat > pbuilder-env.sh <<EOF
#!/bin/bash -ex
/bin/echo "vvvvvvvvvvvvvvvvvvv  pbuilder-env.sh vvvvvvvvvvvvvvvvvvvvvv"
export CCACHE_DIR="/var/cache/pbuilder/ccache"
export PATH="/usr/lib/ccache:${PATH}"
export WORKSPACE=$WORKSPACE
export UBUNTU_DISTRO=$UBUNTU_DISTRO
export ARCH=$ARCH
export IMAGETYPE=$IMAGETYPE
export ROSDISTRO_NAME=$ROSDISTRO_NAME
export OS_NAME=$OS_NAME
export OS_PLATFORM=$OS_PLATFORM
export STACK_NAME=$STACK_NAME
export STACK_XML_URL=$STACK_XML_URL
export STACK_BUILD_DEPENDS="$STACK_BUILD_DEPENDS"
export ROSINSTALL_URL=$ROSINSTALL_URL
export JOB_TYPE=$JOB_TYPE
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
exec $WORKSPACE/buildfarm/${SCRIPT} ${SCRIPTARGS}
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
    --bindmounts "/var/cache/pbuilder/ccache /home" \
    --inputfile $WORKSPACE/buildfarm/$SCRIPT \
    -- $WORKSPACE/pbuilder-env.sh $SCRIPT

/bin/echo "^^^^^^^^^^^^^^^^^^  dispatch.sh ^^^^^^^^^^^^^^^^^^^^"
