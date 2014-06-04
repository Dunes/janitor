#! /bin/bash

# defaults
time_opt="30"
wait_opt=""
log_dir="logs"
error_log_file="unsolved-problems.txt"

args=`getopt Wwt:e:l: $*`
set -- $args
while [ $1 ]
do
	case "$1" in
	-t)
		shift
		time_opt="$1"
		;;
	-e)
		shift
		error_log_file="$1"
		;;
	-l)
		shift
		log_dir="$1"
		;;
	-[Ww])
		wait_opt="$1"
		;;
	--)
		shift
		break
		;;
	*)
		echo "unrecognised option '$1'"
		exit 1
	esac
	shift
done

input="$1"
if [ "$input" == "-" ]
then
	input="/dev/stdin"
fi

error_log="$log_dir/$error_log_file"

while read file_name
do
	echo "starting $file_name"
	./simulator.py "$file_name" -t "$time_opt" "$wait_opt" -l "$log_dir"
	exit_val="$?"
	if [ "$exit_val" -ne 0 ]
	then
		echo "failed to find solution for $file_name"
		echo "$file_name" >> "$error_log"
	fi 
done < "$input"
