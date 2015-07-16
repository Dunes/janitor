(define (domain roborescue)
	(:requirements :strips :fluents :durative-actions :timed-initial-literals :adl :equality :typing)
    (:types agent - object
            ambulance police - agent
    )
	(:predicates
		
		(successful ?a - agent)


	)
	
	(:functions
	)

	(:action police-success
		:parameters (?a - police)
		:precondition ()
		:effect (successful ?a)
	)
	(:action ambulance-success
		:parameters (?a - ambulance)
		:precondition ()
		:effect (successful ?a)
	)

)
