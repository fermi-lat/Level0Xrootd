#!/bin/sh
#
# script to select the staging buffer location intelligently
#
# $1 == file of staging buffer directories, one per line
# $2 == the downlink/delivery ID
#

# get the command line arguments
buflist=$1
downlinkid=$2

# get the number of available buffers
nbuffers=`wc -l $buflist`


