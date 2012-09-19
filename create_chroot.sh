#!/bin/bash -ex

/bin/echo "vvvvvvvvvvvvvvvvvvv  create_chroot.sh vvvvvvvvvvvvvvvvvvvvvv"
IMAGETYPE=$1
DISTRO=$2
ARCH=$3
BASE=/var/cache/pbuilder/$IMAGETYPE.$DISTRO.$ARCH
BASETGZ_FILENAME=$4

BASETGZ_VERSION="0.3"
BASETGZ=/var/cache/pbuilder/$IMAGETYPE.$DISTRO.$ARCH-$BASETGZ_VERSION.tgz

echo $BASETGZ > $BASETGZ_FILENAME
ROOTDIR=$BASE/apt-conf-$BASETGZ_VERSION
IMAGELOCK=/var/cache/pbuilder/$IMAGETYPE.$DISTRO.$ARCH.updatelock
IMAGESTAMPFILE=/var/cache/pbuilder/$IMAGETYPE.$DISTRO.$ARCH.version

cd $WORKSPACE/buildfarm
REPOSTAMP=$(git log -n1 --pretty="%at")
/bin/echo "Repo stamp is $REPOSTAMP"
cd $WORKSPACE

if [ ! -f $BASETGZ ] ; then
    sudo flock $IMAGELOCK -c "pbuilder --create --distribution $DISTRO --architecture $ARCH --basetgz $BASETGZ --debootstrapopts --variant=buildd --components \"main universe multiverse\" --othermirror \"deb http://aptproxy.willowgarage.com/us.archive.ubuntu.com/ubuntu/ $DISTRO-updates main restricted\" --debootstrapopts --keyring=/etc/apt/trusted.gpg"
fi

UPDATE=$WORKSPACE/buildfarm/update_chroot.sh

/bin/echo "This script last updated at:"
ls -l $UPDATE


if [ ! -f $IMAGESTAMPFILE ] ; then
    IMAGESTAMP=0
else
    IMAGESTAMP=$(cat $IMAGESTAMPFILE)
fi
/bin/echo "Image stamp is $IMAGESTAMP"

if [ $REPOSTAMP -gt $IMAGESTAMP ] ; then

    /bin/echo "update has been updated, so let's update"
    /bin/echo $REPOSTAMP > stamp.tmp
    sudo rm -f $IMAGESTAMPFILE
    sudo mv stamp.tmp $IMAGESTAMPFILE
    sudo flock $IMAGELOCK -c "pbuilder execute --basetgz $BASETGZ --save-after-exec -- $UPDATE $IMAGETYPE"

fi


/bin/echo "^^^^^^^^^^^^^^^^^^  create_chroot.sh ^^^^^^^^^^^^^^^^^^^^"
