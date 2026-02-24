#!/bin/bash
eval `/afs/slac/g/glast/isoc/flightOps/isoc-auto PROD isoc_env --add-env=flightops`
python -c "from ISOC import Log; Log.info(\"Level0Xrootd.copydata.ok\", \"Success for $PIPELINE_STREAM\", tgt=\"$PIPELINE_STREAM\")"
