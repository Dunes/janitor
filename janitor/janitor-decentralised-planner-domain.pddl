(define (domain janitor)
	(:requirements :strips :fluents :durative-actions :timed-initial-literals :adl :equality :typing :action-costs :preferences)

	(:types
		agent - object
		node - object
		room - node
	)

	(:predicates
		(available ?a - agent)
		(at ?a - agent ?n - node)
		(edge ?n1 - node ?n2 - node)
		(dirty ?rm - room)
		(extra-dirty ?rm - room)
		(cleaned ?rm - room) ; clean is a keyword
		(cleaning-assist ?rm - room)
		(can-finish ?rm - room) ; planning conditions to assist with coordination
		(can-start ?rm - room)  ; planning conditions to assist with coordination
		(cleaning-assisted ?rm - room)
	)
	
	(:functions
		(distance ?n1 - node ?n2 - node)
		(dirtiness ?rm - room)
	)

	(:durative-action move
		:parameters (?a -agent ?n1 - node ?n2 - node)
		:duration (= ?duration (distance ?n1 ?n2))
		:condition (and
		    (at start (at ?a ?n1))
			(at start (edge ?n1 ?n2))
		)
		:effect (and
		    (at start (not (at ?a ?n1)))
			(at end (at ?a ?n2))
		)
	)
	
	(:durative-action clean
		:parameters (?a - agent ?rm - room)
		:duration (= ?duration (dirtiness ?rm))
		:condition (and
		    (at start (dirty ?rm))
		    (at start (available ?a))
			(over all (at ?a ?rm))
		)
		:effect (and
		    (at start (not (dirty ?rm)))
			(at start (not (available ?a)))
			(at end (cleaned ?rm))
			(at end (available ?a))
		)
	)
	
	(:durative-action extra-clean
		:parameters (?a - agent ?rm - room)
		:duration (= ?duration (dirtiness ?rm))
		:condition (and
		    (at start (extra-dirty ?rm))
			(at start (available ?a))
			(over all (cleaning-assist ?rm))
			(at start (can-start ?rm)) ; planning conditions to assist with coordination
			(at end (can-finish ?rm))  ;
			(over all (at ?a ?rm))
		)
		:effect (and
		    (at start (not (extra-dirty ?rm)))
			(at end (cleaned ?rm))
			(at start (not (available ?a)))
			(at end (available ?a))
		)
	)

	(:durative-action extra-clean-assist
		:parameters (?a - agent ?rm - room)
		:duration (= ?duration (+ 0.001 (dirtiness ?rm)))
		:condition (and
		    (at start (extra-dirty ?rm))
			(at start (available ?a))
			(at start (can-start ?rm)) ; planning conditions to assist with coordination
			(at end (can-finish ?rm))  ;
			(over all (at ?a ?rm))
		)
		:effect (and
			(at start (cleaning-assist ?rm))
			(at start (cleaning-assisted ?rm))
			(at end (not (cleaning-assist ?rm)))
			(at start (not (available ?a)))
			(at end (available ?a))
		)
	)
	
)
