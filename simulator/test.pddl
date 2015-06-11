(define (problem problem-name) (:domain janitor)
(:objects  agent2 rm2 rm3 rm1)
(:init 
    (at agent2 rm2 ) (available agent2 ) (agent agent2 ) 
    
    (extra-dirty rm2 ) (node rm2 ) (is-room rm2 ) (= (dirtiness rm2 ) 10) 
    (dirty rm3 ) (node rm3 ) (is-room rm3 ) (= (dirtiness rm3 ) 10) 
    (cleaned rm1 ) (node rm1 ) (is-room rm1 ) 
    
    (at 10 (cleaning-window rm2 )  ) (at 21.5 (not (cleaning-window rm2 )  )  ) 
    
    (edge rm1 rm2 ) (= (distance rm1 rm2 ) 10) 
    (edge rm1 rm3 ) (= (distance rm1 rm3 ) 10) 
    (edge rm2 rm1 ) (= (distance rm2 rm1 ) 10) 
    (edge rm2 rm3 ) (= (distance rm2 rm3 ) 10) 
    (edge rm3 rm1 ) (= (distance rm3 rm1 ) 10) 
    (edge rm3 rm2 ) (= (distance rm3 rm2 ) 10) ) 

(:goal (and (cleaned rm2 ) ))
)
