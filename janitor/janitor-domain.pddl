(define (domain janitor)
	(:requirements :strips :fluents :durative-actions :conditional-effects :adl :equality)

	(:predicates
		
		(node ?n)
		(edge ?n1 ?n2)
		(is-room ?n)
		
		(agent ?a)
		(at ?a ?n)
		(available ?a)
		
		(dirty ?rm)
		(extra-dirty ?rm)
		(cleaned ?rm) ; clean is a keyword
		
		
	)
	
	(:functions
		(distance ?n1 ?n2)
		(dirtiness ?rm)
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
						(at start (available ?a))
						(at start (is-room ?rm))
						)
		:effect (and (at start (not (dirty ?rm)))
						(at start (not (available ?a)))
						(at end (cleaned ?rm))
						# (at end (assign (dirtiness ?rm) 0))
						(at end (available ?a))
						)
	)
	
	(:durative-action extra-clean
		:parameters (?a1 ?a2 ?rm)
		:duration (= ?duration (dirtiness ?rm))
		:condition (and (at start (extra-dirty ?rm))
						(at start (not (= ?a1 ?a2)))
						(over all (at ?a1 ?rm))
						(over all (at ?a2 ?rm))
						(at start (agent ?a1))
						(at start (agent ?a2))
						(at start (available ?a1))
						(at start (available ?a2))
						(at start (is-room ?rm))
						)
		:effect (and (at start (not (extra-dirty ?rm)))
						(at end (cleaned ?rm))
						(at start (not (available ?a1)))
						(at start (not (available ?a2)))
						
						# (at end (assign (dirtiness ?rm) 0))
						(at end (available ?a1))
						(at end (available ?a1))
						)
	)	
	
)
