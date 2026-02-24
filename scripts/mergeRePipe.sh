#!/bin/sh
#
# script to merge multiple evt files as directed by an index
#

# Set up the environment for FlightOps code.
flavor=`cat ${taskBase}/config/flavor`
platform=`/afs/slac/g/glast/isoc/flightOps/isoc-platform`
echo "using ISOC platform $platform flavor $flavor with halfPipe $Name:  $"
eval `/afs/slac/g/glast/isoc/flightOps/${platform}/${flavor}/bin/isoc isoc_env --add-env=flightops`

# use scratch as tmp if available
if [ -d /scratch ] ; then
    export TMPDIR=/scratch
fi

# drop into the input directory
pushd ${outputBase}/${downlinkID} 2>&1 >/dev/null

# make a datagram-index file for this run
echo "creating datagram index"
grep -h ^DGM ????????-????????-????-?????.idx \
    | sort -u -b -k 2n,2 -k 5n,5 -k 6n,6 \
    >datagrams.idx || exit 1

# make a single event-index file for this run
echo "creating event index"
grep -h ^EVT ????????-????????-????-?????.idx \
    | sort -u -b -k 3g,3 -k 8n,8 \
    >events.idx || exit 1

# create the event-span text file and get the string-rep times for magic-7 retrieval
e0=$(head -n 1 -q events.idx | awk '{print $6}')
e1=$(tail -n 1 -q events.idx | awk '{print $6}')
echo "r0${runID} $e0 $e1" >event_times_${downlinkID}.txt
tevt0=`echo $e0 | python -c 'import datetime, sys; print datetime.datetime.utcfromtimestamp( float( sys.stdin.read() ) - 60.0 )'`
tevt1=`echo $e1 | python -c 'import datetime, sys; print datetime.datetime.utcfromtimestamp( float( sys.stdin.read() ) + 60.0 )'`

# get the level0 archive directory from the retrieval-definition files and then
# dump the magic-7 data for the span covered by the first and last events decoded
echo "getting L0 archive directory"
cat >l0arch.xsl <<EOF
<?xml version="1.0" encoding="US-ASCII"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:template match="/">
    <xsl:value-of select="retdef/arch"/>
  </xsl:template>
</xsl:stylesheet>
EOF
rdfile=`ls -1 RetDef-*.xml | head -1`
l0arch=`xsltproc l0arch.xsl $rdfile | tail -1`
echo "Level-0 archive at $l0arch"
scid=`head -n 1 -q events.idx  | awk '{print $7}'`
echo "retrieving magic-7 data from scid $scid for $tevt0 --> $tevt1"
python ${taskBase}/scripts/DiagRet.py --arch $l0arch --scid $scid -b "$tevt0" -e "$tevt1" --lsm \
    | grep -E 'ATT|ORB' > magic7_${downlinkID}.txt

# put the moot key/alias into the environment so it gets stored in the .evt files
export LSEWRITER_MOOTKEY=`grep ${runID} moot_keys_${downlinkID}.txt | awk '{print $2}'`
export LSEWRITER_MOOTALIAS=`grep ${runID} moot_keys_${downlinkID}.txt | awk '{print $3}'`
echo "exported LSEWRITER_MOOTKEY=$LSEWRITER_MOOTKEY"
echo "exported LSEWRITER_MOOTALIAS=$LSEWRITER_MOOTALIAS"

# make an output directory
rm -rf r0${runID}
mkdir r0${runID}

# pick up any chunk-scaling environment variables
if [ -s $taskBase/config/ChunkScaling ] ; then
    echo "Overriding chunk-scaling parameters:"
    cat $taskBase/config/ChunkScaling
    . $taskBase/config/ChunkScaling
fi

# optionally override max number of events-per-chunk
if [ -s $taskBase/config/maxEvents ] ; then
    maxE=`cat $taskBase/config/maxEvents`
    echo "overriding maxEvents from $maxEvents to $maxE"
    maxEvents=$maxE
fi

# run the merging application
echo "merging datagram streams"
python $taskBase/scripts/MergeDatagrams.py \
    -d datagrams.idx \
    -e events.idx \
    -o "r0${runID}" \
    -l ${downlinkID} --merge || exit 1

# now run the merging application
if [ $withOrphans == "yes" ] ; then
    echo "including orphan events"
    rm -f r0${runID}/r??????????-e*.idx
    outidx="r0${runID}/r0${runID}-e00000000000000000000.idx"
    awk '{print $1 " " $2 " " $3 " " $8 " " $9 " " $11 " " $12 " " $14 " " $15}' <events.idx >$outidx
fi
echo "writing merged event files"
outFile="r0${runID}/r%010d-e%020d.evt"
for midx in `ls -1 r0${runID}/r??????????-e*.idx` ; do
    writeMerge.exe $midx $outFile ${downlinkID} $maxEvents || exit 1
done

# clean up all the intermediate files
rm -f *.evt *.idx *.xml *.xsl r0${runID}/*.idx

