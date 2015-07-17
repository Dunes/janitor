(define (problem roborescue-problem)
	(:domain roborescue)
	(:objects
	
		medic1 - medic
		police1 - police
		civ1 - civilian
		start - building
		finish - building
	)
				
	(:init
	
		(at medic1 start)
		(at police1 start)
		(at civ1 finish)
		;(at civ2 finish)
		
		(empty medic1)
		(buried civ1)
		
		(= (buriedness civ1) 7)
		
		(edge start finish)
		(edge finish start)
		
		(= (distance start finish) 10)
		(= (distance finish start) 10)
		
		(blocked start finish)
		(blocked finish start)
		
		(= (blockedness start finish) 5)
		(= (blockedness finish start) 5)
		
	)
	
	(:goal (and
		(at civ1 start)
		;(at civ2 start)
	))
)
