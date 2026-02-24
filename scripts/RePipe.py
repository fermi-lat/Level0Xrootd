#!/afs/slac/g/glast/isoc/flightOps/rhel4_gcc34/ISOC_PROD/bin/shisoc --add-env=flightops python
#
# Script to generate a "fake" downlink and re-deliver a specific acquisition.

import errno, getpass, logging, os, sys

import sqlalchemy as SA

from Ft.Xml import MarkupWriter

from quarks.cmdline.xoptparse import OptionParser
from quarks.database.dbconfig import DbConfig

from ISOC import SiteDep
from ISOC.TlmUtils import ApidSets

# set basic logging configuration
logging.basicConfig( format='%(asctime)s.%(msecs)03d %(levelname)-8s %(name)s: %(message)s',
                     datefmt='%Y-%m-%d %H:%M:%S' )
logging.getLogger().setLevel( logging.INFO )
_log = logging.getLogger()

acqtype = { 'LPA' : 'LSEP', 'LCI' : 'LSEC' }

def writeRetDef( ofd, type, scid, archroot, spans, l0key = -1, downlinkid = -1, chunkid = -1, runid = -1, gndid = -1, start = -1 ):
    """!@brief Write an event-retrieval definition file

    This routine writes an XML retrieval definition to a file-like object.  The
    resulting file can be used to drive the CHS/eventRet offline applictation to
    extract event data from a set of CCSDS packets.

    @param[in] type Retrieval type, either 'LSEP' or 'LSEC'
    @param[in] ofd File-like object for output
    @param[in] scid Spacecraft ID for use in retrieving data
    @param[in] archroot Root of the L0 packet archive
    @param[in] spans sequence of 3-tuples specifying (apid, t0, t1) to be retrieved
    @param[in] l0key Database key of L0 transfer package providing the data
    @param[in] downlinkid  Downlink ID of the package pointed to by l0key
    @param[in] chunkid ID of the chunk (datagram segment) of the downlink being processed
    @param[in] runinfo Dictionary with keys 'runid', 'gndid', and 'start' specifying
                       run-related information
    """
    # define the internal DTD fragment specifying the structure of the document
    dtd = """<?xml version="1.0" encoding="US-ASCII" ?>
<!DOCTYPE retdef [
<!ELEMENT retdef (arch, run, spans)>
<!ATTLIST retdef
   type (LSEP|LSEC) #REQUIRED
>
<!ELEMENT arch (#PCDATA)>
<!ATTLIST arch
   scid CDATA #REQUIRED
>
<!ELEMENT run (#PCDATA)>
<!ATTLIST run
   runid CDATA #REQUIRED
   l0key CDATA #REQUIRED
   chunkid CDATA #REQUIRED
   gndid CDATA #REQUIRED
   start CDATA #REQUIRED
>
<!ELEMENT spans (span+)>
<!ELEMENT span (#PCDATA)>
<!ATTLIST span
   apid CDATA #REQUIRED
   tbeg CDATA #REQUIRED
   tend CDATA #REQUIRED
>
]>  
"""
    # write the DTD to the output file
    ofd.write( dtd )
    ofd.write( '' )

    # now write out the XML data
    mw = MarkupWriter( stream=ofd, indent=u'yes', omitXmlDeclaration=u'yes' )
    mw.startDocument()
    mw.startElement( u'retdef', attributes={u'type': u'%s' % type} )
    mw.simpleElement( u'arch', attributes={u'scid': u'%s' % scid}, content=u'%s' % archroot )
    mw.simpleElement( u'run', attributes = { u'runid' : u'%s' % runid,
                                             u'l0key' : u'%s' % l0key,
                                             u'chunkid' : u'%s' % chunkid,
                                             u'gndid' : u'%s' % gndid,
                                             u'start' : u'%s' % start } )
    mw.startElement( u'spans' )
    for apid, t0, t1 in spans:
        tbeg = u'%s' % t0
        try:
            tbeg = u'%.6f' % t0
        except:
            pass
        tend = u'%s' % t1
        try:
            tend = u'%.6f' % t1
        except:
            pass
        mw.simpleElement( u'span', attributes = { u'apid' : u'%s' % apid,
                                                  u'tbeg' : u'%s' % tbeg,
                                                  u'tend' : u'%s' % tend } )
    mw.endElement( u'spans' )
    mw.endElement( u'retdef' )
    mw.endDocument()

