#!/usr/bin/env python
# File encoding: utf-8, indentation: tabs
'''Recursively merge one directory into a second, with options on how to handle conflicts
'''
# Future options to be considered:
# Other automatic (although strange) ways to handle conflicts:
# keep only the file with the longest/shortest path name
# keep only the file whose name comes first/last alphabetically

# Simplify support for Python 2.5 with some __future__ imports
from __future__ import absolute_import
from __future__ import division
from __future__ import with_statement

_qualname_ = __file__.partition('.')[0]

import filecmp
import logging
try:
	import configparser as ConfigParser
except ImportError:
	# Python 2
	import ConfigParser

import os
import sys
import shutil

if sys.version < '3':
	def text(x, e=sys.getfilesystemencoding() ):
		# Convert data type to text type
		return x.decode(e)
else:
	raw_input = input
	def text(x, e=sys.getfilesystemencoding() ):
		try:
			return x.decode(e)
		except AttributeError:
			return x


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
	# The next line may be altered by setup.by during build; it must start with optional whitespace and the text "__version__"
	__version__ = VERSION
except NameError:
	__version__ = _getDevelopmentVersion()


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


_signatureSize = 0
def gensig(dirname):
	'''Return a list of one tuple for each file in directory dirname,
	each containing a file signature and the file name.  The file
	signature is a string composed of the sha256 hash of the file
	contents (of size given by global variable _signatureSize, which
	is set in this function) with the file size appended to its end.
	'''
	# To avoid reading all the files, the algorithm could use the
	# file size as a signature, and only get the checksums of files
	# that have duplicate file sizes (and have sizes > 0), but that
	# requires the signature generation to stat all files in both
	# directories first, then read the files later.
	global _signatureSize
	import hashlib
	sig = []
	newSig = hashlib.sha256
	if _signatureSize == 0:
		_signatureSize = len(newSig().hexdigest() )
	for root, dirs, files in os.walk(dirname):
		for name in files:
			filename = os.path.abspath(os.path.join(root, name) )
			size = os.stat(filename).st_size
			try:
				f = open(filename, 'rb')
			except IOError:
				# Can happen if the file is deleted during the script run, or if a link points to a non-existent file
				continue
			m = newSig()
			while True:
				c = f.read(1048576)
				if not c:
					break
				m.update(c)
			f.close()
			sig.append( (str(m.hexdigest()) + str(size), filename) )
	return sig


def duplicates(seqA, seqB):
	'''Return a generator of duplicate items in the given sequences.'''
	return ( x for x in seqA if x in seqB )


def split_path(p):
	'''Split a path into a list with each directory component as one element.'''
	# http://stackoverflow.com/a/15050936
	a, b = os.path.split(p)
	return (split_path(a) if len(a) and len(b) else []) + [b]


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


def rmerge(aname, bname, interactive=False, suffix=''):
	'''Move all files from aname to bname, as long as that will not overwrite
	an existing file.  If it would, handle the conflict interactively if
	interactive is True, or append a suffix if suffix is not empty, or else
	print the relative file name.
	'''
	if suffix and interactive:
		raise ValueError('Only one of --interactive or --suffix may be specified')
	try:
		if os.path.samefile(aname, bname):
			log.error('Different directories must be specified')
	except AttributeError:
		#os.path.samefile does not exist on old versions of python for windows
		pass
	if aname=='' or bname == '' or aname == bname:
		log.error('Two different directories must be specified')
		return 22
	
	for fname in os.listdir(aname):
		destfilename = os.path.abspath(os.path.join(bname, fname) )
		if os.path.exists(destfilename):
			srcfilename = os.path.abspath(os.path.join(aname, fname) )
			if filecmp.cmp(srcfilename, destfilename, shallow=False):
				log.debug("Removing file " + text(srcfilename) )
				os.remove(srcfilename)
			else:
				if interactive:
					import difflib
					print('Conflict found with file ' + text(fname) )
					with open(srcfilename, 'rb') as f:
						srcstr = f.readlines()
					with open(destfilename, 'rb') as f:
						deststr = f.readlines()
					for line in difflib.unified_diff(srcstr, deststr, srcfilename, destfilename):
						sys.stdout.write(line)

					a = raw_input("Which version of " + text(fname) + " would you like to keep? (+, -, o) ")
					if a == '-':
						log.debug("Moving file " + text(srcfilename) + " to " + text(destfilename) )
						shutil.move(srcfilename, destfilename)
					elif a == '+':
						log.debug("Removing file " + text(srcfilename) )
						os.remove(srcfilename)
				elif suffix:
					destfilename = text(destfilename)
					while os.path.exists(destfilename):
						destfilename += text(suffix)
					log.debug("Moving file " + text(srcfilename) + " to " + destfilename)
					shutil.move(srcfilename, destfilename )
				else:
					print(fname)
		else:
			srcfilename = os.path.abspath(os.path.join(aname, fname) )
			if not os.path.exists(os.path.dirname(destfilename) ):
				os.makedirs(os.path.dirname(destfilename) )
			shutil.move(srcfilename, destfilename)

	# Remove any remaining empty directories	
	for root, dirs, files in walkslow(aname):
		if root == aname: continue
		if not dirs and not files:
			os.rmdir(root)
	return


