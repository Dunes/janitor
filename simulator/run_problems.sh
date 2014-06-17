#! /bin/bash


function usage {
	echo "Usage: run_problems.sh [OPTION]... FILE"
	echo "Run the problems listed in FILE (one per line)."
	echo "Records output of problems into a log directory. One file per problem."
	echo "Separately records all plans produced by a problem in sub dir of the logging" 
	echo "  directory called \`plans'"
	echo "Record problems where a solution was not found (failed runs) to a log file."
	echo "When FILE is -, read standard input."
	echo ""
	echo "  -t TIME            Run problems with a planning time of TIME. (default 30)"
	echo "  -e ERROR_OUTPUT    The file to record failed problems to. "
	echo "                       (default \`unsolved-problems.txt')"
	echo "  -l LOG_DIR         The logging directory to log output and failed runs to."
	echo "                       (default \`logs')"
	echo "  -h                 Print this usage instructions."

	exit 1
}

# defaults
time_opt="30"
log_dir="logs"
error_log_file="unsolved-problems.txt"

args=`getopt -q t:e:l: $*`
if [[ $? -ne 0 ]]
then
	usage
fi
set -- $args
while [[ $1 ]]
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
	--)
		shift
		break
		;;
	*)
		echo "unrecognised option \`$1'"
		usage
	esac
	shift
done

input="$1"
if [[ ! "$input" ]]
then
	usage
elif [[ "$input" == "-" ]]
then
	input="/dev/stdin"
fi

error_log="$log_dir/$error_log_file"

while read file_name
do
	echo "starting $file_name"
	./simulator.py "$file_name" -t "$time_opt" -l "$log_dir"
	exit_val="$?"
	if [ "$exit_val" -ne 0 ]
	then
		echo "failed to find solution for $file_name"
		echo "$file_name" >> "$error_log"
	fi 
done < "$input"
