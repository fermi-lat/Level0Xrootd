#!/bin/sh
#
# This script consolidates a segment of the level0 raw-packet archive and
# copies it into xrootd storage.  It takes the following arguments:
#
#  $1 == A string of a form acceptable to `date -d` expressing the date of the segment to be processed
#  $2 == A string of a form acceptable to `date -d` expressing the time of the segment to be processed
#        Note that the string "$1 $2" must be acceptable to `date -d`
#  $3 == One of 'month', 'day', or 'hour' to indicate the size of the segment
#  $4 == Optionally, a working location for the consolidation operation
#
set -e
set -o pipefail

# set up the GLAST-specific Xrootd client tools
source /afs/slac/g/glast/applications/xrootd/bin/setxrootd.sh PROD

# start an isoc environment and defer the spread logging connection
eval `/afs/slac/g/glast/isoc/flightOps/isoc-auto PROD isoc_env --add-env=flightops`
export ISOC_LOG_SPGROUPPREFIX=disabled

# Make auxiliary scripts in the same directory as this one available via PATH.
# The cd-pwd trick makes the pathname absolute.
export PATH=$(cd $(dirname $0); pwd):${PATH}

# set the xroot destination
dest_xroot="/glast/level0"

# get command-line arguments
dateseg="$1 $2"
segsize="$3"
if [ -z "$4" ] ; then
    if [ -d /scratch ] ; then
	archdir="/scratch/level0-xrootd-$$/level0"
    else
	archdir="/tmp/level0-xrootd-$$/level0"
    fi
else
    archdir="$4"
fi

# get the source data location
if [ x"$segmentSource" == "xsitedep" ] ; then
    srcdir=`python -c 'from ISOC import SiteDep; print SiteDep.get("RawArchive", "archdir")' 2>/dev/null`
else
    srcdir=$segmentSource
fi
if [ x"$segmentSCID" == "xsitedep" ] ; then
    sciddir=`python -c 'from ISOC import SiteDep; print "src%04d" % SiteDep.getint("RawArchive","scid")' 2>/dev/null`
else
    sciddir=$segmentSCID
fi

# make the dest data location
mkdir -p $archdir
trap 'rm -rf $archdir' EXIT
stat $archdir

# make the time-dependent part of the hierarchy
case x"$segsize" in 
    xmonth) utcdir=`date -u -d "$dateseg" +%Y/%m` ;;
    xday)   utcdir=`date -u -d "$dateseg" +%Y/%m/%j.%m.%d.%a` ;;
    xhour)  utcdir=`date -u -d "$dateseg" +%Y/%m/%j.%m.%d.%a/utc%H` ;;
    x*)     echo "invalid segment $segsize"; exit 1 ;;
esac
if [ -z "$utcdir" ] ; then
    echo "invalid date specification ($dateseg)"
    exit 1
fi
echo "processing $segsize of $utcdir"

# merge each file in the specified directory
indir="$srcdir/$sciddir/$utcdir"
echo "merging files from $indir to $archdir"
for f in `find $indir -type f -name 's????a????t??????????*' -print |sort` ; do
    echo "merging $f"
    L0Archiver.py --arch $archdir -k 0 --quiet $f || exit 1
done

# make sure _something_ got merged
stat $archdir/$sciddir || exit 1
ls -l $archdir
    
# transfer the rearchived files to xrootd
echo "migrating files from $archdir to $dest_xroot"
pushd $archdir 2>&1 >/dev/null
for f in `find $sciddir -type f -print | sort` ; do
    fn=`basename $f .0000000000`
    fd=`dirname $f`
    run-xrdcp.py $f $dest_xroot/$fd/$fn || exit 1
done
popd 2>&1 >/dev/null

# set a marker file indicating that we succeeded
echo "$streamId" >$indir/xrootd_done

# exit cleanly for the pipeline
exit 0
