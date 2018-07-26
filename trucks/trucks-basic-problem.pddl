(define (problem truck-1)
(:domain Trucks-TimeTIL)
(:objects
	truck1 - truck
	boat1 - boat
	package1 - package
	package2 - package
	l1 - location
	l2 - location
	l3 - location
	a1 - vehiclearea
	a2 - vehiclearea
)

(:init
	(at truck1 l2)
	(free a1 truck1)
	(free a2 truck1)
	(at boat1 l2)
	(free a1 boat1)
	(free a2 boat1)
	(closer a1 a2)
	(at package1 l1)
	(at package2 l2)
	(connected-by-land l1 l2)
	(connected-by-land l2 l1)
	(connected-by-sea l2 l3)
	(connected-by-sea l3 l2)
	(deliverable package1 l3)
	(deliverable package2 l3)
	; (at 500 (not (deliverable package2 l3))) ; (un)comment to change whether package2 to is greedily delivered
	(= (travel-time l1 l2) 300)
	(= (travel-time l2 l1) 300)
	(= (travel-time l2 l3) 400)
	(= (travel-time l3 l2) 400)
)

(:goal (and
	(delivered package1 l3)
	(delivered package2 l3)
))

(:metric minimize (total-time))

)
