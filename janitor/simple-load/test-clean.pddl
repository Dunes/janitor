(define (problem test-move)
	(:domain janitor)
	(:objects agent1 n1 n2 rm1 rm2)
	(:init 
		(agent agent1)
		(node n1)
		(node n2)
		(node rm1) (is-room rm1)
		(node rm2) (is-room rm2)
		
		(edge n1 n2)
		(edge n2 n1)
		(edge n1 rm1)
		(edge rm1 n1)
		(edge n2 rm2)
		(edge rm2 n2)
		
		(= (distance n1 n2) 10)
		(= (distance n2 n1) 10)
		(= (distance n1 rm1) 1)
		(= (distance rm1 n1) 1)
		(= (distance n2 rm2) 1)
		(= (distance rm2 n2) 1)
		
		(dirty rm1)
		(= (dirtiness rm1) 5)
		(dirty rm2)
		(= (dirtiness rm2) 3)
		
		(at agent1 n1)
	)
	
	(:goal (and
			(cleaned rm1)
			(cleaned rm2)
	))
)
