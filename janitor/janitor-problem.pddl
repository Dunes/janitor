(define (problem janitor-problem)
	(:domain janitor)
	(:objects
	    agent1 - agent
	    agent2 - agent
	    n1 - node
	    rm1 - room
	    rm-ed1 - room
	)
	(:init
	    ; agents
		(available agent1)
		(at agent1 n1)

		(available agent2)
		(at agent2 n1)

        ; rooms
		(extra-dirty rm-ed1)
		(= (dirtiness rm-ed1) 5)
		(dirty rm1)
		(= (dirtiness rm1) 5)

	    ; graph
		(edge n1 rm1)
		(edge n1 rm-ed1)
		(edge rm1 n1)
		(edge rm-ed1 n1)
		
		(= (distance n1 rm1) 10)
		(= (distance n1 rm-ed1) 10)
		(= (distance rm1 n1) 10)
		(= (distance rm-ed1 n1) 10)
	)
	
	(:goal (and
		(cleaned rm1)
		(cleaned rm-ed1)
	))
)
