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
		:parameters (?a1 - agent ?a2 - agent ?rm - room)
		:duration (= ?duration (dirtiness ?rm))
		:condition (and
		    (at start (extra-dirty ?rm))
			(at start (not (= ?a1 ?a2)))
			(at start (available ?a1))
			(at start (available ?a2))
			(over all (at ?a1 ?rm))
			(over all (at ?a2 ?rm))
		)
		:effect (and
		    (at start (not (extra-dirty ?rm)))
			(at end (cleaned ?rm))
			(at start (not (available ?a1)))
			(at start (not (available ?a2)))
			(at end (available ?a1))
			(at end (available ?a1))
		)
	)	
	
)
