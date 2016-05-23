#!/bin/bash

dir="problems/roborescue/quantitative/auto"
mkdir -p $dir

domain="roborescue"



edge_length="120"
buriedness="120,120"
blockedness="300,300"
blocked_percentage="0.50"

for a in `seq 2 2 10`
do
    police=$a
    medics=$a
    for i in `seq 4 20`
    do
	    size="$i,$i"
	    let civilians=i*i/4
	    hospitals="0,0 $((i-1)),$((i-1))"
	    
	    # without deaths
	    name="blocked-with-deaths-size($size)-agents($a).json"
	    problem_name="auto-blocked-with-deaths"
	    
	    python3 src/problem_creator.py --output="$dir/$name" \
		    --problem-name "$problem_name" --domain "$domain" \
		    --size $size --buriedness $buriedness --blockedness $blockedness \
		    --blocked-percentage $blocked_percentage --edge-length $edge_length \
		    --civilians $civilians --medics $medics --police $police \
		    --hospitals $hospitals

        # with deaths
	    #name="blocked-with-deaths-size($size).json"
	    #problem_name="auto-blocked-with-deaths"
	    #
	    #python3 src/problem_creator.py --output="$dir/$name" \
		#    --problem-name "$problem_name" --domain "$domain" \
		#    --size $size --buriedness $buriedness --blockedness $blockedness \
		#    --blocked-percentage $blocked_percentage --edge-length $edge_length \
		#    --civilians $civilians --medics $medics --police $police \
		#    --hospitals $hospitals --max-survival=?
    done
done
