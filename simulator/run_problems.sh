#! /bin/bash


function usage {
	echo "Usage: run_problems.sh [OPTION]... [FILE]"
	echo "Run the problems listed in FILE (one per line)."
	echo "Records output of problems into a log directory. One file per problem."
	echo "Separately records all plans produced by a problem in sub dir of the logging"
	echo "  directory called \`plans'"
	echo "Record problems where a solution was not found (failed runs) to a log file."
	echo "When FILE is -, read standard input."
	echo ""
	echo "  -t TIME            Run problems with a planning time of TIME. (default 10)"
	echo "  -q HEURISTIC       Run problems with a heuristic planning time of HEURISTIC"
	echo "  -d PROBLEM_DIR     Use directory as problem source rather than FILE"
	echo "  -e ERROR_OUTPUT    The file to record failed problems to. "
	echo "                       (default \`unsolved-problems.txt')"
	echo "  -l LOG_DIR         The logging directory to log output and failed runs to."
	echo "                       (default \`logs')"
	echo "  -s SIMULATOR       The simulator arg to pass to main.sh"
	echo "  -x                 Shutdown the computer when done. Useful for auto-stopping"
	echo "                       AWS instances. requires password-less sudo. (default"
	echo "                       behaviour is to no do this)"
	echo "  -h                 Print this usage instructions."

	exit 1
}

# defaults
time_opt="10"
heuristic_opt="1"
log_dir="logs"
error_log_file="unsolved-problems.txt"
SHUTDOWN=nope

args=`getopt t:e:l:d:q:s:x $*`
if [[ $? -ne 0 ]]
then
	usage
fi
set -- ${args}
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
	-d)
		shift
		problem_dir="$1"
		;;
	-q)
		shift
		heuristic_opt="$1"
		;;
	-s)
	    shift
	    simulator="$1"
	    ;;
	-x)
	    SHUTDOWN=shutdown
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
if [[ "$input" && "$problem_dir" ]] || [[ ! "$input" && ! "$problem_dir" ]]
then
	usage
elif [[ "$input" == "-" ]]
then
	input="/dev/stdin"
fi

error_log="$log_dir/$error_log_file"

function process_file {
    file_name="$1"
	base_file_name="`basename ${file_name}`"
	echo "starting $file_name"
	./main.sh "$file_name" -t "$time_opt" -q "$heuristic_opt" -l "$log_dir" -s "$simulator" 2>&1 | tee "$log_dir/output/$base_file_name"
	exit_val="${PIPESTATUS[0]}"
	if [[ "$exit_val" != 0 ]]
	then
		echo "failed to find solution for $base_file_name"
		echo "$base_file_name" >> "$error_log"
	fi
}

mkdir "$log_dir/output" -p
if [[ "$input" ]]
then
	while read file_name
	do
		process_file "$file_name"
	done < "$input"
else
	for file_name in "$problem_dir"/*
	do
		process_file "$file_name"
	done
fi


if [ ${SHUTDOWN} = shutdown ]
then
    sudo shutdown now
fi