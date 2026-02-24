#!/bin/env python

import re, subprocess, sys, time

def main(infile, outfile):
    runner = CopyRunner(infile, outfile)
    runner.run()
    while runner.noSpaceLeft():
        runner.prepForRetry()
        runner.run()
    return runner.retcode()

class CopyRunner(object):
    def __init__(self, infile, outfile, waitMinutes=5, maxTries=5):
        self._infile = infile
        self._outfile = "root://glast-rdr/" + outfile
        self._retcode = 0
        self._nospace = False
        self._errorRe = re.compile(r"\bserver\s+error\s+300(5|9)\b.*\bno\s+space\s+left\b", re.IGNORECASE)
        self._waitSecs = waitMinutes * 60
        self._maxTries = maxTries
        self._tries = 0

    def noSpaceLeft(self):
        return self._nospace and (self._retcode != 0)

    def retcode(self):
        return self._retcode

    def prepForRetry(self):
        command = ["xrd.pl", "rm", self._outfile]
        print " ".join(command)
        subprocess.call(command)
        if self._tries < self._maxTries:
            print "Waiting for", self._waitSecs, "seconds before retrying."
            time.sleep(self._waitSecs)

    def run(self):
        if self._tries < self._maxTries:
            self._tries += 1
            command = ["xrdcp", "-sf", self._infile, self._outfile]
            print " ".join(command)
            child = subprocess.Popen(command,
                                     shell=False, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            out, err = child.communicate()
            self._retcode = child.returncode
            self._nospace = (self._errorRe.search(err) is not None)
            if out:
                print out
            if err:
                print >>sys.stderr, err
        else:
            self._nospace = False
            self._retcode = 1
            print >>sys.stderr, "GIVING UP!"

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print >>sys.stderr, "Usage: run-xrdcp INPUT-FILENAME XROOT-FILENAME"
        print >>sys.stderr, "where XROOT-FILENAME is what should come after 'root://glast-rdr/',"
        print >>sys.stderr, "e.g., /glast/level0/src0077/2012/11/307.11.02.Fri/..."
        sys.exit(1)
    else:
        sys.exit(main(sys.argv[1], sys.argv[2]))
