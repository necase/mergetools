#!/usr/bin/env python
# File encoding: utf-8, indentation: tabs
'''Print files that are duplicated within the given directory
'''
# Simplify support for Python 2.5 with some __future__ imports
from __future__ import absolute_import
from __future__ import division
from __future__ import with_statement

_qualname_ = __file__.partition('.')[0]

import logging
try:
	import configparser as ConfigParser
except ImportError:
	# Python 2
	import ConfigParser

import hashlib
import os
import sys


def _getDevelopmentVersion():
	try:
		import inspect
		import subprocess
		_moduleDirectory = os.path.dirname(os.path.realpath(inspect.getsourcefile(_getDevelopmentVersion) ) )
		describer = subprocess.Popen(["git", "describe"], cwd=_moduleDirectory,
				stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		version = describer.communicate()[0]
		if describer.returncode != 0:
			raise ValueError
	except Exception:
		import datetime
		version = 'unknown-' + datetime.datetime.now().strftime('%Y%m%d')

	return version.strip()


try:
	# The next line may be altered by setup.by during build; it needs to start with optional whitespace and the text "__version__"
	__version__ = VERSION
except NameError:
	__version__ = _getDevelopmentVersion()


def dupdict(seq):
	'''Transform a list of 2-tuples (or other similar sequence type) into a
	dict-like object.  The keys of the dict are taken from the first element
	of the tuples, and the values are the second elements.  If multiple tuples
	have the same first element, the value for that key will have all the
	second elements stored in a list.
	'''
	from collections import defaultdict
	d = defaultdict(list)
	for pair in seq:
		d[pair[0] ].append(pair[1] )
	return d


def listdup(dirname, minsize=1):
	'''Print files that are duplicated within the directory.'''
	filesizes = []
	for root, dirs, files in os.walk(dirname):
		for name in files:
			filename = os.path.abspath(os.path.join(root, name) )
			size = os.stat(filename).st_size
			filesizes.append( (size, filename) )
	d = dupdict(filesizes)
	sig = []
	for size, filenames in d.items():
		if size < minsize or len(filenames) < 2: continue
		for filename in filenames:
			try:
				f = open(filename, 'rb')
			except IOError:
				# Can happen if the file is deleted during the script run,
				# or if a link points to a non-existent file
				continue
			m = hashlib.sha256()
			while True:
				data = f.read(1048576)
				if not data:
					break
				m.update(data)
			f.close()
			sig.append( (m.hexdigest(), filename) )
	dupsigs = dupdict(sig)
	for sig, filenames in dupsigs.items():
		if len(filenames) < 2: continue
		print( '"' + '" = "'.join(filenames)  + '"')



log = logging.getLogger(__name__)
class _NullLogHandler(logging.Handler):
	'''A logging handler that performs no action.  It suppresses a warning
	about not configuring logging if the module is imported by another that
	has not configured logging.  For Python 2.7+, use logging.NullHandler
	'''
	def emit(self, x):
		pass
log.addHandler(_NullLogHandler() )


def _debugException(typ, val, tb):
	import traceback, pdb
	traceback.print_exception(typ, val, tb)
	pdb.post_mortem(tb)


def readConfigurationFile(filename, defaultValues=None):
	'''Read a configuration file with a base name given by filename.  Search
	for the file in various system and user directories, and return a
	dictionary containing all the properties set in the configuration files
	it finds.
	'''
	# search in package, then system, then user, then current directory
	if sys.platform.startswith('win'):
		appdata = os.environ['APPDATA'] # Need to add one or more system-wide directories
		path = [os.path.join(appdata, _qualname_),
				_qualname_,
				'']
	elif sys.platform.startswith('darwin'):
		home = os.environ['HOME']
		path = [os.path.join('/Library/Preferences', _qualname_),
				os.path.join('/etc', _qualname_),
				os.path.join('/usr/local/etc', _qualname_),
				os.path.join(home, 'Library/Preferences', _qualname_),
				os.path.join(home, '.' + _qualname_),
				'']
	else:
		# Cygwin, linux, os2, riscos, atheos all fall here
		home = os.environ['HOME']
		path = [os.path.join('/etc', _qualname_),
				os.path.join('/usr/local/etc', _qualname_),
				os.path.join(home, '.' + _qualname_),
				'']
	filenames = [os.path.join(item, filename) for item in path]
	
	c = ConfigParser.ConfigParser(defaultValues)
	c.read(filenames)
	o = c.defaults()
	for section in c.sections():
		o[section.lower() ] = dict(c.items(section) )
	def coerceValues(values, reference):
		for ndx, item in reference.items():
			if isinstance(item, dict):
				castValues(values[ndx], item)
			else:
				if ndx in values:
					values[ndx] = type(item)(values[ndx])
	if defaultValues:
		coerceValues(o, defaultValues)
	return o


def run_cli(argv=None):
	'''Run the command-line interface to listdup.  Parse any options
	in a configuration file or on the command line, then print equivalent
	files to the screen.
	'''
	import logging.handlers
	import optparse
	
	if argv == None:
		argv = sys.argv[1:]
	logging.basicConfig()
	# Read options from argument list
	clparser = optparse.OptionParser(usage="usage: %prog [options] dirname",
			description=__doc__)
	# Generic options
	clparser.add_option('-d', '--debug', dest='debug', action='store_true',
			help='Invoke the python debugger on exceptions')
	clparser.add_option('--loglevel', dest='loglevel',
			help='Set logging level', metavar='LEVEL')
	clparser.add_option('-l', '--logfile', dest='logfile',
			help='Set logging file name', metavar='FILE')
	clparser.add_option('--version', dest='version',
			help='Display program version and exit', action='store_true')
	clparser.add_option('--usage', dest='usage',
			help='Print usage information and exit', action='store_true')
	clparser.add_option('--verbose', dest='verbose',
			help='Print verbose information during program execution',
			action='store_true')
	clparser.add_option('-f', '--file', dest='filename',
			help='Set configuation file name', metavar='FILE')
	
	# listdup-specific options
	clparser.add_option('--min', dest='minsize', metavar='SIZE',
			help='Set minimum size to search for identical files (default 1; 0 means any file size)',
			type='int')
	clparser.set_defaults(filename = _qualname_ + '.cfg')
	(options, args) = clparser.parse_args(argv)
	
	# If there are options for which reading the configuration file
	# and runnning the application code are not necessary, handle
	# them after the command line is parsed and before the configuration
	# files are read
	if options.verbose:
		log.setLevel(logging.INFO)
	
	if options.version:
		print(_qualname_ + ' version ' + __version__ )
		return 0
	
	if options.usage or len(args) != 1:
		if not options.usage:
			print('Must supply exactly one directory to list duplicates.  See usage below.')
		clparser.print_help()
		return 0
	
	# Read options from config file
	o = readConfigurationFile(options.filename)
	
	# Override config file options with command-line options
	clopts = vars(options)
	for key, value in clopts.items():
		if value != None or key not in o:
			o[key] = value
	
	# Configuration parameters are now at their final states,
	# so use the information to configure application behavior
	if o['debug']:
		log.setLevel(logging.DEBUG)
		sys.excepthook = _debugException
	
	if o['loglevel']:
		loglevels = {'debug':logging.DEBUG, 'info':logging.INFO,
				'warning':logging.WARNING, 'error':logging.ERROR,
				'critical':logging.CRITICAL}
		try:
			log.setLevel(loglevels[o['loglevel'] ] )
		except KeyError:
			log.warning('Invalid log level: %s' % o['loglevel'])
	
	if o['logfile']:
		if o['logfile'] == 'syslog':
			# log to syslog
			if sys.platform.startswith('win'):
				syslogName = ('localhost', 514)
			elif sys.platform.startswith('darwin'):
				syslogName = '/var/run/syslog'
			else:
				syslogName == '/dev/log'
			log.addHandler(logging.handlers.SyslogHandler(syslogName) )
		else:
			log.addHandler(
					logging.handlers.RotatingFileLogHandler(o['logfile'],
							maxBytes=30000, backupCount=3) )
	
	# Configuration has completed; run the application
	if len(args) != 1:
		log.error('Exactly one directory must be specified')
		return 22
	
	kwargs = {}
	if o['minsize'] != None: kwargs['minsize'] = o['minsize']
	listdup(*args, **kwargs)
	return 0


if __name__ == '__main__':
	# Suppress a warning about a broken pipe if the output of this script
	# is piped to the input of another program (like less) that exits
	# before reading the entire output
	import signal
	signal.signal(signal.SIGPIPE, signal.SIG_DFL)
	sys.exit(run_cli() )

