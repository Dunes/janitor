(define (domain roborescue)
	(:requirements :strips :fluents :durative-actions :timed-initial-literals :adl :equality :typing)
	(:types
		moveable - object
		agent civilian - moveable
		police medic - agent
		node - object
		building - node
	)
	
	(:predicates
		
		(at ?m - moveable ?n - node)
		(carrying ?m - medic ?c - civilian)
		(empty ?m - medic)
		
		(edge ?n1 ?n2 - node)
		(blocked ?n1 ?n2 - node)
		(unblocked ?n1 ?n2 - node)
		
		(buried ?c - civilian)
		(unburied ?c - civilian)
		;(alive ?c - civilian)
		;(dead ?c - civilian)
		

	)
	
	(:functions
		;(life ?c - civilian)
		(buriedness ?c - civilian)
		(blockedness ?n1 ?n2 - node)
		(distance ?n1 ?n2 - node)
	)

	(:durative-action move
		:parameters (?a - agent ?n1 - node ?n2 - node)
		:duration (= ?duration (distance ?n1 ?n2))
		:condition (and 
			(at start (at ?a ?n1))
			(at start (edge ?n1 ?n2))
			(at start (unblocked ?n1 ?n2))
		)
		:effect (and 
			(at start (not (at ?a ?n1)))
			(at end (at ?a ?n2))
		)
	)

	(:durative-action unblock
		:parameters (?a - police ?n1 - node ?n2 - node)
		:duration (= ?duration (blockedness ?n1 ?n2))
		:condition (and 
			(over all (at ?a ?n1))
			(at start (edge ?n1 ?n2))
			(at start (blocked ?n1 ?n2))
		)
		:effect (and 
			(at end (not (blocked ?n1 ?n2)))
			(at end (not (blocked ?n2 ?n1)))
			(at end (unblocked ?n1 ?n2))
			(at end (unblocked ?n2 ?n1))
		)
	)

	(:durative-action load
		:parameters (?m - medic ?c - civilian ?b - building)
		:duration (= ?duration 1)
		:condition (and 
			(over all (at ?m ?b))
			(at start (at ?c ?b))
			(at start (empty ?m))
			(at start (unburied ?c))
		)
		:effect (and 
			(at start (not (at ?c ?b)))
			(at start (not (empty ?m)))
			(at end (carrying ?m ?c))
		)
	)
	
	(:durative-action unload
		:parameters (?m - medic ?c - civilian ?b - building)
		:duration (= ?duration 1)
		:condition (and 
			(over all (at ?m ?b))
			(at start (carrying ?m ?c))
		)
		:effect (and
			(at start (not (carrying ?m ?c)))
			(at end (at ?c ?b))
			(at end (empty ?m))
		)
	)

	(:durative-action clear
		:parameters (?m - medic ?c - civilian ?b - building)
		:duration (= ?duration (buriedness ?c))
		:condition (and 
			(over all (at ?m ?b))
			(at start (at ?c ?b))
			(at start (buried ?c))
		)
		:effect (and
			(at start (not (buried ?c)))
			(at end (unburied ?c))
		)
	)

)
