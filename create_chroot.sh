#!/bin/sh -x

/bin/echo "vvvvvvvvvvvvvvvvvvv  create_chroot.sh vvvvvvvvvvvvvvvvvvvvvv"
DISTRO=$1
ARCH=$2

BASETGZ=/var/cache/pbuilder/$DISTRO-$ARCH.tgz

if [ ! -f $BASETGZ ] ; then
    sudo pbuilder --create \
        --distribution $DISTRO \
        --architecture $ARCH \
        --basetgz $BASETGZ \
        --debootstrapopts --variant=buildd \
        --components "main universe multiverse"
fi

UPDATE=$WORKSPACE/buildfarm/update_chroot.sh
STAMP=$WORKSPACE/$DISTRO-$ARCH.update_chroot.sh.stamp

if [ -e $STAMP ] ; then
    /bin/echo -n "Chroot last updated at:"
    ls -l $STAMP
else
    /bin/echo -n "No timestamp exists at $STAMP"
fi

if [ -n $STAMP -o $STAMP -ot $UPDATE ] ; then
    /bin/echo "update has been updated, so let's update"
    sudo touch $STAMP
    /bin/echo -n "Stamped:"
    ls -l $STAMP
    sudo pbuilder execute \
        --basetgz $BASETGZ \
        --save-after-exec \
        -- $UPDATE
fi

/bin/echo "^^^^^^^^^^^^^^^^^^  create_chroot.sh ^^^^^^^^^^^^^^^^^^^^"
