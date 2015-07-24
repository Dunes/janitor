(define (domain roborescue)
	(:requirements :strips :fluents :durative-actions :timed-initial-literals :adl :equality :typing :action-costs)
	(:types
		moveable - object
		agent civilian - moveable
		police medic - agent
		node - object
		building hospital - node
	)
	
	(:predicates
		
		(at ?m - moveable ?n - node)
		(carrying ?m - medic ?c - civilian)
		(empty ?m - medic)
		
		(edge ?n1 ?n2 - node)
		(blocked-edge ?n1 ?n2 - node)
		
		(buried ?c - civilian)
		(unburied ?c - civilian)
		
		(rescued ?c - civilian)
		(collected-reward ?c - civilian)
		(started)

	)
	
	(:functions
	    (total-reward)
	    
		(life ?c - civilian)
		(buriedness ?c - civilian)
		(blockedness ?n1 ?n2 - node)
		(distance ?n1 ?n2 - node)
	)
	
	(:process civilian-life-drain
        :parameters (?c - civilian)
        :precondition (started)
        :effect (increase (life ?c) (* #t 1))
    )
    
    (:durative-action collect-reward
        :parameters (?c - civilian)
        :duration (= ?duration 0)
        :condition (and
            (at start (rescued ?c))
        )
        :effect (and
            (at start (increase (total-reward) 10))
            (at start (not (rescued ?c)))
            (at start (collected-reward ?c))
        )
    )

	(:durative-action move
		:parameters (?a - agent ?n1 - node ?n2 - node)
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

	(:durative-action unblock
		:parameters (?a - police ?n1 - node ?n2 - node)
		:duration (= ?duration (blockedness ?n1 ?n2))
		:condition (and 
			(over all (at ?a ?n1))
			(at start (blocked-edge ?n1 ?n2))
		)
		:effect (and 
			(at start (not (blocked-edge ?n1 ?n2)))
			(at start (not (blocked-edge ?n2 ?n1)))
			(at end (edge ?n1 ?n2))
			(at end (edge ?n2 ?n1))
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
		:parameters (?m - medic ?c - civilian ?b - hospital)
		:duration (= ?duration 1)
		:condition (and 
			(over all (at ?m ?b))
			(at start (carrying ?m ?c))
		)
		:effect (and
			(at start (not (carrying ?m ?c)))
			(at end (at ?c ?b))
			(at end (empty ?m))
			(at end (rescued ?c))
		)
	)

	(:durative-action rescue
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
