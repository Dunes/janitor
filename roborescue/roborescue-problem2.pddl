(define (problem roborescue-problem)
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
		(= (buriedness civ1) 50)

		(alive civ2)
		(at 170 (not (alive civ2)))
		(buried civ2)
		(= (buriedness civ2) 50)
	
		; graph	
		(blocked-edge hospital1 building1)
		(blocked-edge building1 hospital1)
		
		(= (distance hospital1 building1) 50)
		(= (distance building1 hospital1) 50)

		(= (blockedness hospital1 building1) 10)
		(= (blockedness building1 hospital1) 10)
		
		
	)
	
	(:goal (and
			(preference r1 (rescued civ1))
			(preference r2 (rescued civ2))
	))
	
	(:metric minimize (+ 
		(total-time)
		(* 1000 (is-violated r1))
		(* 1000 (is-violated r2))
	))
)
