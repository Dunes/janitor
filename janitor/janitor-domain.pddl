(define (domain janitor)
	(:requirements :strips :fluents :durative-actions :conditional-effects :adl :equality)

	(:predicates
		
		(node ?n)
		(edge ?n1 ?n2)
		(is-room ?n)
		(is-resource-room ?n)
		
		(agent ?a)
		(at ?a ?n)
		(has-stock ?a) ; if agent has stock
		(available ?a)
		
		(under-stocked ?rm)
		(fully-stocked ?rm)
		(dirty ?rm)
		(extra-dirty ?rm)
		(not-extra-dirty ?rm)
		(cleaned ?rm) ; clean is a keyword
		
		
	)
	
	(:functions
		(distance ?n1 ?n2)
		(dirtiness ?rm)
		(max-dirt ?rm)
		(req-stock ?rm)
		
		(max-carry ?a)
		(carrying ?a)
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
						(at start (not-extra-dirty ?rm)))
		:effect (and (at start (not (dirty ?rm)))
						(at start (not (available ?a)))
						(at end (cleaned ?rm))
						(at end (assign (dirtiness ?rm) 0))
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
						
						(at end (assign (dirtiness ?rm) 0))
						(at end (available ?a1))
						(at end (available ?a1))
						)
	)

	(:durative-action load
		:parameters (?a ?rm)
		:duration (= ?duration 1)
		:condition (and (over all (at ?a ?rm))
						(at start (agent ?a))
						(at start (is-resource-room ?rm)))
		:effect (and (at start (has-stock ?a))
					(at start (assign (carrying ?a) (max-carry ?a)))
					)
	)

	(:durative-action full-stock-unload
		:parameters (?a ?rm)
		:duration (= ?duration 1)
		:condition (and (over all (at ?a ?rm))
						(at start (has-stock ?a))
						(at start (under-stocked ?rm))
						(at start (agent ?a))
						(at start (available ?a))
						(at start (is-room ?rm))
						(at start (<= (req-stock ?rm) (carrying ?a)))
						)
		:effect (and
					(at start (fully-stocked ?rm))
					(at start (not (under-stocked ?rm)))
					(at start (assign (carrying ?a) (- (carrying ?a) (req-stock ?rm))))
					(at start (assign (req-stock ?rm) 0))
					(at start (not (available ?a)))
					(at end (available ?a))
					)
	)

	(:durative-action partial-stock-unload
		:parameters (?a ?rm)
		:duration (= ?duration 1)
		:condition (and (over all (at ?a ?rm))
						(at start (has-stock ?a))
						(at start (under-stocked ?rm))
						(at start (agent ?a))
						(at start (available ?a))
						(at start (is-room ?rm))
						(at start (> (req-stock ?rm) (carrying ?a)))
						)
		:effect (and
					(at start (assign (req-stock ?rm) (- (req-stock ?rm) (carrying ?a))))
					(at start (assign (carrying ?a) 0))
					(at start (not (available ?a)))
					(at end (available ?a))
					)
	)	
	
)
