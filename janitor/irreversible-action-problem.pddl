(define (problem janitor-problem)
	(:domain janitor)
	(:objects agent1 agent2 n1 rm1 rm2 rm-ed1 rm-ed2)
	(:init 
		(agent agent1)
		(agent agent2)
		(node n1)
		(node rm1)
		(node rm2)
		(node rm-ed1)
		(node rm-ed2)
		
		(edge n1 rm1)
		(edge rm1 n1)
		(edge rm1 rm2)
		(edge rm2 rm1)
		(edge rm2 rm-ed1)
		(edge rm-ed1 rm-ed1)
		(edge rm-ed1 rm-ed2)
		(edge rm-ed2 rm-ed1)
		
		(= (distance n1 rm1) 10)
		(= (distance rm1 n1) 10)
		(= (distance rm1 rm2) 10)
		(= (distance rm2 rm1) 10)
		(= (distance rm2 rm-ed1) 10)
		(= (distance rm-ed1 rm2) 10)
		(= (distance rm-ed1 rm-ed2) 10)
		(= (distance rm-ed2 rm-ed1) 10)

		(dirty rm1)
		(= (dirtiness rm1) 5)
		(occupied rm1)
		(completed rm1) ; comment out to make problem unsolveable
		
		(dirty rm2)
		(= (dirtiness rm2) 5)
		(unoccupied rm2)
		
		(extra-dirty rm-ed1)
		(= (dirtiness rm-ed1) 5)
		(occupied rm-ed1)
		(completed rm-ed1) ; comment out to make problem unsolveable
		
		(extra-dirty rm-ed2)
		(= (dirtiness rm-ed2) 5)
		(unoccupied rm-ed2)
		
		(available agent1)
		(at agent1 n1)
		(available agent2)
		(at agent2 n1)
	)
	
	(:goal (and
			(completed rm1)
			(completed rm2)
			(completed rm-ed1)
			(completed rm-ed2)
	))
)