# handle command line
p = OptionParser()
p.add_option( '--apids', type='apidset', default='956,957',
              help='List of apids for retrieval (%default)' )
p.add_option( '-a', '--arch', default=SiteDep.get('RawArchive', 'archdir'),
              help='raw-archive root directory (%default)' )
p.add_option( '--dbi', default=SiteDep.get('RawArchive', 'dbi' ),
              help='handle to database instance (%default)' )
p.add_option( '-p', '--prefix', default=getpass.getuser(),
              help='acq-summary table-name prefix (%default)' )
p.add_option( '-s', '--scid', type='int', default=SiteDep.get('RawArchive', 'scid' ),
              help='spacecraft id (%default)' )
p.add_option( '-o', '--outbase', default=".",
              help='output directory (%default)' )
p.add_option( '-r', '--runid', type='int',
              help='run id' )
p.add_option( '-d', '--downlink', type='hexordec',
              help='Downlink ID' )
opts, args = p.parse_args()

# get a database connection and the acquisition-summary table
db = DbConfig.fromConfigParser( SiteDep, opts.dbi )
tbl = SA.Table( '%s_acqsummary' % opts.prefix, db.metadata, autoload=True )

# fetch the summary of the acquisition
row = tbl.select().execute( scid=opts.scid, startedat=opts.runid ).fetchone()
if row is None or len(row) == 0:
    _log.error( 'RePipe: run %d for scid %d not found in %s at %s' % ( opts.runid, opts.scid, tbl.name, opts.dbi ) )
    sys.exit(1)

# make the output working directory
outdir = os.path.join( opts.outbase, '%09d' % opts.downlink )
oldum = os.umask( 0 )
try:
    try:
        os.makedirs( outdir, 02775 )
        _log.info( 'RePipe: created output directory %s' % outdir )
    except OSError, oe:
        if oe.errno == errno.EEXIST:
            _log.info( 'RePipe: output directory %s already exists' % outdir )
            pass
finally:
    os.umask( oldum )

# create retdef files for the acquisition
chunkid=1
for a in opts.apids:
    ofd = open( os.path.join( outdir, 'RetDef-%09d-%05d.xml' % ( opts.downlink, chunkid ) ), 'w' )
    writeRetDef( ofd, acqtype[row.type], row.scid, opts.arch,
                 [ (a, row.dgmutc0, row.dgmutc1), ],
                 downlinkid=opts.downlink, runid=row.startedat, start=row.startedat, gndid=-1, chunkid=chunkid )
    _log.info( 'RePipe: created chunk file %s for apid %d of run %d (%s - %s)' % \
              (ofd.name, a, row.startedat, row.dgmutc0, row.dgmutc1) )
    ofd.close()
    chunkid += 1

# create the various L1Proc-interface files
ofd = open( os.path.join( outdir, 'delivered_events_%09d.txt' % opts.downlink ), 'w' )
print >> ofd, 'r%010d %d 0 %s' % ( row.startedat, row.nevts, row.type )
ofd.close()

ofd = open( os.path.join( outdir, 'retired_runs_%09d.txt' % opts.downlink ), 'w' )
print >> ofd, 'r%010d %s' % ( row.startedat, row.status.upper() )
ofd.close()

ofd = open( os.path.join( outdir, 'event_gaps_%09d.txt' % opts.downlink ), 'w' )
ofd.close()

# ofd = open( os.path.join( outdir, 'event_times_%09d.txt' ), 'w' )
# print >> ofd, 'r%010d %d 0 %s' % ( row.startedat, row.nevt, row.type )
# ofd.close()

ofd = open( os.path.join( outdir, 'moot_keys_%09d.txt' % opts.downlink ), 'w' )
print >> ofd, 'r%010d %d %s' % ( row.startedat, row.moot_key, row.moot_alias )
ofd.close()