def smerge(aname, bname, interactive=False, suffix='', commonsuffix=0, minsize=1):
	'''Move all files from aname to bname, as long as that will not overwrite
	an existing file and there are no identical files already somewhere within
	directory bname.  Otherwise, handle the conflict interactively if
	interactive is True, or append a suffix if suffix is not empty, or else
	print the relative file name.
	'''
	if suffix and interactive:
		raise ValueError('Only one of --interactive or --suffix may be specified')
	try:
		if os.path.samefile(aname, bname):
			log.error('Different directories must be specified')
	except AttributeError:
		#os.path.samefile does not exist on old versions of python for windows
		pass
	if aname=='' or bname == '' or aname == bname:
		log.error('Two different directories must be specified')
		return 22
	asig = gensig(aname)
	bsig = gensig(bname)

	# Remove duplicate files from directory bname
	adict = dupdict(asig)
	bdict = dupdict(bsig)
	for item in duplicates(adict, bdict):
		asize = int(item[_signatureSize:] )
		for x in adict[item]:
			xl = split_path(x)
			xl.reverse();
			if asize < minsize:
				commonSuffix = len(os.path.split(relpath(x, aname) ) ) - 1
			else:
				commonSuffix = commonsuffix
			for y in bdict[item]:
				suffixmatch = 0
				yl = split_path(y)
				yl.reverse()
				for xi, yi in zip(xl, yl):
					if xi == yi:
						suffixmatch += 1
					else:
						break
				if suffixmatch >= commonSuffix:
					log.debug(x + ' = ' + y)
					os.remove(x)
					break
	
	# Now that all duplicate files have been removed from directory aname,
	# move all remaining files to bname, as long as that will not overwrite
	# an existing file.  If it would, print the conflicting file by default,
	# and use future command-line options to resolve the conflict differently.
	# We can just run the non-searching rmerge algorithm to do that.
	return rmerge(aname, bname, interactive, suffix)


def walkslow(top):
	'''Walk a directory like os.walk, but monitor the directory for changes
	that may be made by the caller after visiting the directory.  This was
	inspired by the posix command "find -depth"
	'''
	# os.walk from python 2.7 was referred to in this implementation
	valid = True
	try:
		names = os.listdir(top)
	except Exception:
		# Can happen if user does not have permission to read the directory
		return
	dirs, nondirs = [], []
	for name in names:
		if os.path.isdir(os.path.join(top, name)):
			dirs.append(name)
		else:
			nondirs.append(name)
	
	for name in dirs:
		new_path = os.path.join(top, name)
		if not os.path.islink(new_path):
			valid = False
			for x in deepwalk(new_path):
				yield x
	
	if not valid:
		names = os.listdir(top)
		dirs, nondirs = [], []
		for name in names:
			if os.path.isdir(os.path.join(top, name)):
				dirs.append(name)
			else:
				nondirs.append(name)
	
	yield top, dirs, nondirs


def relpath(path, start=os.curdir):
	"""Return a relative version of a path"""
	try:
		return os.path.relpath(path, start)
	except AttributeError:
		# The following implementation was mostly copied from python 2.7
		if not path:
			raise ValueError("no path specified")
		start_list = os.path.abspath(start).split(os.path.sep)
		path_list = os.path.abspath(path).split(os.path.sep)
		if start_list[0].lower() != path_list[0].lower():
			unc_path, rest = os.path.splitunc(path)
			unc_start, rest = os.path.splitunc(start)
			if bool(unc_path) ^ bool(unc_start):
				raise ValueError("Cannot mix UNC and non-UNC paths (%s and %s)"
														% (path, start))
			else:
				raise ValueError("path is on drive %s, start on drive %s"
														% (path_list[0], start_list[0]))
		# Work out how much of the filepath is shared by start and path.
		for i in range(min(len(start_list), len(path_list))):
			if start_list[i].lower() != path_list[i].lower():
				break
		else:
			i += 1

		rel_list = [os.pardir] * (len(start_list)-i) + path_list[i:]
		if not rel_list:
			return os.curdir
		return os.path.join(*rel_list)


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
	'''Run the command-line interface of rmerge.'''
	import logging.handlers
	import optparse
	
	if argv == None:
		argv = sys.argv[1:]
	logging.basicConfig()
	# Read options from argument list
	clparser = optparse.OptionParser(usage="usage: %prog [options] SourceDir DestDir",
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
	
	# rmerge-specific options
	clparser.add_option('-i', '--interactive', dest='interactive',
			help='Resolve conflicts interactively', action='store_true')
	clparser.add_option('--min', dest='minsize', metavar='SIZE',
			help='Set minimum size to search for identical files (default 1; 0 means any file size)',
			type='int')
	clparser.add_option('-n', '--nummatch', dest='nummatch',
			help='Set minimum path component matches (default 0)', metavar='NUM', type='int')
	clparser.add_option('-s', '--search', dest='search',
			help='Search for identical files in the destination directory.  If found, discard the source file.',
			action='store_true')
	clparser.add_option('--suffix', dest='suffix', metavar='SUFFIX',
			help='Copy conflicting files to destination directory after appending the specified suffix',
			type='str')

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
	
	if options.usage or len(args) != 2:
		if not options.usage:
			print('Must supply exactly two directories to merge.  See usage below.')
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
	
	kwargs = {}
	if o['nummatch']:  kwargs['commonsuffix'] = o['nummatch']
	if o['interactive']: kwargs['interactive'] = o['interactive']
	if o['suffix']: kwargs['suffix'] = o['suffix']
	if o['minsize'] != None: kwargs['minsize'] = o['minsize']
	
	# Configuration has completed; run the application
	if o['search']:
		smerge(*args, **kwargs)
	else:
		rmerge(*args, **kwargs)
	return 0


if __name__ == '__main__':
	# Suppress a warning about a broken pipe if the output of this script
	# is piped to the input of another program (like less) that exits
	# before reading the entire output
	import signal
	signal.signal(signal.SIGPIPE, signal.SIG_DFL)
	sys.exit(run_cli() )

