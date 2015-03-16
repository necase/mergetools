#!/bin/sh
# rmerge: recursively merge the files from two similar directory structures
# usage: rmerge [-i] dir1 dir2
# Compares files within dir1 to files of the same name in dir2
# If the file does not exist in dir2, copy it to dir2
# Print conflicting files to stdout
# Give the option to resolve conflicts by showing the diff and deciding immediately when invoked with -i
# If there are empty subdirectories, remove them
# If the files are the same, remove from dir1

# Related commands are:
# diff -rq "$SRC" "$DEST"
# cd "$SRC" && find . -type f -exec diff {} "$DEST/{}" ";"
# cp -n -r -l "$SRC/*" "$DEST"

while getopts "i" opt; do
	case "$opt" in
		i ) INTERACTIVE=1
				;;
		\? ) return 22 # 22 is EINVAL on at least one system
				 ;;
		: ) return 22
				;;
	esac
done
shift `expr $OPTIND - 1`

SRC="$1"
DEST="$2"

if [ -z "$SRC" ] || [ -z "$DEST" ]; then
	echo "Both the source and destination directories must be specified"
	return 22
fi

# if $SRC has a leading dash, $SRC may be confused with a parameter to some program
SRC=`echo "$SRC" | sed -e 's@^\-@./\-@' `


export SRC
export DEST
export INTERACTIVE

# To escape a single quote within a single-quoted string,
# replace each occurrence of  '  with  '\''
# Then nothing else needs to be escaped further.
find "$SRC" -type f -exec sh -c '
	for fullfile in "$@" ; do
		escsrc=`echo "$SRC" | sed -e '\''s@[]/$*.^+|[-]@\\&@g'\'' -`
		file=`echo "$fullfile" | sed -e '\"'s/$escsrc\/\{0,1\}//'\"' -`
		printFilename=`printf '\''%s'\'' "$file" | LC_ALL=POSIX tr -d '\''[:cntrl:]'\'' `
		if [ -e "$DEST/$file" ]; then
			cmp -s "$SRC/$file" "$DEST/$file"
			ret="$?"
			if [ "$ret" = "1" ]; then
				if [ "$INTERACTIVE" = "1" ]; then
					echo
					echo Conflict found: "$printFilename"
					diff -u "$SRC/$file" "$DEST/$file"
					echo
					echo -n "Which file would you like to keep? (-+o): "
					read answer
					case "$answer" in
						- ) mv "$SRC/$file" "$DEST/$file" ;;
						+ ) rm -f "$SRC/$file" ;;
						* ) echo "Skipping file $file" ;;
					esac
				fi
			elif [ "$ret" = "0" ]; then
				rm -f "$SRC/$file"
			else
				echo "ERROR: rmerge encountered problem $ret with $printFilename"
			fi
		else
			mkdir -p "`dirname "$DEST/$file"`"
			mv "$SRC/$file" "$DEST/$file"
		fi
	done
' sh {} '+'

# Delete all empty directories contained within "$SRC"
find "$SRC" -depth -type d -empty -exec sh -c '
	for file in "$@" ; do
		if [ -e "$file" ] && [ "$file" != "$SRC" ]; then
			rm -r "$file"
		fi
	done
' sh {} '+'

