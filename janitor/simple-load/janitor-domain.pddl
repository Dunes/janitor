(define (domain janitor)
	(:requirements :strips :fluents :durative-actions :conditional-effects :adl)

	(:predicates
		
		(node ?n)
		(edge ?n1 ?n2)
		(is-room ?n)
		(is-resource-room ?n)
		
		(agent ?a)
		(at ?a ?n)
		(has-stock ?a) ; if agent has stock
		
		(under-stocked ?rm)
		(fully-stocked ?rm)
		(dirty ?rm)
		(cleaned ?rm) ; clean is a keyword
	)
	
	(:functions
		(distance ?n1 ?n2)
		(dirtiness ?rm)
		(max-dirt ?rm)
	)

	(:durative-action move
		:parameters (?a ?n1 ?n2)
		:duration (= ?duration (distance ?n1 ?n2))
		:condition (and (at start (at ?a ?n1))
						(at start (edge ?n1 ?n2))
						(at start (node ?n1))
						(at start (node ?n2))
						(at start (agent ?a)))
		:effect (and (at start (not (at ?a ?n1)))
						(at end (at ?a ?n2)))
	)
	
	(:durative-action clean
		:parameters (?a ?rm)
		:duration (= ?duration (dirtiness ?rm))
		:condition (and (at start (dirty ?rm))
						(over all (at ?a ?rm))
						(at start (agent ?a))
						(at start (is-room ?rm)))
		:effect (and (at start (not (dirty ?rm)))
						(at end (cleaned ?rm))
						(at end (assign (dirtiness ?rm) 0)))
	)

	(:durative-action load
		:parameters (?a ?rm)
		:duration (= ?duration 1)
		:condition (and (over all (at ?a ?rm))
						(at start (agent ?a))
						(at start (is-resource-room ?rm)))
		:effect (and (at start (has-stock ?a)))
	)

	(:durative-action unload
		:parameters (?a ?rm)
		:duration (= ?duration 1)
		:condition (and (over all (at ?a ?rm))
						(at start (has-stock ?a))
						(at start (under-stocked ?rm))
						(at start (agent ?a))
						(at start (is-room ?rm)))
		:effect (and
					(at start (fully-stocked ?rm))
					(at start (not (under-stocked ?rm)))
					(at start (not (has-stock ?a))))
	)
)
