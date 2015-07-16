(define (problem roborescue-problem)
	(:domain roborescue)
	(:objects agent1 - ambulance
	            agent2 - police)
	(:init
	)
	
	(:goal (and
			(successful agent1)
			(successful agent2)
	))
)
