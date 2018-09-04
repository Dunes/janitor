(define (problem truck-1)
(:domain Trucks-TimeTIL-Bidding)
(:objects
	truck1 - truck
	boat1 - boat
	package1 package2 - package
	sea-portA - location
	sea-portB - location
	land-nodeB - location
	long-land-route0 long-land-route1 long-land-route2 - location
	area1 - vehiclearea
)

(:init
    (main-agent truck1)
	(at truck1 sea-portB)
	(free area1 truck1)

	; helper agent
	(at boat1 sea-portA)
	(free area1 boat1)
	(can-load boat1 package1)
	(= (used-helper-agent boat1) 0)

	; packages
	(at package1 sea-portA)
	(deliverable package1 land-nodeB)
	; comment out this TIL to see the planner avoid using the boat
	(at 400 (not (deliverable package1 land-nodeB)))
	(at package2 sea-portA)
	(deliverable package2 land-nodeB)

	; edges
	(connected-by-land land-nodeB sea-portB)
	(connected-by-land sea-portB land-nodeB)
	(connected-by-sea sea-portA sea-portB)
	(connected-by-sea sea-portB sea-portA)
	; "the long way round"
	(connected-by-land land-nodeB long-land-route0)
	(connected-by-land long-land-route0 land-nodeB)
	(connected-by-land long-land-route0 long-land-route1)
	(connected-by-land long-land-route1 long-land-route0)
	(connected-by-land long-land-route1 long-land-route2)
	(connected-by-land long-land-route2 long-land-route1)
	(connected-by-land long-land-route2 sea-portA)
	(connected-by-land sea-portA long-land-route2)

	; distances
	(= (travel-time land-nodeB sea-portB) 50)
	(= (travel-time sea-portB land-nodeB) 50)
	(= (travel-time sea-portA sea-portB) 50)
	(= (travel-time sea-portB sea-portA) 50)
	; "the long way round"
	(= (travel-time land-nodeB long-land-route0) 50)
	(= (travel-time long-land-route0 land-nodeB) 50)
	(= (travel-time long-land-route0 long-land-route1) 50)
	(= (travel-time long-land-route1 long-land-route0) 50)
	(= (travel-time long-land-route1 long-land-route2) 50)
	(= (travel-time long-land-route2 long-land-route1) 50)
	(= (travel-time long-land-route2 sea-portA) 50)
	(= (travel-time sea-portA long-land-route2) 50)
)

(:goal (and
	(delivered package1 land-nodeB)
	(delivered package2 land-nodeB)
))

(:metric minimize (+
    (total-time)
    (* (used-helper-agent boat1) 100000)
))

)
