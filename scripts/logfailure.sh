#!/bin/bash
eval `/afs/slac/g/glast/isoc/flightOps/isoc-auto PROD isoc_env --add-env=flightops`
python -c "from ISOC import Log; Log.error(\"Level0Xrootd.copydata.fail\", \"Failed for $PIPELINE_STREAM\", tgt=\"$PIPELINE_STREAM\")"
