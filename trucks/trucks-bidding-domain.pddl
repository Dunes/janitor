(define (domain trucks-bidding)
(:requirements :typing :adl :durative-actions :fluents :timed-initial-literals)

(:types
    vehiclearea location locatable - object
    vehicle package - locatable
    truck boat - vehicle
)

(:predicates
    (at ?x - locatable ?l - location)
    (in ?p - package ?v - vehicle ?a - vehiclearea)
    (connected-by-land ?x ?y - location)
    (connected-by-sea ?x ?y - location)
    (free ?a - vehiclearea ?v - vehicle)
    (delivered ?p - package ?l - location)
    (at-destination ?p - package ?l - location)
    (closer ?a1 - vehiclearea ?a2 - vehiclearea)
    (deliverable ?p - package ?l - location)

    (main-agent ?v - vehicle)
    (can-load ?v - vehicle ?p - package)

)

(:functions
    (travel-time ?from ?to - location)
    (used-helper-agent ?v - vehicle)
)


;;;;;;;;;;;;;;;;;;;;
;; COMMON ACTIONS ;;
;;;;;;;;;;;;;;;;;;;;

(:durative-action drive
    :parameters (?t - truck ?from ?to - location)
    :duration (= ?duration (travel-time ?from ?to))
    :condition (and
        (at start (at ?t ?from))
        (over all (connected-by-land ?from ?to))
    )
    :effect (and
        (at start (not (at ?t ?from)))
        (at end (at ?t ?to))
    )
)

(:durative-action sail
    :parameters (?b - boat ?from ?to - location)
    :duration (= ?duration (travel-time ?from ?to))
    :condition (and
        (at start (at ?b ?from))
        (over all (connected-by-sea ?from ?to))
    )
    :effect (and
        (at start (not (at ?b ?from)))
        (at end (at ?b ?to))
    )
)

(:durative-action unload
    :parameters (?p - package ?v - vehicle ?a1 - vehiclearea ?l - location)
    :duration (= ?duration 1)
    :condition (and
        (at start (in ?p ?v ?a1))
        (at start
            (forall (?a2 - vehiclearea)
                (imply (closer ?a2 ?a1) (free ?a2 ?v))
            )
        )
        (over all (at ?v ?l))
        (over all
            (forall (?a2 - vehiclearea)
                (imply (closer ?a2 ?a1) (free ?a2 ?v))
            )
        )
    )
    :effect (and
        (at start (not (in ?p ?v ?a1)))
        (at end (free ?a1 ?v))
        (at end (at ?p ?l))
    )
)


;;;;;;;;;;;;;;;;;;;;;;;;
;; MAIN AGENT ACTIONS ;;
;;;;;;;;;;;;;;;;;;;;;;;;

(:durative-action load
    :parameters (?p - package ?v - vehicle ?a1 - vehiclearea ?l - location)
    :duration (= ?duration 1)
    :condition (and
        (at start (main-agent ?v))
        (at start (at ?p ?l))
        (at start (free ?a1 ?v))
        (at start
            (forall (?a2 - vehiclearea)
                (imply (closer ?a2 ?a1) (free ?a2 ?v))
            )
        )
        (over all (at ?v ?l))
        (over all
            (forall (?a2 - vehiclearea)
                (imply (closer ?a2 ?a1) (free ?a2 ?v))
            )
        )
    )
    :effect (and
        (at start (not (at ?p ?l)))
        (at start (not (free ?a1 ?v)))
        (at end (in ?p ?v ?a1))
    )
)


;;;;;;;;;;;;;;;;;;;;;;;;;;
;; HELPER AGENT ACTIONS ;;
;;;;;;;;;;;;;;;;;;;;;;;;;;

(:durative-action helper-load
    :parameters (?p - package ?v - vehicle ?a1 - vehiclearea ?l - location)
    :duration (= ?duration 1)
    :condition (and
        (at start (can-load ?v ?p))
        (at start (at ?p ?l))
        (at start (free ?a1 ?v))
        (at start
            (forall (?a2 - vehiclearea)
                (imply (closer ?a2 ?a1) (free ?a2 ?v))
            )
        )
        (over all (at ?v ?l))
        (over all
            (forall (?a2 - vehiclearea)
                (imply (closer ?a2 ?a1) (free ?a2 ?v))
            )
        )
    )
    :effect (and
        (at start (not (can-load ?v ?p)))
        (at start (increase (used-helper-agent ?v) 1))
        (at start (not (at ?p ?l)))
        (at start (not (free ?a1 ?v)))
        (at end (in ?p ?v ?a1))
    )
)


;;;;;;;;;;;;;;;;;;;;;;
;; DELIvERY ACTIONS ;;
;;;;;;;;;;;;;;;;;;;;;;

(:durative-action deliver-ontime
    :parameters (?p - package ?l - location)
    :duration (= ?duration 1)
    :condition (and
        (over all (at ?p ?l))
        (at end (deliverable ?p ?l))
    )
    :effect (and
        (at end (not (at ?p ?l)))
        (at end (delivered ?p ?l))
        (at end (at-destination ?p ?l))
    )
)

(:durative-action deliver-anytime
    :parameters (?p - package ?l - location)
    :duration (= ?duration 1)
    :condition (and
        (at start (at ?p ?l))
        (over all (at ?p ?l))
    )
    :effect (and
        (at end (not (at ?p ?l)))
        (at end (at-destination ?p ?l)))
    )
)


)