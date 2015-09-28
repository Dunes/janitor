(define (problem roborescue-problem-test)
	(:domain roborescue)
	(:objects
	
		medic1 - medic
		police1 - police
		civ1 civ2 - civilian
		hospital1 - hospital
		building1 - building
	)
				
	(:init
	
		; agents
		(at medic1 hospital1)
		(at police1 hospital1)

		(available medic1)
		(empty medic1)
		
		; civilians
		(at civ1 building1)
		(at civ2 building1)
		
		(alive civ1)
		;(at 200 (not (alive civ1))) ; til
		(buried civ1)
		(= (buriedness civ1) 100)

		(alive civ2)
		;(at 170 (not (alive civ2)))
		(buried civ2)
		(= (buriedness civ2) 100)
	
		; graph	
		(edge hospital1 building1)
		(edge building1 hospital1)
		
		(= (distance hospital1 building1) 50)
		(= (distance building1 hospital1) 50)		
	)
	
	(:goal (and
			(preference rescued-civ1 (rescued civ1))
			(preference rescued-civ2 (rescued civ2))
	))
	
	(:metric minimize (+ 
		(* 1 (total-time))
		(* 1000 (is-violated rescued-civ1))
		(* 1000 (is-violated rescued-civ2))
	))
)
