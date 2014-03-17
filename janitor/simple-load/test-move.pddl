(define (problem test-move)
	(:domain janitor)
	(:objects agent1 n1 n2)
	(:init 
		(agent agent1)
		(node n1)
		(node n2)
		
		(edge n1 n2)
		(edge n2 n1)
		
		(= (distance n1 n2) 10)
		(= (distance n2 n1) 10)
		
		(at agent1 n2)
	)
	
	(:goal (and
			(at agent1 n1)
	))
)
